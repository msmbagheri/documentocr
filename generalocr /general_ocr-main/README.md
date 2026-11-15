# general_ocr

This repository is created to make a general pipeline for adding new datasets to our OCR flow.

The current task is to generate to-be-refined labels on Kotob Darsi dataset.

## Installation

Tested on python 3.10

```pip install -r requirements.txt```

## Usage

Suppose you have download a book pdf from [here](http://www.chap.sch.ir/books)

Then use `pdf_utils.py` to convert it to a set of images.

Then set the images folder path as `DATA_PATH` in the `.env` file.

Change other vars in `.env` to suit your case, you can see an example already, make it similar to this.

Then run

```python main.py```

---

## Local Surya 2.5 recognition (llama.cpp, offline)

The pipeline reads text with Surya 2.5 served by a local `llama.cpp` server.

### One-time assets (already present)

| File | Size |
|---|---|
| `datasets/surya_gguf/surya-2.5-Q8_0.gguf` | 628,680,096 B |
| `datasets/surya_gguf/surya-2.5-mmproj.gguf` | 207,345,920 B |
| `datasets/surya_gguf/SHA256SUMS.txt` | checksums |

Surya text-detection weights are cached at `~/.cache/datalab/models/text_detection/2025_05_07` (74 MB).

### Start everything with one command

```bash
./run_ocr.sh
```

`run_ocr.sh` starts the server container (if not running), waits for `/health`, then runs `main.py`.

### Manual server start

```bash
docker run -d --name surya-llama --gpus all \
  -p 127.0.0.1:8080:8080 \
  -v /home/metadeep-one/projects/documentocr/datasets/surya_gguf:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server-cuda \
  -m /models/surya-2.5-Q8_0.gguf \
  --mmproj /models/surya-2.5-mmproj.gguf \
  -ngl 99 --host 0.0.0.0 --port 8080 \
  --parallel 1 --ctx-size 16384 \
  --image-min-tokens 1024 \
  --alias datalab-to/surya-ocr-2.5 \
  --jinja --special
```

> `--image-min-tokens 1024` is required: without it Surya 2.5 loses short/small images
> (observed: empty or heavily corrupted output). `--alias` must be exactly
> `datalab-to/surya-ocr-2.5` — the model id Surya verifies via `/v1/models`.

### Outputs

Per input image in `JSONS_PATH`:

- `<stem>_lines.json` — detection boxes (unchanged contract)
- `<stem>_ocr.json` — recognized text: `text` + `blocks[]` (label, bbox, reading_order, html)

### Switches (`config.py` / `.env`)

| Var | Default | Meaning |
|---|---|---|
| `ENABLE_RECOGNITION` | `true` | run Surya recognition, write `*_ocr.json` |
| `ENABLE_PADDLE` | `false` | run the Paddle layout stage + layout merge (currently crashes on this host) |
| `SURYA_INFERENCE_BACKEND` | `llamacpp` | force llama.cpp backend |
| `SURYA_INFERENCE_URL` | `http://127.0.0.1:8080/v1` | attach to running server |

If the server is down, recognition logs `SpawnError: ... not reachable at /health`
per image and the pipeline still completes detection.

---

## Web UI (no-terminal usage)

A minimal RTL web interface (`webui/`) on top of the **same** Surya 2.5 + llama.cpp
pipeline — no new frameworks (Python stdlib `http.server` only, vanilla JS).

```bash
./run_ui.sh            # starts the engine if needed + web UI on http://127.0.0.1:8501
```

Open `http://127.0.0.1:8501`, drop an image (PNG/JPG/JPEG/WEBP/TIFF/BMP) or a
multi-page PDF, press «شروع OCR», and read the extracted text, processing info
and the real engine JSON in the same page. Copy / download TXT and JSON are
built in.

How it connects: `POST /api/ocr` (raw bytes + `X-Filename`) → the backend saves
the upload under `.webui_tmp/<job>/`, converts PDFs via the existing
`pdf_utils.pdf_to_images`, and runs the existing `SuryaDetection.detect()` on
every page (a thin shim provides `get_data()`). The response contains the
**real** `*_ocr.json` payload per page. Jobs are serialized with a global lock
(the engine runs `--parallel 1`); temp dirs are deleted right after the
response. `GET /api/health` proxies the llama.cpp `/health` probe for the
status pills. No shell is ever called with user input.

Environment knobs: `WEBUI_HOST` (default `127.0.0.1`), `WEBUI_PORT` (default
`8501`), `WEBUI_MAX_UPLOAD_BYTES` (default 25 MiB). PDF is offered only when
`pdf2image` + `pdftoppm` actually work on the host.

Browser tests (system Playwright, not a project dependency):

```bash
python3 webui/tests/ui_smoke.py        # 36 functional + layout checks
python3 webui/tests/ui_screenshots.py  # evidence screenshots
python3 webui/tests/ui_pdf_check.py    # multi-page PDF flow
python3 webui/tests/ui_error_state.py  # engine-down handling (stops/starts docker itself)
python3 webui/tests/ui_bbox_viewer.py  # bounding-box viewer (35 checks: exact coords, zoom, selection)
```

### Bounding-box viewer

After every OCR run the result section includes «بررسی بصری کادرها»: the page
image with the **real** engine coordinates drawn as an SVG overlay
(`viewBox` = engine image size, so boxes stay pixel-exact at any zoom).
Two layers: OCR blocks (blue, numbered) and detection lines from the real
`*_lines.json` (green, polygons when present; only `bboxes` are forwarded —
never the heatmap/affinity arrays). Click a box or a list row to see the
block's text/label/confidence/reading order and copy its text; invalid or
out-of-bounds coordinates raise a visible warning instead of being silently
corrected.



---

## Web UI (DocumentOCR)

A single-page Persian/RTL interface for non-technical users: drop a document,
press **شروع OCR**, read the extracted text, copy it, or download the TXT/JSON.

### Run it

```bash
./run_ui.sh                       # http://127.0.0.1:8501
WEBUI_PORT=8600 ./run_ui.sh       # custom port
```

`run_ui.sh` starts the llama.cpp container if it is not running, then serves
the UI. Nothing else is needed — no new Python dependency, no build step.

### How the UI talks to the OCR engine

```
browser ──POST /api/ocr──► webui/server.py (stdlib http.server)
                                 │  1. upload → .webui_tmp/<job-id>/
                                 │  2. PDF → pdf_utils.pdf_to_images (existing helper)
                                 │  3. SuryaDetection.detect()  ← the existing pipeline
                                 │  4. read back <stem>_ocr.json (the real engine output)
                                 ▼
                          llama.cpp  :8080  (Surya 2.5 GGUF)
```

* Same classes and logic as the CLI pipeline — `classes/detection.SuryaDetection`
  is imported directly; no OCR logic is re-implemented.
* One job at a time (`threading.Lock`) because llama.cpp runs with `--parallel 1`.
* Every job uses its own temp directory, deleted in a `finally` block
  (stale dirs older than 1 h are purged at startup).
* The engine badge in the header reflects a real probe of
  `http://127.0.0.1:8080/health` (polled every 8 s).

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | engine readiness, busy flag, supported formats, upload limit |
| `GET` | `/api/config` | upload limit + supported formats |
| `POST` | `/api/ocr` | run OCR on one uploaded document (image or PDF) |

`POST /api/ocr` sends the raw file body with an `X-Filename` header and
returns the real engine JSON per page:

```json
{"ok": true, "file": "page_1.png", "kind": "image", "page_count": 1,
 "elapsed_ms": 8135, "pages": [{"page": 1, "text": "…", "blocks": 37,
 "chars": 1115, "json": { …the real <stem>_ocr.json… }}]}
```

Errors are returned with a user-facing Persian `message` + `hint`
(`503 engine_unavailable`, `415 unsupported_type`, `422 unreadable_image`,
`422 no_text`, …). A blank result is never reported as success.

### UI tests (Playwright already installed on this host)

```bash
python3 webui/tests/ui_smoke.py        # 32 functional checks
python3 webui/tests/ui_screenshots.py  # curated evidence screenshots
python3 webui/tests/ui_pdf_check.py    # multi-page PDF
python3 webui/tests/ui_error_state.py  # engine-down error handling
```

Screenshots land in `docs/reports/2026-11-14_webui/screenshots/`.

### Web UI switches

| Env var | Default | Meaning |
|---|---|---|
| `WEBUI_HOST` | `127.0.0.1` | bind address |
| `WEBUI_PORT` | `8501` | UI port |
| `WEBUI_MAX_UPLOAD_BYTES` | `26214400` | upload limit (25 MB) |

The UI is static HTML/CSS/JS (`webui/static/`) with a local Vazirmatn font —
no CDN, no external request at runtime.
