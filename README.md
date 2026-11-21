# konkoor_synth

> **Repository orientation** *(added 2026-11-21)* — this repo hosts two related efforts:
>
> 1. **konkoor_synth** (described below) — Persian Konkoor exam-page synthesis + OCR evaluation harness (root: `gen.py`, `evaluation/`, `output_konkour/`). Mostly dormant.
> 2. **DocumentOCR** *(ACTIVE)* — local Persian document OCR pipeline + web UI in [`generalocr /general_ocr-main/`](./generalocr%20/general_ocr-main/) (Surya 2.5 via llama.cpp; `./run_ui.sh` → http://127.0.0.1:8501; reports in `docs/reports/`).
>
> **AI agents:** start with [`AGENTS.md`](AGENTS.md) → [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) → [`docs/DECISIONS.md`](docs/DECISIONS.md), and run `python3 tools/drift_audit.py` at task start and closeout.
>
> <!-- reliability:orientation -->

This repository is created to synthisize Konkoor style pages:

![A Synthisized Sample](assets/photo_2025-06-07_09-06-53.jpg)

# Installation

I used python 3.13

```pip install -r requirements.txt```

# Generation

Contact me to give the json of the questions data.
You can change anything you want from `.env` file, the existing settings is what that created the test dataset.

Then run

```python gen.py --json_path <QUESTIONS_DATA_JSON_PATH> --n <NUMBER_OF_SAMPLES_TO_GENERATE>```

If the generation stopped in the middle and you wanted to resume it from where it lastly was, you can run the command again. Otherwise, pass ```--overwrite``` option.

The image results will be saved to `<OUTPUT_PATH>/images` and the bounding box results would be saved to `<OUTPUT_PATH/bboxes.json`

# Evaluation

The evaluation process is done by calling the local OCR API. make sure you have access, then set the correct api url in `evaluation/.env`. For more information read [./evaluation/README.md](./evaluation/README.md)

If you read the evaluation readme and yet want to use the first evaluation method, to prepare the dataset for each model run the followings:

```python
python prepare_dataset.py --task blocks
python prepare_dataset.py --task crops --identifier title
python prepare_dataset.py --task crops --identifier word
```

Then continue [from here](./evaluation/README.md#if-you-want-the-first-method)






