# IDPL-PFOD Persian OCR Benchmark (EasyOCR)

**Date:** 2026-11-14
**Task:** Measure Persian-OCR quality on the IDPL-PFOD benchmark dataset (the dataset used in the 2025 paper *"Empirical Evaluation of Well-known Farsi OCR Engines on the IDPL-PFOD Dataset"*) using a locally-available OCR engine, and compare against the published numbers.

## What was done

| Step | Result |
|---|---|
| Dataset | **IDPL-PFOD** from HF mirror `myrkur/IDPL-PFOD` → `datasets/IDPL-PFOD/` (30,138 line-images 700×50: 25,617 train + 4,521 test), shipped with UTF-8 ground-truth manifests |
| Engine | **EasyOCR 1.7.2** (`fa` → Arabic model `arabic.pth`), GPU, models cached locally — **no new downloads** |
| Metric | Persian-normalised CER / WER / char-accuracy (see `bench/persian_metrics.py`) |
| Harness | `bench/run_easyocr.py` (resumable) → `bench/easyocr_results.jsonl` (4,521 lines) |

## Measured results (4,521 test lines, EasyOCR)

| Metric | Value |
|---|---|
| Corpus CER | **68.21%** |
| Corpus WER | **88.87%** |
| Char accuracy (1−CER) | **31.79%** |
| Exact match (line) | **0.18%** |
| Engine runtime errors | 0 |
| Speed | ~24 img/s on RTX 6000 Ada |

## Published comparison (from the 2025 IDPL-PFOD paper)

| Engine | Published overall accuracy |
|---|---|
| Tesseract 5.x | **84.41%** |
| EasyOCR 1.x | **73.28%** |

## Honest comparison note (inference, not verified)

The published numbers come from the paper authors' own evaluation protocol (exact metric definition / test subset is **not verifiable from here**). Our measured EasyOCR char-accuracy (31.8%) is far below the paper's 73.28%. Likely contributing reasons — **these are inferences, not confirmed facts**:

1. **Metric definition mismatch (likely):** the paper's "overall accuracy" may be a different formula (e.g., word-level / partial-credit) than our strict CER on normalised text.
2. **Test-set selection:** the HF mirror (`myrkur/IDPL-PFOD`) may include noisy/textured backgrounds that the paper evaluates separately; we ran on the **full** 4,521-image test split as shipped.
3. **Normalisation strictness:** we unify ی/ي، ک/ك and drop tashkīl/ZWNJ; standard Levenshtein CER — small spelling variants count as errors.

We do **not** claim our number contradicts the paper; our protocol is simply different and fully reproducible.

## Sample outputs (GT → EasyOCR)

```
GT  : رسد و حتی در رودبار بسیاری از روغن هایی که بدون علامت استاندارد و پروانه
HYP : پروانه | بدون علامت استاندارد | از روغن مابی | حتی در رودبار | سماری
GT  : باشید» است که با حضور تمام نمایندگان استان‌های کشور مخاطبان خود را با
HYP : مخاطبان خود را با فرهتگ مناطف | تمام نمايندكان استانهاى | سث كه | ا تر
```

## Project-own OCR status (no-download check)

| Component | Status |
|---|---|
| Surya **line detection** | ✅ works offline (model cached in `~/.cache/datalab/models/text_detection/`) |
| Surya **text recognition** (v2.5 VLM) | ❌ needs the VLM model (GGUF) — not cached; download failed on network this session |
| PaddleOCR (project pipeline) | ❌ segfaults in PaddlePaddle 2.6.2 on this machine |

## Files

- `bench/persian_metrics.py` — normalisation + metrics
- `bench/run_easyocr.py`, `bench/aggregate_easyocr.py` — runner / summariser
- `bench/easyocr_results.jsonl` — 4,521 per-line results
- `datasets/IDPL-PFOD/images/` (30,138 PNG) + `train_manifest.jsonl` / `test_manifest.jsonl`
- `datasets/PTDR/` — real-world Persian scene/document text (42k+ files, SOTA bench in its 2025 paper)

## Next options (user choice)

1. QA a random sample of the 4,521 predictions visually (screenshots) — **Playwright rule** requires this before claiming quality.
2. Fix Surya recognition when network is stable (download `surya-ocr-2.5` GGUF once) → benchmark the *project's own* recogniser.
3. Install Tesseract `fas` (needs root) → full 3-way table.
