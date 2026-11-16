#!/usr/bin/env python3
"""DocumentOCR — minimal web UI backend.

Design constraints (mission):
  * zero new third-party web dependencies -> Python stdlib ``http.server`` only
  * reuse the existing OCR pipeline (``classes.detection.SuryaDetection``),
    never re-implement detection/recognition
  * llama.cpp is started with ``--parallel 1`` -> every OCR job is serialized
    with a global lock
  * per-request temp directory, always cleaned up (retention policy: 0 after
    the response is built)

Run:  python3 webui/server.py   (or ./run_ui.sh from the project root)
"""

from __future__ import annotations

import base64
import io
import difflib
import json
import mimetypes
import os
import re
import shutil
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit, urlparse

# --------------------------------------------------------------------------
# Paths / imports. ``classes/detection.py`` calls load_dotenv() at import
# time, so the CWD must be the project root and it must be on sys.path.
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)

os.chdir(APP_ROOT)
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from loguru import logger  # noqa: E402  (already a project dependency)
from PIL import Image  # noqa: E402

from classes.detection import SuryaDetection  # noqa: E402
from config import settings  # noqa: E402

STATIC_DIR = os.path.join(HERE, "static")
TMP_ROOT = os.path.join(APP_ROOT, ".webui_tmp")
SAVED_ROOT = os.path.join(HERE, "saved")  # persistent OCR results (one dir per save)
MAX_SAVED_ITEMS = int(os.environ.get("WEBUI_MAX_SAVED_ITEMS", "50"))

HOST = os.environ.get("WEBUI_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEBUI_PORT", "8501"))
MAX_UPLOAD_BYTES = int(os.environ.get("WEBUI_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
PREVIEW_MAX_SIDE = 1500
PREVIEW_JPEG_QUALITY = 85
PDF_DPI = 200

# Engine location is derived from the same single source of truth the OCR
# pipeline uses (.env -> SURYA_INFERENCE_URL).
_OCR_URL = os.environ.get("SURYA_INFERENCE_URL", "http://127.0.0.1:8080/v1").rstrip("/")
HEALTH_URL = (_OCR_URL[: -len("/v1")] if _OCR_URL.endswith("/v1") else _OCR_URL) + "/health"
ENGINE_LABEL = "Surya 2.5 · llama.cpp"

try:  # PDF support is only advertised when the existing infra really works
    import pdf2image  # noqa: F401

    _HAS_PDF = shutil.which("pdftoppm") is not None
except Exception:  # pragma: no cover
    _HAS_PDF = False

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
SUPPORTED_EXTENSIONS = sorted(IMAGE_EXTENSIONS | ({".pdf"} if _HAS_PDF else set()))

# --------------------------------------------------------------------------
# Model / pipeline state
# --------------------------------------------------------------------------
_model: SuryaDetection | None = None
_model_lock = threading.Lock()
_pipeline_lock = threading.Lock()  # llama.cpp runs with --parallel 1
_busy = False


def engine_ready(timeout: float = 2.0) -> bool:
    """Probe the llama.cpp server health endpoint (real check, no guessing)."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            payload = json.loads(resp.read().decode("utf-8") or "{}")
            return payload.get("status") == "ok"
    except Exception:
        return False


def get_model() -> SuryaDetection:
    """Create the Surya pipeline once (loads DetectionPredictor + attaches to llama.cpp)."""
    global _model
    if _model is None:
        _model = SuryaDetection(
            output_dir=TMP_ROOT, save=True, detector_type="lines"
        )
    return _model


class _PathDataset:
    """Minimal stand-in for ``classes.dataset.ImagesDataset``.

    ``SuryaDetection.detect()`` only needs ``len()`` and ``get_data()``, so this
    keeps the UI on the exact same code path without touching the original
    dataset class.
    """

    def __init__(self, paths):
        self.data = list(paths)

    def get_data(self):
        return self.data

    def __len__(self):
        return len(self.data)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
_SAFE_NAME = re.compile(r"[^0-9A-Za-z\u0600-\u06FF._-]+")


def safe_stem(filename: str, fallback: str = "document") -> str:
    base = os.path.basename(filename or "").replace("\\", "/")
    base = base.rsplit("/", 1)[-1]
    stem, ext = os.path.splitext(base)
    stem = _SAFE_NAME.sub("_", stem).strip("._-") or fallback
    return stem[:80]


MAX_OVERLAY_BOXES = 3000
BBOX_TOL = 1.5  # px tolerance for out-of-bounds validation


def _boxes_within(boxes, w: float, h: float, tol: float = BBOX_TOL) -> bool:
    for b in boxes:
        x1, y1, x2, y2 = b["bbox"]
        if x1 < -tol or y1 < -tol or x2 > w + tol or y2 > h + tol:
            return False
    return True


def collect_layers(job_dir: str, stem: str, img_size: list) -> dict:
    """Collect the Detection-lines layer from the real ``<stem>_lines.json``.

    Only ``bboxes`` (+ polygon/confidence) are forwarded; the huge
    heatmap/affinity_map arrays are never sent to the UI. Coordinates are
    validated against the real image size — never rescaled silently.
    """
    path = os.path.join(job_dir, f"{stem}_lines.json")
    if not os.path.isfile(path):
        return {"available": False, "reason": "lines_file_missing"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:  # noqa: BLE001
        return {"available": False, "reason": "lines_file_unreadable"}

    raw_boxes = raw.get("bboxes") or []
    lines = []
    for lb in raw_boxes[:MAX_OVERLAY_BOXES]:
        box = lb.get("bbox") if isinstance(lb, dict) else lb
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            coords = [float(v) for v in box]
        except (TypeError, ValueError):
            continue
        poly = None
        if isinstance(lb, dict) and isinstance(lb.get("polygon"), list) and len(lb["polygon"]) >= 3:
            try:
                poly = [[float(p[0]), float(p[1])] for p in lb["polygon"]]
            except (TypeError, ValueError, IndexError):
                poly = None
        conf = lb.get("confidence") if isinstance(lb, dict) else None
        try:
            conf_f = float(conf) if conf is not None else None
        except (TypeError, ValueError):
            conf_f = None
        lines.append({"bbox": coords, "polygon": poly, "confidence": conf_f})

    return {
        "available": len(lines) > 0,
        "valid": _boxes_within(lines, img_size[0], img_size[1]),
        "total": len(raw_boxes),
        "truncated": len(lines) < len(raw_boxes),
        "lines": lines,
    }


def _estimate_skew_cv(gray):
    """Best deskew angle via projection-profile variance (text-line method).

    Binarizes INK only for the estimate (never shown to the OCR engine) and
    searches -8..+8 deg: the angle whose warp makes horizontal text rows form
    the sharpest peaks (max row-sum variance) wins.  Unlike Hough-on-edges
    (v1), this cannot lock onto diagonal table borders — long borders and text
    lines share the same dominant direction, and short diagonal noise barely
    moves the profile.  Returns (angle_deg, best_score, straight_score); the
    returned angle IS the correction to apply.
    """
    import cv2  # noqa: N813
    import numpy as np

    scale = 1000.0 / max(gray.shape[:2])
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                cv2.THRESH_BINARY_INV, 31, 15)
    ih, iw = ink.shape
    center = (iw / 2.0, ih / 2.0)
    best_a, best_s, base_s = 0.0, -1.0, 0.0
    for ang in np.arange(-8.0, 8.01, 0.5):
        m = cv2.getRotationMatrix2D(center, float(ang), 1.0)
        rot = cv2.warpAffine(ink, m, (iw, ih), flags=cv2.INTER_NEAREST, borderValue=0)
        s = float(np.var(rot.sum(axis=1, dtype=np.float64)))
        if abs(ang) < 1e-9:
            base_s = s
        if s > best_s:
            best_a, best_s = float(ang), s
    return best_a, best_s, base_s


def docprep_page(path: str, mode: str) -> str:
    """EXPERIMENTAL opt-in: run the vendored ``document-preprocessor`` package
    BEFORE OCR. Two modes (both atomic: write to a temp file, swap on success):

      * "geometry" (RECOMMENDED) — only the package's geometry-safe steps:
        EXIF fix + quadrilateral perspective warp + DPI-aware downscale.
        NO contrast/denoise/binarize/sharpen (those are tuned for Tesseract
        and REGRESS Surya — see A/B, 2026-11-16: full pipeline dropped
        insurance fields 5/5 -> 0/5, contrast+denoise 5/5 -> 1/5).
      * "full" — the package's complete pipeline (perspective + contrast +
        denoise + Otsu/adaptive binarize + sharpen + DPI), exactly as the
        vendor ships it. Offered for the user's own A/B; expected to hurt
        Surya on flat scans.

    Falls back to the original path on ANY error (never breaks the job).
    """
    if mode not in ("geometry", "full"):
        return path
    try:
        import sys as _sys
        _docprep_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_docprep")
        if _docprep_dir not in _sys.path:
            _sys.path.insert(0, _docprep_dir)
        from document_preprocessor import DocumentPreprocessor, PreprocessorConfig  # noqa: N812
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"docprep unavailable ({exc}) — using original")
        return path
    try:
        from PIL import ImageOps  # noqa: N812
        config = PreprocessorConfig.from_profile_and_env()
        dp = DocumentPreprocessor(config=config)
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")
        if mode == "geometry":
            im = dp.detect_and_warp_document(im)          # perspective warp
            im = dp.to_grayscale(im)                       # Surya prefers grayscale
            im = dp.resize_long_side(im)                    # uses config.target_long_side_px
        else:
            im = dp.process_image(im, debug_dir=None)      # vendored full pipeline
        ext = os.path.splitext(path)[1].lower() or ".jpg"
        tmp = path + ".docprep"
        if ext in (".png",) or im.mode == "P":
            im.convert("RGB").save(tmp, "PNG")           # package's save_for_ocr is JPEG-only
        else:
            im.save(tmp, "JPEG", quality=95, dpi=(config.dpi, config.dpi))
        os.replace(tmp, path)
        return path
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"docprep {mode} failed ({exc}) — keeping original")
        if os.path.isfile(path + ".docprep"):
            try:
                os.remove(path + ".docprep")
            except OSError:
                pass
        return path


def preprocess_page(path: str, enhance: bool) -> str:
    """Doc-quality enhancement BEFORE OCR (the OCR engine is untouched). v2.

    Expert rules (v1's blind autocontrast+Hough REGRESSED a good doc 45->39
    fields, so every step here is conditional and geometry-safe):
      * NO binarization/thresholding reaches the engine — Surya's CNN/Transformer
        detector wants natural grayscale photos, not line-art.
      * illumination normalization: divide by the blurred background -> flattens
        shadows/yellowed paper; SKIPPED when the page is already clean/white.
      * conditional upscale: only small scans (< 1500px longest side, cap 2x),
        plus a mild unsharp mask to restore stroke acuity after interpolation.
      * text-based deskew: projection-profile variance, applied only for
        0.6..15 deg AND only when it clearly beats the straight score (+12%).
      * light denoise only when the high-frequency noise metric is high.
    A clean scan therefore passes through unchanged (changed stays False and
    the file is not even re-encoded), so good documents cannot regress.
    """
    if not enhance:
        return path
    try:
        import cv2  # noqa: N813
        import numpy as np
        from PIL import ImageFilter, ImageOps
    except ImportError:
        return path
    try:
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:  # noqa: BLE001
        return path

    w, h = im.size
    changed = False
    arr = np.asarray(im)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # 1) illumination normalization — ONLY for genuinely dark/colored or
    #    heavily shadowed pages. Evidence (A/B, 2026-11-15): the good insurance
    #    scan has bg.std=15.9 purely from its own colored panels -> a std-based
    #    gate falsely "enhanced" it and cost 5 fields; a dark-background green
    #    card (bg.mean=179) genuinely needs it (+15 detected lines).
    k = max(31, (max(w, h) // 30) * 2 + 1)
    k = min(k, (min(w, h) // 2) * 2 - 1)
    if k >= 3:
        bg = cv2.GaussianBlur(gray, (k, k), 0)
        if float(bg.mean()) < 200.0 or float(bg.std()) > 25.0:
            f = arr.astype(np.float32)
            bgf = cv2.GaussianBlur(f, (k, k), 0)
            out = np.clip(f / np.maximum(bgf, 1.0) * 235.0, 0, 255).astype(np.uint8)
            arr, im = out, Image.fromarray(out)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            changed = True

    # 2) upscale small scans (detector misses small text otherwise), cap 2x
    if max(w, h) < 1500:
        scale = min(2.0, 1500.0 / max(w, h))
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
        arr = np.asarray(im)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        changed = True

    # 3) deskew via text-row projection variance (best-effort, small angles only)
    try:
        ang, best_s, base_s = _estimate_skew_cv(gray)
        if 0.6 <= abs(ang) <= 15.0 and best_s > base_s * 1.12:
            im = im.rotate(ang, resample=Image.BICUBIC, expand=False,
                           fillcolor=(255, 255, 255))
            changed = True
    except Exception:  # noqa: BLE001
        pass

    if changed:
        try:
            if path.lower().endswith((".jpg", ".jpeg")):
                im.save(path, quality=95)
            else:
                im.save(path)
        except OSError:
            return path  # read-only/unwritable page: keep original
    return path


def preview_data_url(image_path: str) -> str:
    """Downscaled JPEG preview (used for PDF pages, which the browser cannot preview)."""
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        im.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=PREVIEW_JPEG_QUALITY, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def image_size(image_path: str):
    with Image.open(image_path) as im:
        return list(im.size)


# --------------------------------------------------------------------------
# Table field extraction (post-processing only: OCR engine output unchanged).
# Builds Table -> fields -> key/value from the REAL engine HTML structure and
# the REAL detection-line geometry. Bounding boxes are never fabricated: a
# field without a matching detection line gets bbox=null + bbox_status="none".
# --------------------------------------------------------------------------
from html.parser import HTMLParser
from html import unescape as _html_unescape


class _TableHTMLParser(HTMLParser):
    """Rows of {text, colspan} cells from a <table> HTML fragment."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.rows: list = []
        self._row = None
        self._cell = None
        self._colspan = 1

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            try:
                self._colspan = max(1, int(dict(attrs).get("colspan", "1")))
            except ValueError:
                self._colspan = 1

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            text = re.sub(r"\s+", " ", _html_unescape("".join(self._cell))).strip()
            self._row.append({"text": text, "colspan": self._colspan})
            self._cell = None
            self._colspan = 1
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _split_kv(cell_text: str):
    """'نام پدر: اکبر' -> ('نام پدر', 'اکبر');  'کد پستی:' -> ('کد پستی', '');"""
    if ":" in cell_text:
        key, _, value = cell_text.partition(":")
        return key.strip(" :.\u2013-"), value.strip()
    return None, None  # bare cell (no colon)


def _split_trailing_number(text: str):
    """'label ۱۲۳.۴۵' -> ('label', '۱۲۳.۴۵'); (None, None) without a trailing number."""
    m = re.search(r"([۰-۹٠-٩0-9][۰-۹٠-٩0-9.,/%]*)\s*$", text or "")
    if not m:
        return None, None
    prefix = text[:m.start()].strip()
    # the prefix must contain a real (non-numeric) label word
    if not prefix or not re.search(r"[^\s\d۰-۹٠-٩.,/%+\-]", prefix):
        return None, None
    return prefix, m.group(1)


def _split_merged_pair(ktext: str, vtext: str):
    """Split engine-merged label+value patterns in adjacent bare-cell pairs.

    P2 operator: left cell is a lone formula operator ('+'/'-'/'=') and the
                 right cell merged label+amount -> key=label, value=amount.
    P1 echo:     right cell is a short label echoed inside the left cell
                 ('شماره' | 'شماره ۳۱۵۳۰/...') -> value = trailing number.
    Otherwise the pair is returned unchanged (never invent data).
    """
    kt, vt = (ktext or "").strip(), (vtext or "").strip()
    if not kt or not vt:
        return ktext, vtext
    if len(vt) == 1 and vt in "+-=×x*":
        key, num = _split_trailing_number(kt)
        if num:
            return key, num
        return ktext, vtext
    # P1 echo: the short label (vt) re-appears at the start of the merged
    # cell (kt): 'شماره' | 'شماره ۳۱۵۳۰/...' -> key='شماره', value=number
    nkt = re.sub(r"[\s\u200c]+", "", kt)
    nvt = re.sub(r"[\s\u200c]+", "", vt)
    labelish = re.search(r"[^\s\d۰-۹٠-٩.,/%+\-]", vt)
    if labelish and 2 <= len(nvt) < len(nkt) and nkt.startswith(nvt):
        key, num = _split_trailing_number(kt)
        if num:
            return vt, num
    return ktext, vtext


def _line_inside(bbox, table_bbox, tol=6.0):
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return (table_bbox[0] - tol <= cx <= table_bbox[2] + tol
            and table_bbox[1] - tol <= cy <= table_bbox[3] + tol)


def extract_table_fields(block: dict, det_lines: list) -> list:
    """Fields of one Table block: real cell structure + real line geometry.

    Rows/cells come from the engine's own <table> HTML; each field's bbox is
    the union of the real detection lines mapped to its cells (RTL order:
    first cell of a row = rightmost line of the visual row). No line -> no bbox.
    """
    parser = _TableHTMLParser()
    try:
        parser.feed(block.get("html") or "")
    except Exception:  # noqa: BLE001
        return []
    rows = parser.rows
    bbox = block.get("bbox")
    if not rows or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return []
    try:
        tb = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return []

    # real text lines inside the table (aspect>=1.2 filters grid-line stubs)
    text_lines = []
    for ln in det_lines or []:
        lb = ln.get("bbox") if isinstance(ln, dict) else None
        if not lb or len(lb) != 4:
            continue
        try:
            lb = [float(v) for v in lb]
        except (TypeError, ValueError):
            continue
        w, h = abs(lb[2] - lb[0]), abs(lb[3] - lb[1])
        if w < 8 or w / max(h, 1.0) < 1.2:
            continue
        if _line_inside(lb, tb):
            text_lines.append(lb)

    # assign every line to its HTML row by proportional y-position (never by
    # threshold clustering: small row gaps merged rows and shifted the
    # cluster->row index, which silently dropped cell geometry)
    bands = [[] for _ in rows]
    y_span = (tb[3] - tb[1]) or 1.0
    for lb in text_lines:
        cy = (lb[1] + lb[3]) / 2
        r = int((cy - tb[1]) / y_span * len(rows))
        r = min(max(r, 0), len(rows) - 1)
        bands[r].append(lb)

    conf = block.get("confidence")
    try:
        conf = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf = None

    def line_union(boxes):
        boxes = [b for b in boxes if b]
        if not boxes:
            return None
        return [min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes)]

    fields = []
    for r_idx, row in enumerate(rows):
        band = bands[r_idx]
        # RTL: first cell of the row = rightmost line of the visual row
        row_lines = sorted(band, key=lambda b: (b[0] + b[2]) / 2, reverse=True)
        # a single wide line (detector merged both cell texts) covers every cell
        if len(band) == 1 and len(row) > 1:
            row_lines = [band[0]] * len(row)

        pending_key = None  # colon-field awaiting its value from a bare cell
        bare = []           # [(text, line)] label-less cells awaiting RTL pairing

        def flush_bare():
            # pair consecutive bare cells (RTL): first = key, second = value.
            # This builds the real Table -> Fields -> Key/Value hierarchy for
            # tables whose cells carry no colon (e.g. label/value column pairs).
            i = 0
            while i < len(bare):
                ktext, kline = bare[i]
                if i + 1 < len(bare) and len(ktext) > 1:
                    # a single character is never a label (VIN-letter rows etc.)
                    vtext, vline = bare[i + 1]
                    skey, svalue = _split_merged_pair(ktext, vtext)
                    boxes = [b for b in (kline, vline) if b]
                    fields.append({
                        "key": skey, "value": svalue,
                        "bbox": line_union(boxes),
                        "key_bbox": kline[:] if kline else None,
                        "value_bbox": vline[:] if vline else None,
                        "confidence": conf,
                        "bbox_status": "line" if boxes else "none",
                    })
                    i += 2
                else:  # single-char or leftover cell -> value-only fragment
                    fields.append({
                        "key": "", "value": ktext,
                        "bbox": kline[:] if kline else None,
                        "key_bbox": None, "value_bbox": None,
                        "confidence": conf,
                        "bbox_status": "line" if kline else "none",
                    })
                    i += 1
            bare.clear()

        for c_idx, cell in enumerate(row):
            text = cell.get("text") or ""
            if not text:
                continue
            line = row_lines[c_idx] if c_idx < len(row_lines) else None
            key, value = _split_kv(text)
            if key is not None:  # colon cell -> new field (engine's own "Key: Value")
                flush_bare()
                field = {
                    "key": key, "value": value,
                    "bbox": line[:] if line else None,
                    "key_bbox": line[:] if line else None, "value_bbox": None,
                    "confidence": conf,
                    "bbox_status": "line" if line else "none",
                }
                fields.append(field)
                pending_key = field if not value else None
            else:  # bare cell: value of a key-only cell, else queued for pairing
                if pending_key is not None and not pending_key["value"]:
                    pending_key["value"] = text
                    if line:
                        pending_key["value_bbox"] = line[:]
                        pending_key["bbox"] = line_union([pending_key["bbox"], line])
                    pending_key = None
                else:
                    bare.append((text, line[:] if line else None))
        flush_bare()

    return fields


def inject_table_fields(payload: dict, layers: dict) -> int:
    """Add 'fields' to every Table block of a page payload (incremental)."""
    if not isinstance(payload, dict):
        return 0
    lines = (layers or {}).get("lines") or []
    added = 0
    for block in payload.get("blocks") or []:
        if block.get("label") != "Table":
            continue
        if "<table" not in (block.get("html") or "").lower():
            continue
        fields = extract_table_fields(block, lines if (layers or {}).get("available") else [])
        if fields:
            block["fields"] = fields
            block["fields_count"] = len(fields)
            added += len(fields)
    return added


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.hint = hint


def purge_stale_temp(max_age_s: int = 3600) -> None:
    """Remove leftovers from previously crashed runs (crash-safety net)."""
    if not os.path.isdir(TMP_ROOT):
        return
    now = time.time()
    for name in os.listdir(TMP_ROOT):
        path = os.path.join(TMP_ROOT, name)
        try:
            if now - os.path.getmtime(path) > max_age_s:
                shutil.rmtree(path, ignore_errors=True)
                logger.info(f"purged stale temp dir: {path}")
        except OSError:
            pass


# --------------------------------------------------------------------------
# Saved results (persistent, on-disk; survives restarts and reloads)
# --------------------------------------------------------------------------
_SAVE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _save_dir(save_id: str) -> str:
    if not _SAVE_ID_RE.match(save_id or ""):
        raise HttpError(400, "bad_id", "شناسهٔ ذخیره نامعتبر است.")
    return os.path.join(SAVED_ROOT, save_id)


def save_result(payload: dict) -> dict:
    """Persist an OCR result (client POSTs back the exact /api/ocr response).

    Layout: webui/saved/<id>/meta.json + page_<n>.jpg per page. ``preview``
    data URLs are decoded to real JPEG files so meta.json stays lean; they
    are regenerated from those files on every read.
    """
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise HttpError(400, "bad_payload", "ساختار نتیجهٔ OCR نامعتبر است.")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise HttpError(400, "bad_payload", "نتیجهٔ OCR هیچ صفحه‌ای ندارد.")

    try:
        existing = [n for n in os.listdir(SAVED_ROOT) if _SAVE_ID_RE.match(n)]
    except FileNotFoundError:
        existing = []
    if len(existing) >= MAX_SAVED_ITEMS:
        raise HttpError(
            413,
            "too_many_saved",
            f"تعداد نتایج ذخیره‌شده به حداکثر ({MAX_SAVED_ITEMS}) رسیده است.",
            "چند مورد قدیمی را حذف کنید و دوباره تلاش کنید.",
        )

    save_id = uuid.uuid4().hex
    final_dir = os.path.join(SAVED_ROOT, save_id)
    tmp_dir = final_dir + ".partial"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        clean_pages = []
        for page in pages:
            if not isinstance(page, dict):
                raise HttpError(400, "bad_payload", "ساختار صفحهٔ نتیجه نامعتبر است.")
            entry = {k: page.get(k) for k in
                     ("page", "text", "blocks", "chars", "json", "image_size",
                      "blocks_valid", "layers")}
            preview = page.get("preview")
            if isinstance(preview, str) and preview.startswith("data:image/jpeg;base64,"):
                try:
                    img_bytes = base64.b64decode(preview.split(",", 1)[1], validate=True)
                except Exception:  # noqa: BLE001
                    img_bytes = None
                if img_bytes:
                    name = f"page_{page.get('page', len(clean_pages) + 1)}.jpg"
                    with open(os.path.join(tmp_dir, name), "wb") as f:
                        f.write(img_bytes)
                    entry["has_image"] = name
            clean_pages.append(entry)

        meta = {
            "id": save_id,
            "name": (_clean_label(payload.get("file"))
                     if payload.get("file") else "document"),
            "kind": payload.get("kind") or "image",
            "page_count": payload.get("page_count") or len(clean_pages),
            "elapsed_ms": payload.get("elapsed_ms"),
            "pipeline_ms": payload.get("pipeline_ms"),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pages": clean_pages,
        }
        tmp_meta = os.path.join(tmp_dir, "meta.json")
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        os.replace(tmp_meta, os.path.join(tmp_dir, "meta.json"))  # fs-sync point
        os.rename(tmp_dir, final_dir)  # atomic publish
    except HttpError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(f"save_result failed: {exc}\n{traceback.format_exc()}")
        raise HttpError(500, "save_failed", "ذخیرهٔ نتیجه ناموفق بود.") from exc

    logger.info(f"OCR result saved: id={save_id} name={meta['name']!r} pages={len(clean_pages)}")
    return {"ok": True, "id": save_id, "saved_at": meta["created_at"]}


def _load_meta(save_id: str) -> dict:
    path = os.path.join(_save_dir(save_id), "meta.json")
    if not os.path.isfile(path):
        raise HttpError(404, "not_found", "نتیجهٔ ذخیره‌شده یافت نشد.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"unreadable meta.json for {save_id}: {exc}")
        raise HttpError(500, "unreadable", "خواندن نتیجهٔ ذخیره‌شده ناموفق بود.") from exc


def list_saved() -> list:
    """Saved items, newest first (summary only — no page payloads)."""
    items = []
    if not os.path.isdir(SAVED_ROOT):
        return items
    for name in os.listdir(SAVED_ROOT):
        if not _SAVE_ID_RE.match(name):
            continue
        try:
            meta = _load_meta(name)
        except HttpError:
            continue
        chars = sum(int(p.get("chars") or 0) for p in meta.get("pages", []))
        items.append({
            "id": meta["id"],
            "name": meta.get("name"),
            "kind": meta.get("kind"),
            "page_count": meta.get("page_count"),
            "chars": chars,
            "created_at": meta.get("created_at"),
        })
    items.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return items


def read_saved(save_id: str) -> dict:
    """Rebuild the exact /api/ocr response shape from a saved item."""
    meta = _load_meta(save_id)
    pages = []
    for page in meta.get("pages", []):
        entry = dict(page)
        img_name = entry.pop("has_image", None)
        if img_name:
            entry["preview"] = preview_data_url(os.path.join(_save_dir(save_id), img_name))
        pages.append(entry)
    return {
        "ok": True,
        "saved": True,
        "id": meta["id"],
        "file": meta.get("name"),
        "kind": meta.get("kind"),
        "page_count": meta.get("page_count"),
        "elapsed_ms": meta.get("elapsed_ms"),
        "pipeline_ms": meta.get("pipeline_ms"),
        "saved_at": meta.get("created_at"),
        "pages": pages,
    }


def delete_saved(save_id: str) -> dict:
    path = _save_dir(save_id)
    if not os.path.isdir(path):
        raise HttpError(404, "not_found", "نتیجهٔ ذخیره‌شده یافت نشد.")
    shutil.rmtree(path, ignore_errors=True)
    logger.info(f"OCR result deleted: id={save_id}")
    return {"ok": True, "id": save_id}


_SAFE_LABEL = re.compile(r"[^0-9A-Za-z\u0600-\u06FF ._،؛():\u2013\u2014\u0640\-]+")
_LABEL_MAX_LEN = 100


def _clean_label(raw) -> str:
    """Sanitize a user-provided display name (no path, no control chars)."""
    if not isinstance(raw, str):
        raise HttpError(400, "bad_name", "نام باید یک رشتهٔ متنی باشد.")
    name = _SAFE_LABEL.sub("_", raw)
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    name = name[:_LABEL_MAX_LEN].strip()
    if not name:
        raise HttpError(400, "bad_name", "نام نمی‌تواند خالی باشد.",
                        "یک نام معتبر وارد کنید.")
    return name


def rename_saved(save_id: str, new_name) -> dict:
    """Change the display name of a saved result (meta.json rewrite, atomic)."""
    meta = _load_meta(save_id)  # 404 if missing; also validates the id
    old_name = meta.get("name")
    meta["name"] = _clean_label(new_name)
    meta_path = os.path.join(_save_dir(save_id), "meta.json")
    tmp_path = meta_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        os.replace(tmp_path, meta_path)  # atomic publish
    except Exception as exc:  # noqa: BLE001
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
        logger.error(f"rename_saved failed: {exc}\n{traceback.format_exc()}")
        raise HttpError(500, "rename_failed", "تغییر نام ناموفق بود.") from exc
    logger.info(f"OCR result renamed: id={save_id} {old_name!r} -> {meta['name']!r}")
    return {"ok": True, "id": save_id, "name": meta["name"]}


_DIGIT_RUN = re.compile(r"[0-9۰-۹][0-9۰-۹.,/\-]*")
_REFINE_MODEL = os.environ.get("OCR_REFINE_MODEL", "baidu/ernie-5.5-flash-preview:free")
_REFINE_SYS = (
    "تو اصلاح‌کنندهٔ متن چاپی فارسی هستی که از OCR پرشده است. "
    "فقط اشتباهات واضح تشخیص حروف (مثل شباهت حروف) را اصلاح کن. "
    "اعداد، ارقام، نشانه‌ها، فرمت‌ها و ترتیب خطوط را دست نزن. "
    "اگر خطی درست است عیناً برگردان. خروجی: فقط همان خطوط اصلاح‌شده، هر خط در یک سطر."
)


def refine_text_free_llm(text: str):
    """EXPERIMENTAL opt-in: post-OCR Persian char-error correction via a FREE
    OpenRouter model. Hard safety rails (verified in A/B, 2026-11-16):
      1. every digit run of every output line must EXACTLY equal the source
         line's runs (no numeric invention - dates/amounts are untouchable),
      2. line-level similarity >= 0.5 vs source (rejects rewritten lines),
      3. per-line acceptance: a failed guard keeps the ORIGINAL line.
    Returns the corrected text, or None when disabled/unavailable/no change.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key or not text.strip():
        return None
    lines = [l for l in text.splitlines() if l.strip()]
    body = {
        "model": _REFINE_MODEL,
        "messages": [{"role": "system", "content": _REFINE_SYS},
                     {"role": "user",
                      "content": "خطوط:\n" + "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines))}],
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.load(r)["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001 - free tier may 429/timeout: stay safe
        logger.warning(f"refine skipped: {exc}")
        return None
    out_lines = [re.sub(r"^\d+[\.\):]\s*", "", l.strip()) for l in out.splitlines() if l.strip()]
    if len(out_lines) != len(lines):
        logger.warning("refine skipped: line count changed")
        return None
    fixed, changed = [], False
    for src, cand in zip(lines, out_lines):
        ok = (_DIGIT_RUN.findall(src) == _DIGIT_RUN.findall(cand)
              and difflib.SequenceMatcher(None, src, cand).ratio() >= 0.5)
        if ok and cand != src:
            changed = True
        fixed.append(cand if ok else src)
    return "\n".join(fixed) if changed else None


def run_pipeline(upload_bytes: bytes, filename: str, enhance: bool = True, refine: bool = False,
                 docprep: str = "") -> dict:
    """Execute the real OCR pipeline for one uploaded document."""
    global _busy

    if not settings.ENABLE_RECOGNITION:
        raise HttpError(
            503,
            "recognition_disabled",
            "استخراج متن در تنظیمات غیرفعال شده است.",
            "ENABLE_RECOGNITION=true را در .env تنظیم کنید.",
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HttpError(
            415,
            "unsupported_type",
            "فرمت فایل پشتیبانی نمی‌شود.",
            "فرمت‌های مجاز: " + "، ".join(e.lstrip(".").upper() for e in SUPPORTED_EXTENSIONS),
        )

    if not engine_ready():
        raise HttpError(
            503,
            "engine_unavailable",
            "سرویس OCR در دسترس نیست.",
            "سرور پردازش اجرا نشده است. با اجرای run_ocr.sh یا run_ui.sh دوباره تلاش کنید.",
        )

    job_dir = os.path.join(TMP_ROOT, uuid.uuid4().hex)
    os.makedirs(job_dir, exist_ok=True)
    started = time.time()
    try:
        raw_path = os.path.join(job_dir, "upload" + ext)
        with open(raw_path, "wb") as f:
            f.write(upload_bytes)

        # ---- normalise / split the input into page images ------------------
        pages: list[str] = []
        kind = "image"
        if ext == ".pdf":
            kind = "pdf"
            from pdf_utils import pdf_to_images  # existing project helper

            try:
                pages = pdf_to_images(raw_path, os.path.join(job_dir, "pages"), dpi=PDF_DPI)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"pdf conversion failed: {exc}\n{traceback.format_exc()}")
                raise HttpError(
                    422,
                    "pdf_failed",
                    "خواندن فایل PDF ناموفق بود.",
                    "از سالم بودن فایل و رمزگذاری‌نبودن آن مطمئن شوید.",
                ) from exc
            if not pages:
                raise HttpError(422, "pdf_empty", "این فایل PDF هیچ صفحه‌ای ندارد.")
        else:
            page_path = os.path.join(job_dir, "page_1.png")
            try:
                with Image.open(raw_path) as im:
                    im.convert("RGB").save(page_path, "PNG")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"image decode failed: {exc}")
                raise HttpError(
                    422,
                    "unreadable_image",
                    "فایل تصویری قابل خواندن نیست.",
                    "ممکن است فایل خراب یا با پسوند نادرست ذخیره شده باشد.",
                ) from exc
            pages = [page_path]

        # ---- optional doc-quality enhancement before OCR -------------------
        if docprep in ("geometry", "full"):
            pages = [docprep_page(p, docprep) for p in pages]
        pages = [preprocess_page(p, enhance) for p in pages]

        # ---- run the existing pipeline (serialized: --parallel 1) ----------
        with _pipeline_lock:
            _busy = True
            try:
                logger.info(
                    f"OCR job start: file={filename!r} kind={kind} pages={len(pages)}"
                )
                model = get_model()
                model.output_dir = job_dir  # per-request output dir (single-threaded)
                job_started = time.time()
                model.detect(_PathDataset(pages))
                job_elapsed = time.time() - job_started
            finally:
                _busy = False

        # ---- collect real engine output ------------------------------------
        result_pages = []
        failures = []
        for index, page_path in enumerate(pages, start=1):
            stem = os.path.splitext(os.path.basename(page_path))[0]
            ocr_path = os.path.join(job_dir, f"{stem}_ocr.json")
            if not os.path.isfile(ocr_path):
                failures.append(index)
                continue
            with open(ocr_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            text = (payload.get("text") or "").strip()
            if refine:
                refined = refine_text_free_llm(text)
                if refined is not None:
                    text = refined
            entry = {
                "page": index,
                "text": text,
                "blocks": len(payload.get("blocks") or []),
                "chars": len(text),
                "json": payload,
                "image_size": image_size(page_path),
            }
            blocks_raw = payload.get("blocks") or []
            blocks_boxes = [
                {"bbox": b["bbox"]}
                for b in blocks_raw
                if isinstance(b.get("bbox"), (list, tuple)) and len(b["bbox"]) == 4
            ]
            entry["blocks_valid"] = _boxes_within(blocks_boxes, *entry["image_size"])
            entry["layers"] = collect_layers(job_dir, stem, entry["image_size"])
            fields_n = inject_table_fields(payload, entry["layers"])
            if fields_n:
                logger.info(f"table fields extracted on page {index}: {fields_n}")
            if kind == "pdf" or enhance:
                # preview from the ACTUAL processed page guarantees the bbox
                # overlay aligns even when enhancement resized/deskewed it
                entry["preview"] = preview_data_url(page_path)
            result_pages.append(entry)

        if not result_pages:
            raise HttpError(
                503,
                "recognition_failed",
                "استخراج متن از سند ناموفق بود.",
                "اتصال سرور OCR یا سالم بودن تصویر را بررسی کنید.",
            )

        if failures:
            logger.error(f"recognition failed for pages: {failures}")

        # A blank result must never be reported as success.
        if all(not p["text"] for p in result_pages):
            raise HttpError(
                422,
                "no_text",
                "متنی در سند شناسایی نشد.",
                "تصویر ممکن است خالی، تار یا بدون متن قابل تشخیص باشد.",
            )

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            f"OCR job done: pages={len(result_pages)} "
            f"chars={sum(p['chars'] for p in result_pages)} in {elapsed_ms} ms"
        )
        return {
            "ok": True,
            "file": filename,
            "kind": kind,
            "page_count": len(pages),
            "elapsed_ms": elapsed_ms,
            "pipeline_ms": int(job_elapsed * 1000),
            "pages": result_pages,
        }
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "DocumentOCR/1.0"
    protocol_version = "HTTP/1.1"

    # -- low level ------------------------------------------------------
    def log_message(self, fmt, *args):  # route stdlib access logs to loguru
        logger.debug("webui " + fmt % args)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str) -> None:
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".js"):
            ctype = "text/javascript; charset=utf-8"
        elif path.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif path.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif path.endswith(".ttf"):
            ctype = "font/ttf"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, rel: str) -> None:
        rel = rel.lstrip("/")
        target = os.path.abspath(os.path.join(STATIC_DIR, rel))
        if not target.startswith(os.path.abspath(STATIC_DIR) + os.sep):
            self._send_json(404, {"ok": False, "code": "not_found", "message": "مسیر یافت نشد."})
            return
        if not os.path.isfile(target):
            self._send_json(404, {"ok": False, "code": "not_found", "message": "فایل یافت نشد."})
            return
        self._send_file(target)

    # -- routes ---------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._static("index.html")
            elif path.startswith("/static/"):
                self._static(path[len("/static/"):])
            elif path == "/api/health":
                ready = engine_ready()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "service": "online",
                        "engine": {
                            "label": ENGINE_LABEL,
                            "ready": ready,
                            "endpoint": HEALTH_URL,
                        },
                        "busy": _busy,
                        "pdf": _HAS_PDF,
                        "max_upload_bytes": MAX_UPLOAD_BYTES,
                        "formats": [e.lstrip(".") for e in SUPPORTED_EXTENSIONS],
                    },
                )
            elif path == "/api/config":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "max_upload_bytes": MAX_UPLOAD_BYTES,
                        "formats": [e.lstrip(".") for e in SUPPORTED_EXTENSIONS],
                        "pdf": _HAS_PDF,
                    },
                )
            elif path == "/api/saved":
                self._send_json(200, {"ok": True, "items": list_saved()})
            elif path.startswith("/api/saved/"):
                self._send_json(200, read_saved(path[len("/api/saved/"):]))
            else:
                self._send_json(404, {"ok": False, "code": "not_found", "message": "مسیر یافت نشد."})
        except Exception as exc:  # noqa: BLE001
            logger.error(f"GET {path} failed: {exc}\n{traceback.format_exc()}")
            self._send_json(500, {"ok": False, "code": "server_error", "message": "خطای داخلی سرور."})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/saved":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    raise HttpError(400, "empty_body", "داده‌ای برای ذخیره ارسال نشده است.")
                if length > MAX_UPLOAD_BYTES:
                    raise HttpError(413, "too_large", "حجم نتیجهٔ ارسالی بیش از حد مجاز است.")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise HttpError(400, "truncated_body", "داده به‌طور کامل دریافت نشد.")
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    raise HttpError(400, "bad_json", "بدنهٔ درخواست JSON معتبر نیست.")
                self._send_json(200, save_result(payload))
            except HttpError as err:
                logger.warning(f"save rejected [{err.code}]: {err.message}")
                self._send_json(err.status, {"ok": False, "code": err.code, "message": err.message, "hint": err.hint})
            except Exception as exc:  # noqa: BLE001
                logger.error(f"POST /api/saved failed: {exc}\n{traceback.format_exc()}")
                self._send_json(500, {"ok": False, "code": "server_error", "message": "خطای داخلی سرور."})
            return

        if path != "/api/ocr":
            self._send_json(404, {"ok": False, "code": "not_found", "message": "مسیر یافت نشد."})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                raise HttpError(400, "empty_body", "فایلی ارسال نشده است.")
            if length > MAX_UPLOAD_BYTES:
                raise HttpError(
                    413,
                    "file_too_large",
                    f"حجم فایل بیشتر از حد مجاز ({MAX_UPLOAD_BYTES // (1024 * 1024)} مگابایت) است.",
                )

            raw_name = unquote(self.headers.get("X-Filename") or "document")
            filename = os.path.basename(raw_name.replace("\\", "/")) or "document"
            # the stored name is always rebuilt from a sanitized stem
            filename = safe_stem(filename) + os.path.splitext(filename)[1].lower()

            body = self.rfile.read(length)
            if len(body) != length:
                raise HttpError(400, "truncated_body", "فایل به‌طور کامل دریافت نشد.")

            enhance_q = (urlsplit(self.path).query or "")
            qs = parse_qs(enhance_q)
            enhance = (qs.get("enhance") or ["1"])[0] not in ("0", "false", "off")
            refine = (qs.get("refine") or ["0"])[0] not in ("0", "false", "off")
            docprep = (qs.get("docprep") or [""])[0]
            if docprep not in ("", "geometry", "full"):
                docprep = ""
            payload = run_pipeline(body, filename, enhance=enhance, refine=refine, docprep=docprep)
            self._send_json(200, payload)

        except HttpError as err:
            logger.warning(f"OCR request rejected [{err.code}]: {err.message}")
            self._send_json(
                err.status,
                {"ok": False, "code": err.code, "message": err.message, "hint": err.hint},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"POST /api/ocr failed: {exc}\n{traceback.format_exc()}")
            self._send_json(
                500,
                {
                    "ok": False,
                    "code": "processing_failed",
                    "message": "پردازش سند با خطا مواجه شد.",
                    "hint": "جزئیات در لاگ سرور ثبت شده است.",
                },
            )


    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/saved/"):
                self._send_json(200, delete_saved(path[len("/api/saved/"):]))
            else:
                self._send_json(404, {"ok": False, "code": "not_found", "message": "مسیر یافت نشد."})
        except HttpError as err:
            self._send_json(err.status, {"ok": False, "code": err.code, "message": err.message, "hint": err.hint})
        except Exception as exc:  # noqa: BLE001
            logger.error(f"DELETE {path} failed: {exc}\n{traceback.format_exc()}")
            self._send_json(500, {"ok": False, "code": "server_error", "message": "خطای داخلی سرور."})

    def do_PATCH(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/saved/"):
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    raise HttpError(400, "empty_body", "داده‌ای ارسال نشده است.")
                if length > 64 * 1024:
                    raise HttpError(413, "too_large", "بدنهٔ درخواست بیش از حد بزرگ است.")
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    raise HttpError(400, "bad_json", "بدنهٔ درخواست JSON معتبر نیست.")
                if not isinstance(payload, dict) or "name" not in payload:
                    raise HttpError(400, "bad_payload", "فیلد «name» الزامی است.")
                self._send_json(200, rename_saved(path[len("/api/saved/"):], payload["name"]))
            else:
                self._send_json(404, {"ok": False, "code": "not_found", "message": "مسیر یافت نشد."})
        except HttpError as err:
            self._send_json(err.status, {"ok": False, "code": err.code, "message": err.message, "hint": err.hint})
        except Exception as exc:  # noqa: BLE001
            logger.error(f"PATCH {path} failed: {exc}\n{traceback.format_exc()}")
            self._send_json(500, {"ok": False, "code": "server_error", "message": "خطای داخلی سرور."})


def main() -> None:
    os.makedirs(TMP_ROOT, exist_ok=True)
    os.makedirs(SAVED_ROOT, exist_ok=True)
    purge_stale_temp()

    if not engine_ready(timeout=3):
        logger.warning(
            f"engine NOT reachable at {HEALTH_URL} — the UI will start, "
            "but OCR requests return 503 until the llama.cpp server is up."
        )
    else:
        logger.info(f"engine reachable at {HEALTH_URL}")

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    logger.info(f"DocumentOCR UI listening on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
