/* =========================================================
   DocumentOCR — UI logic
   Talks to the local Python backend (webui/server.py) which
   runs the real Surya 2.5 + llama.cpp pipeline.
   ========================================================= */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    dropzone: $("dropzone"),
    fileInput: $("file-input"),
    fileCard: $("file-card"),
    fileName: $("file-name"),
    fileMeta: $("file-meta"),
    removeFile: $("remove-file"),
    runBtn: $("run-btn"),
    runLabel: $("run-label"),
    runSpinner: $("run-spinner"),
    errorBox: $("error-box"),
    errorTitle: $("error-title"),
    errorHint: $("error-hint"),
    dismissError: $("dismiss-error"),
    engineStatus: $("engine-status"),
    engineValue: $("engine-value"),
    jobStatus: $("job-status"),
    jobValue: $("job-value"),
    formatsChip: $("formats-chip"),
    dropMeta: $("drop-meta"),
    previewStage: $("preview-stage"),
    previewCanvas: $("preview-canvas"),
    previewImg: $("preview-img"),
    previewPdf: $("preview-pdf"),
    placeholder: $("preview-placeholder"),
    zoomControls: $("zoom-controls"),
    zoomIn: $("zoom-in"),
    zoomOut: $("zoom-out"),
    zoomFit: $("zoom-fit"),
    zoomLabel: $("zoom-label"),
    pageTabs: $("page-tabs"),
    result: $("result"),
    resultBadge: $("result-badge"),
    ocrText: $("ocr-text"),
    textMeta: $("text-meta"),
    stats: $("stats"),
    jsonView: $("json-view"),
    jsonCode: $("json-code"),
    copyText: $("copy-text"),
    downloadTxt: $("download-txt"),
    downloadOriginal: $("download-original"),
    copyJson: $("copy-json"),
    downloadJson: $("download-json"),
    toast: $("toast"),
    enhanceToggle: $("enhance-toggle"),
    refineToggle: $("refine-toggle"),
    refineWrap: $("refine-wrap"),
    bbControls: $("bb-controls"),
    bbShowBlocks: $("bb-show-blocks"),
    bbShowLines: $("bb-show-lines"),
    bbShowNums: $("bb-show-nums"),
    bbNumsWrap: $("bb-nums-wrap"),
    bbLinesWrap: $("bb-lines-wrap"),
    bbZoomIn: $("bb-zoom-in"),
    bbZoomOut: $("bb-zoom-out"),
    bbZoomFit: $("bb-zoom-fit"),
    bbZoomLabel: $("bb-zoom-label"),
    bbWarning: $("bb-warning"),
    bbStage: $("bb-stage"),
    bbCanvas: $("bb-canvas"),
    bbFrame: $("bb-frame"),
    bbImg: $("bb-img"),
    bbSvg: $("bb-svg"),
    bbPlaceholder: $("bb-placeholder"),
    bbCount: $("bb-count"),
    bbCopyText: $("bb-copy-text"),
    bbInfo: $("bb-info"),
    bbInfoLabel: $("bb-info-label"),
    bbInfoOrder: $("bb-info-order"),
    bbInfoConf: $("bb-info-conf"),
    bbInfoText: $("bb-info-text"),
    bbInfoBbox: $("bb-info-bbox"),
    bbList: $("bb-list"),
    saveResult: $("save-result"),
    savedList: $("saved-list"),
    savedCount: $("saved-count"),
    savedEmpty: $("saved-empty"),
  };

  const state = {
    file: null,
    objectUrl: null,
    busy: false,
    serverBusy: false,
    result: null,
    pageIndex: 0,
    zoom: 1,
    fitScale: 1,
    formats: ["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"],
    maxBytes: 25 * 1024 * 1024,
    pdf: false,
    bb: {
      zoom: 1,
      fitScale: 1,
      blocks: [],      // sorted by reading_order
      lines: [],
      linesValid: false,
      linesAvailable: false,
      imgSize: null,   // engine image size [W, H]
      sel: null,       // selected block index (null = none)
      dragged: false,
      showBlocks: true,
      showLines: true,
      showNums: true,
      expanded: {},   // table block index -> bool (fields shown)
      fsel: null,     // selected field {b: blockIndex, f: fieldIndex} | null
    },
  };

  /* ---------------- utilities ---------------- */

  const faNum = (n) => Number(n).toLocaleString("fa-IR");

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "—";
    const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    const rounded = unit === 0 ? Math.round(value) : Math.round(value * 10) / 10;
    return `${faNum(rounded)} ${units[unit]}`;
  }

  function formatDuration(ms) {
    if (ms == null) return "—";
    if (ms < 1000) return `${faNum(Math.round(ms))} میلی‌ثانیه`;
    const sec = ms / 1000;
    return `${faNum(Math.round(sec * 10) / 10)} ثانیه`;
  }

  let toastTimer = null;
  function toast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("is-visible"), 2600);
  }

  function showError(message, hint) {
    els.errorTitle.textContent = message || "خطایی رخ داد.";
    if (hint) {
      els.errorHint.textContent = hint;
      els.errorHint.hidden = false;
    } else {
      els.errorHint.hidden = true;
    }
    els.errorBox.hidden = false;
  }

  function clearError() {
    els.errorBox.hidden = true;
    els.errorTitle.textContent = "";
    els.errorHint.textContent = "";
    els.errorHint.hidden = true;
  }

  function setJobState(kind, text) {
    els.jobStatus.dataset.state = kind;
    els.jobValue.textContent = text;
  }

  function setEngineState(ready) {
    els.engineStatus.dataset.state = ready ? "ready" : "offline";
    els.engineValue.textContent = ready ? "آماده به کار" : "در دسترس نیست";
  }

  function setBusy(busy) {
    state.busy = busy;
    els.runBtn.disabled = busy || !state.file || !state.engineReady;
    els.runSpinner.hidden = !busy;
    els.runLabel.textContent = busy ? "در حال استخراج متن از سند…" : "شروع OCR";
    els.fileInput.disabled = busy;
    els.removeFile.disabled = busy;
    els.saveResult.disabled = busy || !state.result;
    els.runBtn.setAttribute("aria-busy", busy ? "true" : "false");
    if (busy) {
      setJobState("busy", "در حال پردازش");
    } else if (state.engineReady) {
      setJobState("idle", "آماده به کار");
    }
  }

  /* ---------------- health ---------------- */

  async function refreshHealth() {
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (!res.ok) throw new Error("health failed");
      const data = await res.json();

      state.engineReady = Boolean(data.engine && data.engine.ready);
      state.serverBusy = Boolean(data.busy);
      state.pdf = Boolean(data.pdf);
      state.maxBytes = data.max_upload_bytes || state.maxBytes;
      if (Array.isArray(data.formats) && data.formats.length) state.formats = data.formats;

      setEngineState(state.engineReady);
      applyFormatsHint();
      if (!state.busy) {
        els.runBtn.disabled = !state.file || !state.engineReady || state.serverBusy;
        if (state.serverBusy) setJobState("busy", "در حال پردازش");
        else setJobState("idle", "آماده به کار");
      }
      if (!state.engineReady) {
        showError(
          "سرویس OCR در دسترس نیست.",
          "سرور پردازش اجرا نشده است. با اجرای run_ocr.sh یا run_ui.sh دوباره تلاش کنید."
        );
      } else if (!state.serverBusy) {
        // only auto-clear engine errors, never a real job error
        if (els.errorTitle.textContent === "سرویس OCR در دسترس نیست.") clearError();
      }
    } catch (err) {
      setEngineState(false);
      els.runBtn.disabled = true;
    }
  }

  function applyFormatsHint() {
    const preferred = ["png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp", "pdf"];
    const ordered = preferred.filter((f) => state.formats.includes(f));
    state.formats
      .filter((f) => !preferred.includes(f))
      .forEach((f) => ordered.push(f));

    const labels = ordered.map((f) => f.toUpperCase());
    els.formatsChip.textContent = state.pdf ? "تصویر و PDF" : "تصویر";
    els.dropMeta.textContent =
      `${labels.join(" · ")} — حداکثر ${formatBytes(state.maxBytes)}`;
    els.fileInput.accept = state.formats.map((f) => "." + f).join(",");
  }

  /* ---------------- file selection ---------------- */

  function extensionOf(name) {
    const i = name.lastIndexOf(".");
    return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
  }

  function looksLikePdf(file) {
    return extensionOf(file.name) === "pdf" || file.type === "application/pdf";
  }

  function clearPreview() {
    if (state.objectUrl) {
      URL.revokeObjectURL(state.objectUrl);
      state.objectUrl = null;
    }
    els.previewImg.hidden = true;
    els.previewImg.removeAttribute("src");
    els.previewPdf.hidden = true;
    els.previewPdf.removeAttribute("src");
    els.previewCanvas.classList.remove("has-image");
    els.placeholder.hidden = false;
    els.zoomControls.hidden = true;
    els.pageTabs.hidden = true;
    els.pageTabs.innerHTML = "";
  }

  function selectFile(file) {
    clearError();
    if (!file) return;

    const ext = extensionOf(file.name);
    if (!state.formats.includes(ext)) {
      showError(
        "فرمت فایل پشتیبانی نمی‌شود.",
        `فرمت‌های مجاز: ${state.formats.map((f) => f.toUpperCase()).join("، ")}`
      );
      resetFile();
      return;
    }
    if (file.size > state.maxBytes) {
      showError(
        "حجم فایل بیشتر از حد مجاز است.",
        `حداکثر حجم مجاز ${formatBytes(state.maxBytes)} است.`
      );
      resetFile();
      return;
    }
    if (file.size === 0) {
      showError("فایل خالی است.", "یک فایل معتبر انتخاب کنید.");
      resetFile();
      return;
    }

    state.file = file;
    state.result = null;
    state.pageIndex = 0;
    state.zoom = 1;
    els.result.hidden = true;
    els.saveResult.disabled = true;

    els.fileCard.hidden = false;
    els.fileName.textContent = file.name;
    els.fileMeta.textContent = `${formatBytes(file.size)} · ${ext.toUpperCase()}`;
    els.dropzone.querySelector(".dropzone__title").textContent = "جایگزینی سند";
    els.dropzone.querySelector(".dropzone__sub").textContent = "فایل دیگری را رها یا انتخاب کنید";

    els.runBtn.disabled = !state.engineReady;
    renderPreview(file);
  }

  function resetFile() {
    state.file = null;
    state.result = null;
    els.saveResult.disabled = true;
    els.fileInput.value = "";
    els.fileCard.hidden = true;
    els.fileName.textContent = "";
    els.fileMeta.textContent = "";
    els.runBtn.disabled = true;
    els.dropzone.querySelector(".dropzone__title").textContent = "تصویر سند را اینجا رها کنید";
    els.dropzone.querySelector(".dropzone__sub").textContent = "یا برای انتخاب از کامپیوتر کلیک کنید";
    clearPreview();
    bbReset();
  }

  function renderPreview(file) {
    clearPreview();

    if (looksLikePdf(file)) {
      state.objectUrl = URL.createObjectURL(file);
      els.previewPdf.src = state.objectUrl;
      els.previewPdf.hidden = false;
      els.placeholder.hidden = true;
      els.zoomControls.hidden = true;
      return;
    }

    state.objectUrl = URL.createObjectURL(file);
    els.previewImg.onload = () => {
      els.previewImg.hidden = false;
      els.placeholder.hidden = true;
      els.zoomControls.hidden = false;
      state.zoom = 1;
      applyZoom();
    };
    els.previewImg.onerror = () => {
      showError("پیش‌نمایش تصویر ممکن نیست.", "ممکن است فایل خراب باشد.");
    };
    els.previewImg.src = state.objectUrl;
  }

  /* ---------------- zoom / pan ---------------- */

  function applyZoom() {
    const img = els.previewImg;
    if (!img || img.hidden || !img.naturalWidth) return;

    const stage = els.previewStage;
    const availW = Math.max(stage.clientWidth - 26, 80);
    const availH = Math.max(stage.clientHeight - 26, 80);
    const fit = Math.min(availW / img.naturalWidth, availH / img.naturalHeight);
    state.fitScale = fit;

    const width = Math.max(Math.round(img.naturalWidth * fit * state.zoom), 24);
    const height = Math.max(Math.round(img.naturalHeight * fit * state.zoom), 24);
    img.style.width = width + "px";
    img.style.height = height + "px";

    els.zoomLabel.textContent = `${faNum(Math.round(state.zoom * 100))}٪`;
    els.zoomFit.disabled = state.zoom === 1;
    els.zoomOut.disabled = state.zoom <= 0.5;
    els.zoomIn.disabled = state.zoom >= 4;
  }

  function setZoom(next) {
    state.zoom = Math.min(4, Math.max(0.5, Math.round(next * 100) / 100));
    applyZoom();
  }

  /* ---------------- OCR run ---------------- */

  async function runOCR() {
    if (!state.file || state.busy || !state.engineReady) return;

    clearError();
    setBusy(true);
    els.result.hidden = true;

    const started = performance.now();
    try {
      const enhance = els.enhanceToggle.checked ? "1" : "0";
      const refine = els.refineToggle && els.refineToggle.checked ? "1" : "0";
      const res = await fetch("/api/ocr?enhance=" + enhance + "&refine=" + refine, {
        method: "POST",
        headers: {
          "Content-Type": state.file.type || "application/octet-stream",
          "X-Filename": encodeURIComponent(state.file.name),
        },
        body: state.file,
      });

      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        throw { message: "پاسخ سرور قابل خواندن نبود.", hint: "لطفاً دوباره تلاش کنید." };
      }

      if (!res.ok || !data.ok) {
        throw {
          message: data.message || "پردازش سند ناموفق بود.",
          hint: data.hint || "",
        };
      }

      state.result = data;
      state.pageIndex = 0;
      els.saveResult.disabled = false;
      renderResult(data, Math.round(performance.now() - started));
      toast("متن سند با موفقیت استخراج شد.");
    } catch (err) {
      if (err && err.message) {
        showError(err.message, err.hint || "");
      } else {
        showError("ارتباط با سرویس OCR برقرار نشد.", "اتصال سرور را بررسی کنید.");
      }
      refreshHealth();
    } finally {
      setBusy(false);
    }
  }

  /* ---------------- result rendering ---------------- */

  function renderResult(data, clientMs) {
    els.result.hidden = false;

    const pages = data.pages || [];
    const page = pages[state.pageIndex] || pages[0];

    els.resultBadge.textContent =
      data.kind === "pdf" && pages.length > 1
        ? `${faNum(pages.length)} صفحه پردازش شد`
        : "پردازش با موفقیت انجام شد";

    renderStats(data, page, clientMs);
    renderPage(state.pageIndex);

    if (pages.length > 1) {
      els.pageTabs.hidden = false;
      els.pageTabs.innerHTML = "";
      pages.forEach((p, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "page-tab";
        btn.textContent = `صفحه ${faNum(p.page)}`;
        btn.setAttribute("aria-selected", i === state.pageIndex ? "true" : "false");
        btn.addEventListener("click", () => {
          state.pageIndex = i;
          els.pageTabs.querySelectorAll(".page-tab").forEach((b, bi) => {
            b.setAttribute("aria-selected", bi === i ? "true" : "false");
          });
          renderPage(i);
          renderStats(data, pages[i], clientMs);
        });
        els.pageTabs.appendChild(btn);
      });
    } else {
      els.pageTabs.hidden = true;
    }

    if (!state.busy) {
      setJobState("idle", "آماده به کار");
    }

    requestAnimationFrame(() => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      els.result.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    });
  }

  function renderPage(index) {
    const data = state.result;
    if (!data) return;
    const page = data.pages[index];
    if (!page) return;

    // text
    els.ocrText.innerHTML = "";
    const blocks = (page.json && page.json.blocks) || [];
    const pieces = [];
    blocks
      .slice()
      .sort((a, b) => (a.reading_order ?? 0) - (b.reading_order ?? 0))
      .forEach((block) => {
        const text = (block.text || "").trim();
        if (!text) return;
        const p = document.createElement("p");
        p.setAttribute("dir", "auto");
        p.textContent = text;
        els.ocrText.appendChild(p);
        pieces.push(text);
      });

    if (!pieces.length) {
      const p = document.createElement("p");
      p.className = "ocr-empty";
      p.textContent = page.text || "متنی برای نمایش وجود ندارد.";
      els.ocrText.appendChild(p);
      pieces.push(page.text || "");
    }

    els.textMeta.textContent = `${faNum(page.chars)} کاراکتر · ${faNum(page.blocks)} بلوک`;

    // json (real engine output, no synthetic data)
    els.jsonCode.innerHTML = highlightJson(page.json);

    // preview for PDF pages (browser cannot render PDF pages natively)
    if (page.preview) {
      els.previewPdf.hidden = true;
      els.previewImg.hidden = false;
      els.placeholder.hidden = true;
      els.zoomControls.hidden = false;
      if (state.objectUrl) {
        URL.revokeObjectURL(state.objectUrl);
        state.objectUrl = null;
      }
      state.zoom = 1;
      els.previewImg.onload = () => applyZoom();
      els.previewImg.src = page.preview;
    }

    bbRender(page);
  }

  function renderStats(data, page, clientMs) {
    const elapsed = data.elapsed_ms ?? clientMs;
    const items = [
      { label: "نام فایل", value: data.file },
      { label: "تعداد بلوک‌های استخراج‌شده", value: faNum(page.blocks) },
      { label: "تعداد کاراکترها", value: faNum(page.chars) },
      { label: "زمان پردازش", value: formatDuration(elapsed) },
      { label: "وضعیت عملیات", value: "موفق", ok: true },
    ];
    if ((data.pages || []).length > 1) {
      items.splice(1, 0, {
        label: "صفحه",
        value: `${faNum(page.page)} از ${faNum(data.pages.length)}`,
      });
    }

    els.stats.innerHTML = "";
    items.forEach((item) => {
      const el = document.createElement("div");
      el.className = "stat";

      const label = document.createElement("span");
      label.className = "stat__label";
      label.textContent = item.label;

      const value = document.createElement("span");
      value.className = "stat__value" + (item.ok ? " stat__value--ok" : "");
      value.textContent = item.value;
      value.setAttribute("dir", "auto");

      el.appendChild(label);
      el.appendChild(value);
      els.stats.appendChild(el);
    });
  }

  function highlightJson(obj) {
    let text;
    try {
      text = JSON.stringify(obj, null, 2);
    } catch (_) {
      return "";
    }
    const escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    return escaped.replace(
      /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      (match) => {
        let cls = "j-num";
        if (/^"/.test(match)) {
          cls = /:$/.test(match) ? "j-key" : "j-str";
        } else if (/^(true|false)$/.test(match)) {
          cls = "j-bool";
        } else if (match === "null") {
          cls = "j-null";
        }
        // values may mix Persian and Latin: isolate them so bidi keeps the
        // string readable inside the LTR JSON document
        const inner = cls === "j-str" ? `<bdi>${match}</bdi>` : match;
        return `<span class="${cls}">${inner}</span>`;
      }
    );
  }

  /* ---------------- copy / download ---------------- */

  async function copyToClipboard(text) {
    if (!text) return false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {
      /* fall through to legacy path */
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (_) {
      return false;
    }
  }

  function currentPage() {
    if (!state.result) return null;
    return state.result.pages[state.pageIndex] || state.result.pages[0] || null;
  }

  function baseName() {
    const name = state.file ? state.file.name : "document";
    const dot = name.lastIndexOf(".");
    return dot > 0 ? name.slice(0, dot) : name;
  }

  function download(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function pageSuffix() {
    const data = state.result;
    if (!data) return "";
    return (data.pages || []).length > 1 ? `_page${state.pageIndex + 1}` : "";
  }

  /* ---------------- bounding-box viewer ---------------- */

  const BB_SVG_NS = "http://www.w3.org/2000/svg";
  const bb = state.bb;

  function bbReset() {
    bb.zoom = 1;
    bb.fitScale = 1;
    bb.blocks = [];
    bb.lines = [];
    bb.linesValid = false;
    bb.linesAvailable = false;
    bb.imgSize = null;
    bb.sel = null;
    bb.frameW = 0;
    bb.frameH = 0;
    els.bbFrame.hidden = true;
    els.bbImg.removeAttribute("src");
    els.bbSvg.innerHTML = "";
    els.bbList.innerHTML = "";
    els.bbInfo.hidden = true;
    els.bbCopyText.disabled = true;
    els.bbCount.textContent = "—";
    els.bbWarning.hidden = true;
    els.bbPlaceholder.hidden = false;
    els.bbLinesWrap.hidden = true;
    els.bbNumsWrap.hidden = true;
    els.bbZoomLabel.textContent = `${faNum(100)}٪`;
    bb.expanded = {};
    bb.fsel = null;
  }

  function bbWarn(messages) {
    if (!messages.length) {
      els.bbWarning.hidden = true;
      return;
    }
    els.bbWarning.innerHTML = "";
    messages.forEach((m) => {
      const p = document.createElement("p");
      p.textContent = m;
      els.bbWarning.appendChild(p);
    });
    els.bbWarning.hidden = false;
  }

  // Fields shown in the UI: only entries that carry a real key. Keyless cells
  // (empty boxes, previously rendered as «مقدار بدون عنوان») hold no label and
  // are hidden per user request. The JSON payload keeps every field untouched.
  // A field is displayed only when it is COMPLETE: real key AND real value.
  // Key-only («شماره ملی:» with nothing read) and keyless fragments are hidden.
  function bbDisplayFields(b) {
    const all = Array.isArray(b && b.fields) ? b.fields : [];
    const out = [];
    all.forEach((f, fi) => {
      const key = f && f.key ? String(f.key).trim() : "";
      const value = f && f.value ? String(f.value).trim() : "";
      if (!key || !value) return; // incomplete -> empty box -> not displayed
      out.push({ f: f, fi: fi, key: key, value: value });
    });
    return out;
  }

  // Display ordinal (1..n over displayed fields) of a field with original index.
  function bbDisplayOrdinal(bIdx, fIdx) {
    const b = bb.blocks[bIdx];
    if (!b) return fIdx + 1;
    const disp = bbDisplayFields(b);
    const pos = disp.findIndex((x) => x.fi === fIdx);
    return pos >= 0 ? pos + 1 : fIdx + 1;
  }

  function bbRender(page) {
    const j = page.json || {};
    const blocks = (j.blocks || [])
      .slice()
      .sort((a, b) => (a.reading_order ?? 0) - (b.reading_order ?? 0));
    bb.blocks = blocks;
    bb.imgSize = Array.isArray(page.image_size) ? page.image_size.slice() : null;
    bb.sel = null;

    const layers = page.layers || {};
    bb.lines = layers.lines || [];
    bb.linesAvailable = Boolean(layers.available) && bb.lines.length > 0;
    bb.linesValid = Boolean(layers.valid);

    // show/hide optional controls based on the real data
    els.bbLinesWrap.hidden = !bb.linesAvailable;
    if (bb.linesAvailable) els.bbShowLines.checked = bb.showLines;
    els.bbNumsWrap.hidden = blocks.length === 0;

    // warnings — never silently fix coordinates (mission req. 6.7)
    const warns = [];
    if (!page.blocks_valid) {
      warns.push("هشدار: برخی مختصات بلوک‌های OCR خارج از محدودهٔ تصویر است و ممکن است دقیق نباشد.");
    }
    if (bb.linesAvailable && !bb.linesValid) {
      warns.push("هشدار: مختصات خطوط Detection با ابعاد تصویر سازگار نیست؛ لایهٔ خطوط قابل اعتماد نیست.");
    }
    if (layers.truncated) {
      warns.push(`تعداد خطوط بیش از حد مجاز است؛ فقط ${faNum(bb.lines.length)} خط از ${faNum(layers.total)} نمایش داده می‌شود.`);
    }
    bbWarn(warns);

    // image source: original upload for images, engine-side JPEG for PDF pages
    const src = page.preview || state.objectUrl;
    els.bbImg.hidden = false;
    els.bbImg.onload = () => {
      bbValidateAspect();
      bbApplyZoom();
      bbDraw();
    };
    if (src) {
      if (els.bbImg.src === src) {
        bbValidateAspect();
        bbApplyZoom();
        bbDraw();
      } else {
        els.bbImg.src = src;
      }
    } else {
      bbValidateAspect();
      bbApplyZoom();
      bbDraw();
    }
    els.bbFrame.hidden = false;
    els.bbPlaceholder.hidden = true;

    // list
    els.bbList.innerHTML = "";
    blocks.forEach((b, i) => {
      const row = document.createElement("div");
      row.className = "bb-row";
      row.setAttribute("role", "option");
      row.dataset.index = String(i);
      const dispFields = bbDisplayFields(b);
      const hasFields = dispFields.length > 0;
      if (hasFields) row.classList.add("bb-row--table");

      const num = document.createElement("span");
      num.className = "bb-row__num";
      num.textContent = faNum(i + 1);

      const body = document.createElement("span");
      body.className = "bb-row__body";

      const label = document.createElement("span");
      label.className = "bb-row__label";
      label.textContent = b.label || "Block";
      if (b.confidence != null) {
        const conf = document.createElement("span");
        conf.textContent = `اطمینان ${faNum(Math.round(b.confidence * 100))}٪`;
        label.appendChild(conf);
      }
      if (hasFields) {
        const chip = document.createElement("span");
        chip.className = "bb-row__fields-chip";
        chip.textContent = `${faNum(dispFields.length)} فیلد`;
        label.appendChild(chip);
      }

      const text = document.createElement("span");
      text.className = "bb-row__text";
      text.textContent = (b.text || "").trim() || "—";
      text.setAttribute("dir", "auto");

      body.appendChild(label);
      body.appendChild(text);
      row.appendChild(num);
      row.appendChild(body);

      if (hasFields) {
        const chev = document.createElement("button");
        chev.type = "button";
        chev.className = "icon-btn icon-btn--sm bb-row__chev";
        chev.setAttribute("aria-label", `نمایش یا پنهان‌سازی ${faNum(dispFields.length)} فیلد جدول`);
        chev.setAttribute("aria-expanded", bb.expanded[i] ? "true" : "false");
        chev.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
        chev.addEventListener("click", (e) => {
          e.stopPropagation();
          bbToggleExpand(i);
        });
        row.appendChild(chev);
      }

      row.addEventListener("click", () => bbSelect(i, { scroll: true }));
      row.addEventListener("mouseenter", () => bbHover(i, true));
      row.addEventListener("mouseleave", () => bbHover(i, false));
      els.bbList.appendChild(row);

      if (hasFields) {
        dispFields.forEach((d, pos) => {
          const f = d.f;
          const fi = d.fi;
          const child = document.createElement("div");
          child.className = "bb-row bb-row--child" + (bb.expanded[i] ? " is-open" : "");
          child.setAttribute("role", "option");
          child.dataset.block = String(i);
          child.dataset.field = String(fi);

          const cnum = document.createElement("span");
          cnum.className = "bb-row__num bb-row__num--field";
          cnum.textContent = faNum(pos + 1);

          const cbody = document.createElement("span");
          cbody.className = "bb-row__body";
          const ckey = document.createElement("span");
          ckey.className = "bb-row__fkey";
          ckey.textContent = d.key;
          ckey.setAttribute("dir", "auto");
          const cval = document.createElement("span");
          cval.className = "bb-row__fval";
          cval.textContent = d.value ? `${d.key}: ${d.value}` : `${d.key}: —`;
          cval.setAttribute("dir", "auto");
          const cmeta = document.createElement("span");
          cmeta.className = "bb-row__fmeta";
          const geom = f.bbox ? "مختصات: خط واقعی" : "بدون مختصات معتبر";
          const bits = [];
          if (f.confidence != null) bits.push(`اطمینان ${faNum(Math.round(f.confidence * 100))}٪`);
          if (!d.value) bits.push("بدون مقدار");
          bits.push(geom);
          cmeta.textContent = bits.join(" · ");
          if (!d.value) cmeta.classList.add("bb-row__fmeta--novalue");
          if (!f.bbox) cmeta.classList.add("bb-row__fmeta--none");
          cbody.appendChild(ckey);
          cbody.appendChild(cval);
          cbody.appendChild(cmeta);

          child.appendChild(cnum);
          child.appendChild(cbody);
          child.addEventListener("click", (e) => {
            e.stopPropagation();
            bbSelectField(i, fi, { scroll: true });
          });
          els.bbList.appendChild(child);
        });
      }
    });
    els.bbCount.textContent = `${faNum(blocks.length)} بلوک`;
    bbUpdateInfo();
  }

  function bbToggleExpand(i) {
    bb.expanded[i] = !bb.expanded[i];
    const chev = els.bbList.querySelector(`.bb-row[data-index="${i}"] .bb-row__chev`);
    if (chev) {
      chev.classList.toggle("is-open", !!bb.expanded[i]);
      chev.setAttribute("aria-expanded", bb.expanded[i] ? "true" : "false");
    }
    els.bbList.querySelectorAll(`.bb-row--child[data-block="${i}"]`).forEach((c) => {
      c.classList.toggle("is-open", !!bb.expanded[i]);
    });
    bbDraw();
  }

  function bbValidateAspect() {
    if (!bb.imgSize || !els.bbImg.naturalWidth) return;
    const natAr = els.bbImg.naturalWidth / els.bbImg.naturalHeight;
    const engAr = bb.imgSize[0] / bb.imgSize[1];
    if (Math.abs(natAr - engAr) / engAr > 0.02) {
      bbWarn([
        "هشدار: نسبت ابعاد تصویر نمایش‌داده‌شده با ابعاد گزارش‌شدهٔ موتور OCR هم‌خوانی ندارد. موقعیت کادرها ممکن است دقیق نباشد.",
        ...(els.bbWarning.hidden ? [] : Array.from(els.bbWarning.children).map((c) => c.textContent)),
      ]);
    }
  }

  function bbEngineSize() {
    // viewBox = real engine image space (server-reported)
    return bb.imgSize || [els.bbImg.naturalWidth || 1, els.bbImg.naturalHeight || 1];
  }

  function bbApplyZoom() {
    if (els.bbImg.hidden || !els.bbImg.naturalWidth) return;
    const stage = els.bbStage;
    // Reserve fixed scrollbar space: frame size must never depend on whether a
    // scrollbar happens to be visible (appear/disappear -> stage.clientWidth
    // oscillates -> endless resize = the viewer flicker after opening a file).
    const SB = 16;
    const availW = Math.max(stage.clientWidth - SB - 26, 80);
    const availH = Math.max(stage.clientHeight - SB - 26, 80);
    const fit = Math.min(availW / els.bbImg.naturalWidth, availH / els.bbImg.naturalHeight);
    bb.fitScale = fit;
    const newW = Math.max(Math.round(els.bbImg.naturalWidth * fit * bb.zoom), 24);
    const newH = Math.max(Math.round(els.bbImg.naturalHeight * fit * bb.zoom), 24);
    if (els.bbFrame.style.width === newW + "px" && els.bbFrame.style.height === newH + "px") {
      return; // no visual change -> break the feedback loop
    }
    bb.frameW = newW;
    bb.frameH = newH;
    els.bbFrame.style.width = bb.frameW + "px";
    els.bbFrame.style.height = bb.frameH + "px";

    els.bbZoomLabel.textContent = `${faNum(Math.round(bb.zoom * 100))}٪`;
    els.bbZoomFit.disabled = bb.zoom === 1;
    els.bbZoomOut.disabled = bb.zoom <= 0.5;
    els.bbZoomIn.disabled = bb.zoom >= 4;

    // numbers: keep ~13px on screen regardless of zoom
    const [ew] = bbEngineSize();
    const scale = bb.frameW / ew;
    els.bbSvg.querySelectorAll(".bb-num").forEach((t) => {
      t.setAttribute("font-size", String(Math.max(13 / scale, 2)));
    });
  }

  function setBbZoom(next) {
    bb.zoom = Math.min(4, Math.max(0.5, Math.round(next * 100) / 100));
    bbApplyZoom();
  }

  function bbDraw() {
    const [ew, eh] = bbEngineSize();
    els.bbSvg.setAttribute("viewBox", `0 0 ${ew} ${eh}`);
    els.bbSvg.setAttribute("preserveAspectRatio", "none");
    const frag = document.createDocumentFragment();

    if (bb.showLines && bb.linesAvailable) {
      bb.lines.forEach((ln) => {
        let shape;
        if (ln.polygon && ln.polygon.length >= 3) {
          shape = document.createElementNS(BB_SVG_NS, "polygon");
          shape.setAttribute("points", ln.polygon.map((p) => p.join(",")).join(" "));
          shape.setAttribute("class", "bb-poly");
        } else {
          shape = document.createElementNS(BB_SVG_NS, "rect");
          const [x1, y1, x2, y2] = ln.bbox;
          shape.setAttribute("x", String(Math.min(x1, x2)));
          shape.setAttribute("y", String(Math.min(y1, y2)));
          shape.setAttribute("width", String(Math.abs(x2 - x1)));
          shape.setAttribute("height", String(Math.abs(y2 - y1)));
          shape.setAttribute("class", "bb-line");
        }
        frag.appendChild(shape);
      });
    }

    if (bb.showBlocks) {
      bb.blocks.forEach((b, i) => {
        const [x1, y1, x2, y2] = b.bbox || [];
        if (![x1, y1, x2, y2].every((v) => typeof v === "number" && isFinite(v))) return;
        const rx = Math.min(x1, x2);
        const ry = Math.min(y1, y2);
        const rw = Math.abs(x2 - x1);
        const rh = Math.abs(y2 - y1);
        const rect = document.createElementNS(BB_SVG_NS, "rect");
        rect.setAttribute("x", String(rx));
        rect.setAttribute("y", String(ry));
        rect.setAttribute("width", String(rw));
        rect.setAttribute("height", String(rh));
        rect.setAttribute("class", "bb-shape" + ((Array.isArray(b.fields) && b.fields.length) ? " bb-shape--table" : ""));
        rect.dataset.index = String(i);
        if (i === bb.sel) rect.classList.add("is-selected");
        frag.appendChild(rect);

        // inner field boxes (only while the table row is expanded)
        const dispFields = bbDisplayFields(b);
        if (bb.expanded[i] && dispFields.length) {
          dispFields.forEach((d, pos) => {
            const f = d.f;
            const fi = d.fi;
            const [fx1, fy1, fx2, fy2] = f.bbox || [];
            if (![fx1, fy1, fx2, fy2].every((v) => typeof v === "number" && isFinite(v))) return;
            const frx = Math.min(fx1, fx2), fry = Math.min(fy1, fy2);
            const frw = Math.abs(fx2 - fx1), frh = Math.abs(fy2 - fy1);
            const frect = document.createElementNS(BB_SVG_NS, "rect");
            frect.setAttribute("x", String(frx));
            frect.setAttribute("y", String(fry));
            frect.setAttribute("width", String(frw));
            frect.setAttribute("height", String(frh));
            frect.setAttribute("class", "bb-field");
            frect.dataset.block = String(i);
            frect.dataset.field = String(fi);
            if (bb.fsel && bb.fsel.b === i && bb.fsel.f === fi) frect.classList.add("is-selected");
            frag.appendChild(frect);

            if (bb.showNums) {
              const [ew2] = bbEngineSize();
              const scale = (bb.frameW || 1) / ew2;
              const fs = Math.max(13 / scale, 2);
              const t = document.createElementNS(BB_SVG_NS, "text");
              t.setAttribute("x", String(frx + frw - fs * 0.35));
              t.setAttribute("y", String(fry > fs * 1.5 ? fry - fs * 0.35 : fry + fs * 1.1));
              t.setAttribute("text-anchor", "end");
              t.setAttribute("font-size", String(fs));
              t.setAttribute("class", "bb-num bb-num--field");
              t.textContent = String(pos + 1);
              frag.appendChild(t);
            }
          });
        }

        if (bb.showNums) {
          const [ew2] = bbEngineSize();
          const scale = (bb.frameW || 1) / ew2;
          const fs = Math.max(13 / scale, 2);
          const t = document.createElementNS(BB_SVG_NS, "text");
          t.setAttribute("x", String(rx + rw - fs * 0.35));
          t.setAttribute("y", String(ry > fs * 1.5 ? ry - fs * 0.35 : ry + fs * 1.1));
          t.setAttribute("text-anchor", "end");
          t.setAttribute("font-size", String(fs));
          t.setAttribute("class", "bb-num");
          t.textContent = String(i + 1);
          frag.appendChild(t);
        }
      });
    }

    els.bbSvg.innerHTML = "";
    els.bbSvg.appendChild(frag);
  }

  function bbHover(index, on) {
    const rect = els.bbSvg.querySelector(`.bb-shape[data-index="${index}"]`);
    if (rect) rect.classList.toggle("is-hover", on);
    const row = els.bbList.querySelector(`.bb-row[data-index="${index}"]`);
    if (row) row.classList.toggle("is-hover", on);
  }

  function bbSelect(index, opts = {}) {
    bb.sel = index;
    bb.fsel = null;
    els.bbSvg.querySelectorAll(".bb-shape").forEach((r) => {
      r.classList.toggle("is-selected", Number(r.dataset.index) === index);
    });
    els.bbSvg.querySelectorAll(".bb-field.is-selected").forEach((r) => r.classList.remove("is-selected"));
    els.bbList.querySelectorAll(".bb-row").forEach((r) => {
      const isBlock = r.dataset.index != null;
      r.classList.toggle("is-active", isBlock && Number(r.dataset.index) === index);
      r.classList.remove("has-active-child"); // field selection cleared
    });
    bbUpdateInfo();
    if (index != null && opts.scroll) {
      const b = bb.blocks[index];
      const rect = els.bbSvg.querySelector(`.bb-shape[data-index="${index}"]`);
      if (b && rect) {
        const [ew, eh] = bbEngineSize();
        const sx = bb.frameW / ew;
        const sy = bb.frameH / eh;
        const cx = ((b.bbox[0] + b.bbox[2]) / 2) * sx;
        const cy = ((b.bbox[1] + b.bbox[3]) / 2) * sy;
        const stage = els.bbStage;
        const targetL = cx - stage.clientWidth / 2;
        const targetT = cy - stage.clientHeight / 2;
        const frameL = els.bbFrame.offsetLeft;
        const frameT = els.bbFrame.offsetTop;
        stage.scrollTo({
          left: Math.max(0, frameL + targetL - els.bbCanvas.clientLeft),
          top: Math.max(0, frameT + targetT - els.bbCanvas.clientTop),
          behavior: "smooth",
        });
      }
    }
  }

  function bbSelectField(bIdx, fIdx, opts = {}) {
    bb.fsel = { b: bIdx, f: fIdx };
    bb.sel = null;
    els.bbSvg.querySelectorAll(".bb-shape.is-selected").forEach((r) => r.classList.remove("is-selected"));
    els.bbSvg.querySelectorAll(".bb-field").forEach((r) => {
      r.classList.toggle("is-selected",
        Number(r.dataset.block) === bIdx && Number(r.dataset.field) === fIdx);
    });
    els.bbList.querySelectorAll(".bb-row").forEach((r) => {
      const isChild = r.dataset.field != null;
      r.classList.toggle("is-active",
        isChild && Number(r.dataset.block) === bIdx && Number(r.dataset.field) === fIdx);
    });
    // highlight parent table row when a child field is selected (so user knows which table)
    els.bbList.querySelectorAll(".bb-row").forEach((r) => {
      r.classList.toggle("has-active-child",
        Number(r.dataset.index) === bIdx && r.classList.contains("bb-row--table"));
    });
    bbUpdateInfo();
    if (opts.scroll) {
      const child = els.bbList.querySelector(`.bb-row--child[data-block="${bIdx}"][data-field="${fIdx}"]`);
      if (child) child.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function bbUpdateInfo() {
    if (bb.fsel && bb.blocks[bb.fsel.b] && (bb.blocks[bb.fsel.b].fields || [])[bb.fsel.f]) {
      const f = bb.blocks[bb.fsel.b].fields[bb.fsel.f];
      els.bbInfo.hidden = false;
      els.bbInfoLabel.textContent = `فیلد ${faNum(bbDisplayOrdinal(bb.fsel.b, bb.fsel.f))} · ${f.key || "مقدار"}`;
      els.bbInfoOrder.textContent = `جدول: ${faNum(bb.fsel.b + 1)}`;
      els.bbInfoConf.textContent =
        f.confidence != null ? `اطمینان: ${faNum(Math.round(f.confidence * 100))}٪` : "";
      els.bbInfoText.textContent =
        f.value ? `${f.key ? f.key + ": " : ""}${f.value}` : (f.key ? f.key + ":" : "—");
      els.bbInfoBbox.textContent = f.bbox
        ? `bbox: [${f.bbox.map((v) => Number(v).toFixed(1)).join(", ")}]`
        : "بدون مختصات معتبر — هیچ کادر ساختگی ساخته نشده است";
      els.bbCopyText.disabled = !f.value;
      return;
    }
    if (bb.sel == null || !bb.blocks[bb.sel]) {
      els.bbInfo.hidden = true;
      els.bbCopyText.disabled = true;
      return;
    }
    const b = bb.blocks[bb.sel];
    els.bbInfo.hidden = false;
    els.bbInfoLabel.textContent = `${faNum(bb.sel + 1)} · ${b.label || "Block"}`;
    els.bbInfoOrder.textContent = `ترتیب خواندن: ${faNum((b.reading_order ?? 0) + 1)}`;
    els.bbInfoConf.textContent =
      b.confidence != null ? `اطمینان: ${faNum(Math.round(b.confidence * 100))}٪` : "";
    // hierarchy: a Table shows its fields (Key/Value list), not flat text
    const disp = bbDisplayFields(b);
    const totalF = Array.isArray(b.fields) ? b.fields.length : 0;
    els.bbInfoText.textContent = "";
    if (disp.length) {
      const wrap = document.createElement("span");
      wrap.className = "bb-info__fields";
      disp.forEach((d) => {
        const row = document.createElement("span");
        row.className = "bb-info__field";
        row.setAttribute("dir", "auto");
        const k = document.createElement("b");
        k.textContent = `${d.key}: `;
        const v = document.createElement("span");
        v.textContent = d.value;
        row.appendChild(k);
        row.appendChild(v);
        wrap.appendChild(row);
      });
      const hiddenN = totalF - disp.length;
      if (hiddenN > 0) {
        const more = document.createElement("span");
        more.className = "bb-info__more";
        more.textContent = `+ ${faNum(hiddenN)} فیلد ناقص (بدون مقدار یا عنوان) — در JSON موجود است`;
        wrap.appendChild(more);
      }
      els.bbInfoText.appendChild(wrap);
    } else if (totalF) {
      const more = document.createElement("span");
      more.className = "bb-info__more";
      more.textContent = `${faNum(totalF)} فیلد ناقص (بدون مقدار یا عنوان) — در JSON موجود است`;
      els.bbInfoText.appendChild(more);
    } else {
      els.bbInfoText.textContent = (b.text || "").trim() || "—";
    }
    const [x1, y1, x2, y2] = b.bbox || [];
    els.bbInfoBbox.textContent =
      typeof x1 === "number" ? `bbox: [${x1.toFixed(1)}, ${y1.toFixed(1)}, ${x2.toFixed(1)}, ${y2.toFixed(1)}]` : "";
    els.bbCopyText.disabled = !(b.text || "").trim();
  }

  els.bbShowBlocks.addEventListener("change", () => {
    bb.showBlocks = els.bbShowBlocks.checked;
    bbDraw();
  });
  els.bbShowLines.addEventListener("change", () => {
    bb.showLines = els.bbShowLines.checked;
    if (bb.showLines && !bb.linesValid && bb.linesAvailable) {
      toast("مختصات خطوط با ابعاد تصویر سازگار نیست.");
    }
    bbDraw();
  });
  els.bbShowNums.addEventListener("change", () => {
    bb.showNums = els.bbShowNums.checked;
    bbDraw();
  });
  els.bbZoomIn.addEventListener("click", () => setBbZoom(bb.zoom + 0.25));
  els.bbZoomOut.addEventListener("click", () => setBbZoom(bb.zoom - 0.25));
  els.bbZoomFit.addEventListener("click", () => setBbZoom(1));

  // click selection on the overlay (ignore clicks that were pan drags)
  els.bbSvg.addEventListener("click", (e) => {
    if (bb.dragged) return;
    const field = e.target.closest(".bb-field");
    if (field) {
      bbSelectField(Number(field.dataset.block), Number(field.dataset.field));
      return;
    }
    const shape = e.target.closest(".bb-shape");
    if (shape) {
      bbSelect(Number(shape.dataset.index));
    } else if (e.target === els.bbSvg || e.target === els.bbImg) {
      bbSelect(null);
    }
  });
  els.bbSvg.addEventListener("mouseover", (e) => {
    const field = e.target.closest(".bb-field");
    if (field) {
      field.classList.add("is-hover");
      const child = els.bbList.querySelector(`.bb-row--child[data-block="${field.dataset.block}"][data-field="${field.dataset.field}"]`);
      if (child) child.classList.add("is-hover");
      return;
    }
    const shape = e.target.closest(".bb-shape");
    if (shape) bbHover(Number(shape.dataset.index), true);
  });
  els.bbSvg.addEventListener("mouseout", (e) => {
    const field = e.target.closest(".bb-field");
    if (field) {
      field.classList.remove("is-hover");
      const child = els.bbList.querySelector(`.bb-row--child[data-block="${field.dataset.block}"][data-field="${field.dataset.field}"]`);
      if (child) child.classList.remove("is-hover");
      return;
    }
    const shape = e.target.closest(".bb-shape");
    if (shape) bbHover(Number(shape.dataset.index), false);
  });

  els.bbCopyText.addEventListener("click", async () => {
    if (bb.sel == null || !bb.blocks[bb.sel]) return;
    const ok = await copyToClipboard((bb.blocks[bb.sel].text || "").trim());
    toast(ok ? "متن بلوک در کلیپ‌بورد کپی شد." : "کپی ممکن نشد.");
  });

  // pan inside the viewer when zoomed
  let bbPan = null;
  els.bbStage.addEventListener("pointerdown", (e) => {
    const stageBox = els.bbStage.getBoundingClientRect();
    const frameBox = els.bbFrame.getBoundingClientRect();
    if (frameBox.width <= stageBox.width && frameBox.height <= stageBox.height) return;
    bbPan = { x: e.clientX, y: e.clientY, left: els.bbStage.scrollLeft, top: els.bbStage.scrollTop };
    bb.dragged = false;
    els.bbStage.setAttribute("dragging", "");
    els.bbStage.setPointerCapture(e.pointerId);
  });
  els.bbStage.addEventListener("pointermove", (e) => {
    if (!bbPan) return;
    const dx = e.clientX - bbPan.x;
    const dy = e.clientY - bbPan.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) bb.dragged = true;
    els.bbStage.scrollLeft = bbPan.left - dx;
    els.bbStage.scrollTop = bbPan.top - dy;
  });
  ["pointerup", "pointercancel"].forEach((type) => {
    els.bbStage.addEventListener(type, () => {
      bbPan = null;
      setTimeout(() => { bb.dragged = false; }, 0);
      els.bbStage.removeAttribute("dragging");
    });
  });
  els.bbStage.addEventListener(
    "wheel",
    (e) => {
      if (!els.bbFrame.hidden && e.ctrlKey) {
        e.preventDefault();
        setBbZoom(bb.zoom + (e.deltaY < 0 ? 0.15 : -0.15));
      }
    },
    { passive: false }
  );
  if ("ResizeObserver" in window) {
    let bbResizeRaf = 0;
    const roBb = new ResizeObserver(() => {
      if (bbResizeRaf) return;
      bbResizeRaf = requestAnimationFrame(() => {
        bbResizeRaf = 0;
        bbApplyZoom();
      });
    });
    roBb.observe(els.bbStage);
  }

  /* ---------------- saved results (persistent) ---------------- */

  const faDateTime = (iso) => {
    try {
      return new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", timeStyle: "short" })
        .format(new Date(iso));
    } catch (_) {
      return iso || "—";
    }
  };

  // Downscaled JPEG preview for image uploads (mirrors the server's PDF preview).
  function imagePreviewDataUrl(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        try {
          const maxSide = 1500;
          const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(Math.round(img.naturalWidth * scale), 1);
          canvas.height = Math.max(Math.round(img.naturalHeight * scale), 1);
          canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/jpeg", 0.85));
        } catch (err) {
          reject(err);
        } finally {
          URL.revokeObjectURL(url);
        }
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("preview failed"));
      };
      img.src = url;
    });
  }

  async function buildSavePayload() {
    const data = state.result;
    if (!data) return null;
    const payload = {
      ok: true,
      file: data.file,
      kind: data.kind,
      page_count: data.page_count,
      elapsed_ms: data.elapsed_ms,
      pipeline_ms: data.pipeline_ms,
      pages: [],
    };
    for (const page of data.pages || []) {
      const entry = { ...page };
      if (!entry.preview && state.file && !looksLikePdf(state.file)) {
        entry.preview = await imagePreviewDataUrl(state.file);
      }
      payload.pages.push(entry);
    }
    return payload;
  }

  async function saveResult() {
    if (!state.result || state.busy || els.saveResult.disabled) return;
    els.saveResult.disabled = true;
    try {
      const payload = await buildSavePayload();
      const res = await fetch("/api/saved", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data || !data.ok) {
        throw { message: (data && data.message) || "ذخیرهٔ نتیجه ناموفق بود.", hint: (data && data.hint) || "" };
      }
      toast("نتیجه در فهرست نتایج ذخیره‌شده ذخیره شد.");
      await refreshSaved();
    } catch (err) {
      if (err && err.message) showError(err.message, err.hint || "");
      else showError("ذخیرهٔ نتیجه ناموفق بود.", "اتصال سرور را بررسی کنید.");
    } finally {
      els.saveResult.disabled = !state.result || state.busy;
    }
  }

  async function refreshSaved() {
    try {
      const res = await fetch("/api/saved", { cache: "no-store" });
      const data = await res.json();
      const items = (data && data.ok && Array.isArray(data.items)) ? data.items : [];
      renderSavedList(items);
    } catch (_) {
      /* list is non-critical; leave the current view as-is */
    }
  }

  function renderSavedList(items) {
    els.savedList.innerHTML = "";
    els.savedCount.textContent = faNum(items.length);
    els.savedEmpty.hidden = items.length > 0;
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "saved-row";
      row.setAttribute("role", "button");
      row.tabIndex = 0;
      row.dataset.id = item.id;

      const body = document.createElement("span");
      body.className = "saved-row__body";
      const name = document.createElement("span");
      name.className = "saved-row__name";
      name.textContent = item.name || "document";
      name.setAttribute("dir", "auto");
      const meta = document.createElement("span");
      meta.className = "saved-row__meta";
      const parts = [faDateTime(item.created_at), `${faNum(item.chars)} کاراکتر`];
      if ((item.page_count || 1) > 1) parts.push(`${faNum(item.page_count)} صفحه`);
      meta.textContent = parts.join(" · ");
      body.appendChild(name);
      body.appendChild(meta);

      const del = document.createElement("button");
      del.type = "button";
      del.className = "icon-btn icon-btn--sm saved-row__del";
      del.setAttribute("aria-label", `حذف ${item.name || "نتیجهٔ ذخیره‌شده"}`);
      del.title = "حذف";
      del.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13"/></svg>';

      const open = () => loadSaved(item.id);
      row.addEventListener("click", open);
      row.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      });
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteSaved(item.id);
      });

      row.appendChild(body);
      row.appendChild(del);
      els.savedList.appendChild(row);
    });
  }

  async function loadSaved(id) {
    if (state.busy) return;
    try {
      const res = await fetch(`/api/saved/${id}`, { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || !data || !data.ok) {
        throw { message: (data && data.message) || "بازیابی نتیجه ناموفق بود." };
      }
      state.result = data;
      state.pageIndex = 0;
      els.saveResult.disabled = false;
      renderResult(data, data.elapsed_ms ?? 0);
      if (data.saved) toast(`نتیجهٔ ذخیره‌شدهٔ «${data.file || "document"}» بازیابی شد.`);
    } catch (err) {
      if (err && err.message) showError(err.message, err.hint || "");
      else showError("بازیابی نتیجه ناموفق بود.", "اتصال سرور را بررسی کنید.");
      refreshSaved();
    }
  }

  async function deleteSaved(id) {
    try {
      const res = await fetch(`/api/saved/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok || !data || !data.ok) {
        throw { message: (data && data.message) || "حذف ناموفق بود." };
      }
      toast("نتیجهٔ ذخیره‌شده حذف شد.");
    } catch (err) {
      toast((err && err.message) || "حذف ناموفق بود.");
    }
    refreshSaved();
  }

  els.saveResult.addEventListener("click", saveResult);

  /* ---------------- events ---------------- */

  els.dropzone.addEventListener("click", () => {
    if (!state.busy) els.fileInput.click();
  });

  els.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!state.busy) els.fileInput.click();
    }
  });

  els.fileInput.addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) selectFile(file);
  });

  ["dragenter", "dragover"].forEach((type) => {
    els.dropzone.addEventListener(type, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!state.busy) els.dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend"].forEach((type) => {
    els.dropzone.addEventListener(type, (e) => {
      e.preventDefault();
      els.dropzone.classList.remove("is-dragover");
    });
  });

  els.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    els.dropzone.classList.remove("is-dragover");
    if (state.busy) return;
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) selectFile(file);
  });

  // page-level drop safety net (avoid the browser opening the file)
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());

  els.removeFile.addEventListener("click", () => {
    if (state.busy) return;
    resetFile();
    clearError();
  });

  els.runBtn.addEventListener("click", runOCR);
  els.dismissError.addEventListener("click", clearError);

  els.zoomIn.addEventListener("click", () => setZoom(state.zoom + 0.25));
  els.zoomOut.addEventListener("click", () => setZoom(state.zoom - 0.25));
  els.zoomFit.addEventListener("click", () => setZoom(1));

  els.previewStage.addEventListener(
    "wheel",
    (e) => {
      if (!els.previewImg.hidden && e.ctrlKey) {
        e.preventDefault();
        setZoom(state.zoom + (e.deltaY < 0 ? 0.15 : -0.15));
      }
    },
    { passive: false }
  );

  // drag to pan when zoomed in
  let pan = null;
  els.previewStage.addEventListener("pointerdown", (e) => {
    if (els.previewImg.hidden || state.zoom <= 1) return;
    pan = { x: e.clientX, y: e.clientY, left: els.previewStage.scrollLeft, top: els.previewStage.scrollTop };
    els.previewStage.setAttribute("dragging", "");
    els.previewStage.setPointerCapture(e.pointerId);
  });
  els.previewStage.addEventListener("pointermove", (e) => {
    if (!pan) return;
    els.previewStage.scrollLeft = pan.left - (e.clientX - pan.x);
    els.previewStage.scrollTop = pan.top - (e.clientY - pan.y);
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach((type) => {
    els.previewStage.addEventListener(type, () => {
      pan = null;
      els.previewStage.removeAttribute("dragging");
    });
  });

  if ("ResizeObserver" in window) {
    const ro = new ResizeObserver(() => applyZoom());
    ro.observe(els.previewStage);
  } else {
    window.addEventListener("resize", applyZoom);
  }

  els.copyText.addEventListener("click", async () => {
    const page = currentPage();
    if (!page) return;
    const ok = await copyToClipboard(page.text);
    toast(ok ? "متن در کلیپ‌بورد کپی شد." : "کپی متن ممکن نشد.");
  });

  els.downloadTxt.addEventListener("click", () => {
    const page = currentPage();
    if (!page) return;
    download(`${baseName()}${pageSuffix()}_ocr.txt`, page.text, "text/plain;charset=utf-8");
    toast("فایل TXT دانلود شد.");
  });

  els.downloadOriginal.addEventListener("click", () => {
    if (!state.file) return;
    const url = URL.createObjectURL(state.file);
    const a = document.createElement("a");
    a.href = url;
    a.download = state.file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast("فایل اصلی دانلود شد.");
  });

  els.copyJson.addEventListener("click", async () => {
    const page = currentPage();
    if (!page) return;
    const ok = await copyToClipboard(JSON.stringify(page.json, null, 2));
    toast(ok ? "JSON در کلیپ‌بورد کپی شد." : "کپی JSON ممکن نشد.");
  });

  els.downloadJson.addEventListener("click", () => {
    const page = currentPage();
    if (!page) return;
    download(
      `${baseName()}${pageSuffix()}_ocr.json`,
      JSON.stringify(page.json, null, 2),
      "application/json;charset=utf-8"
    );
    toast("فایل JSON دانلود شد.");
  });

  /* ---------------- boot ---------------- */

  applyFormatsHint();
  refreshHealth();
  refreshSaved();
  setInterval(refreshHealth, 8000);
  window.addEventListener("focus", refreshHealth);
})();
