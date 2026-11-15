# فعال‌سازی پایپ‌لاین DocumentOCR با Surya 2.5 + llama.cpp

- **تاریخ:** 2026-11-14
- **دامنه:** مأموریت فعال‌سازی (نه توسعه معماری جدید)
- **پروژه:** `/home/metadeep-one/projects/documentocr`
- **زیرپروژه:** `generalocr /general_ocr-main` (نام دایرکتوری دارای فاصله انتهایی است)
- **وضعیت VCS:** مخزن Git نیست؛ همه تغییرات فایل محلی و ثبت‌نشده‌اند

---

## A. وضعیت نهایی

**موفق با محدودیت**

### بخش‌هایی که واقعاً کار می‌کنند (با مدرک اجرا)

| قابلیت | وضعیت | مدرک |
|---|---|---|
| Recognition واقعی از طریق llama.cpp | کار می‌کند | `docker logs surya-llama` + ۱۰ فایل `*_ocr.json` با متن غیرخالی |
| بارگذاری مدل از مسیر محلی | کار می‌کند | `-m /models/surya-2.5-Q8_0.gguf --mmproj /models/surya-2.5-mmproj.gguf` (bind-mount فقط-خواندنی) |
| حفظ Detection موجود (Surya `DetectionPredictor`) | کار می‌کند | `*_lines.json` با کلیدهای `bboxes, heatmap, affinity_map, image_bbox` بدون تغییر |
| خارج بودن Paddle از مسیر اصلی | کار می‌کند | `ENABLE_PADDLE=false` → پیام «Paddle layout stage is skipped (not called)» |
| خوانده شدن سند واقعی A4 توسط `main.py` | کار می‌کند | `results/konkour/jsons/page_1_ocr.json` — ۳۷ بلوک / ۱۱۱۵ کاراکتر |
| Batch ≥ ۱۰ ورودی بدون Crash | کار می‌کند | ۳ اجرای متوالی ۱۰-تصویری موفق (۲ اجرای `main.py` + ۱ اجرای `run_ocr.sh`) |
| دستور اجرای مجدد مستند | کار می‌کند | `./run_ocr.sh` (تأیید end-to-end در ۵۹ ثانیه) |
| خروجی OCR در قالب JSON قابل مشاهده | کار می‌کند | `*_ocr.json` با `text` + `blocks[]` |

### بخش‌هایی که هنوز مسدود هستند

| مورد | وضعیت | علت واقعی مشاهده‌شده |
|---|---|---|
| PaddleOCR (layout + YOLO export) | مسدود/غیرفعال | paddlepaddle 2.6.2 → SIGSEGV در `NaiveExecutor::CreateVariables`؛ paddlepaddle 3.3.1 → `NotImplementedError` در PIR. طبق دامنه مأموریت ارتقا انجام نشد |
| ارزیابی کمّی دقت روی ۴۵۲۱ نمونه | انجام نشد | خارج از محدوده مأموریت (§۱۰) |
| نسخه‌بندی تغییرات | ممکن نیست | پروژه مخزن Git نیست |

---

## B. وضعیت محیط

### نسخه‌های Python / کتابخانه‌ها (از venv خود پروژه)

| پکیج | نسخه |
|---|---|
| Python | 3.12.3 |
| `surya-ocr` | **0.23.0** |
| `torch` | 2.15.0 |
| `torchvision` | 0.29.2 |
| `transformers` | 5.22.2 |
| `paddleocr` | 3.7.0 |
| `paddlepaddle` | 2.6.2 (ناسازگار با این میزبان) |
| `huggingface-hub` | 1.33.0 |
| `pillow` | 10.4.0 |
| `numpy` | 2.3.5 |

### llama.cpp

| مورد | مقدار |
|---|---|
| Image | `ghcr.io/ggml-org/llama.cpp:server-cuda` (از قبل موجود؛ دانلود مجدد انجام نشد) |
| نسخه | **9894 (a8cfdbb9e)** — از `--version` داخل کانتینر |
| کانتینر | `surya-llama` |
| دسترسی | `127.0.0.1:8080` (فقط loopback میزبان) |
| Model id گزارش‌شده | `datalab-to/surya-ocr-2.5` (از `/v1/models`) |

### مشخصات مدل‌های GGUF

مسیر واحد و متمرکز: `datasets/surya_gguf/` (تنها نقطه‌ای که مسیر مدل تعریف شده است — در `.env`/کد تکرار نشده)

| فایل | بایت دقیق | حجم خوانا | SHA256 |
|---|---|---|---|
| `surya-2.5-Q8_0.gguf` | 628,680,096 | ~599.6 MiB | `5ab34c76845f66d2882ec5c89735894b700e0a7decd08898ab962b2afb9aca57` |
| `surya-2.5-mmproj.gguf` | 207,345,920 | ~197.7 MiB | `f245dbf784cf73683a273a37fefae0d0d7983b083a5d2fecf9309476f861f659` |

- منبع: `https://huggingface.co/datalab-to/surya-ocr-2.5-gguf/resolve/main/`
- **حجم دانلود واقعی: 836,026,016 بایت (≈ 797.3 MiB)** — یک‌بار، با `curl -C -` (قابل resume)، سپس SHA256 محاسبه و در `datasets/surya_gguf/SHA256SUMS.txt` ثبت شد.
- حجم واقعی با اعلام منبع (`content-length`) مطابقت دارد؛ فایل ناقص پذیرفته نشد.
- مدل Detection (موجود، بدون دانلود جدید): `~/.cache/datalab/models/text_detection/2025_05_07` — ۷۴ مگابایت.

### وضعیت GPU

| مورد | مقدار |
|---|---|
| کارت | NVIDIA RTX 6000 Ada Generation |
| حافظه کل | 49,140 MiB |
| حافظه مصرفی با سرور فعال | ~5.0–5.4 GiB |
| افزایش حافظه در Batch متوالی | 5414 → 5324 MiB (**بدون نشتی**) |
| خطای CUDA | صفر مورد در لاگ سرور |

---

## C. تغییرات پروژه

اصل حاکم: **هیچ بازنویسی ساختاری انجام نشد.** همهٔ تغییرات، حداقلی و با دلیل یک مانع واقعی.

| # | فایل:خط | تغییر | دلیل فنی ضرورت |
|---|---|---|---|
| ۱ | `classes/detection.py:1-16` | افزودن `load_dotenv(override=True)` **قبل از** import های surya؛ افزودن `json`, `re` | Surya متغیر `SURYA_INFERENCE_*` را در زمان import/ساخت predictor می‌خواند؛ بدون این، `.env` دیرتر از surya بارگذاری می‌شد و predictor تلاش می‌کرد سرور خودش را spawn کند |
| ۲ | `classes/detection.py:84-87` | `self.recognition_predictor = RecognitionPredictor() if settings.ENABLE_RECOGNITION else None` | **یافتهٔ اصلی مأموریت:** predictor ساخته می‌شد ولی هیچ‌جا صدا زده نمی‌شد؛ پایپ‌لاین هرگز متنی تولید نمی‌کرد. کلید `ENABLE_RECOGNITION` امکان غیرفعال‌سازی سریع را حفظ می‌کند |
| ۳ | `classes/detection.py:89-115` | متد جدید `_save_ocr()`: تبدیل `PageOCRResult.blocks[].html` → متن ساده + ذخیره `<stem>_ocr.json` | API واقعی Surya 0.23.0 متن را در `block.html` می‌دهد؛ قرارداد `*_lines.json` نباید تغییر کند → فایل **جدید و افزایشی** نوشته می‌شود (کوچک‌ترین Adapter ممکن) |
| ۴ | `classes/detection.py:118-129` | فراخوانی recognition داخل `detect()` با `try/except` به‌ازای هر تصویر | بدون try/except، قطع سرور کل Batch را متوقف می‌کرد؛ اکنون خطا لاگ و پایپ‌لاین ادامه می‌دهد (مدرک: تست قطع سرویس) |
| ۵ | `config.py:26-27` | `ENABLE_PADDLE: bool = False` و `ENABLE_RECOGNITION: bool = True` | نیاز به سوئیچ قابل بازگشت برای خارج‌کردن Paddle از مسیر حیاتی، بدون حذف کد |
| ۶ | `main.py:35-51` | گیت `ENABLE_PADDLE` دور مرحلهٔ layout و merge؛ با `false` فقط `['lines']` اجرا می‌شود و merge/YOLO رد می‌شود | Paddle در Runtime کرش می‌کرد و مانع اجرای Surya می‌شد؛ این تغییر حداقلی، کد Paddle را دست‌نخورده نگه می‌دارد |
| ۷ | `.env:17-23` | `SURYA_INFERENCE_BACKEND=llamacpp`, `SURYA_INFERENCE_URL=http://127.0.0.1:8080/v1`, `ENABLE_PADDLE=false`, `ENABLE_RECOGNITION=true` | آدرس سرور و سوئیچ‌ها باید قابل تغییر از تنظیمات باشند، نه hard-code در کد |
| ۸ | `run_ocr.sh:1-58` | **فایل جدید**: بررسی وجود مدل‌ها، شروع کانتینر در صورت نیاز، انتظار برای `/health`، سپس اجرای `main.py` | الزام «یک دستور قابل تکرار»؛ همچنین فلگ‌های حیاتی (`--image-min-tokens`, `--alias`) در یک نقطهٔ مرجع متمرکز شد |
| ۹ | `README.md:29-88` | بخش جدید: دارایی‌ها، دستور یک‌خطی، اجرای دستی سرور، خروجی‌ها، جدول سوئیچ‌ها | مستندسازی راه‌اندازی مجدد پس از Restart |
| ۱۰ | `datasets/surya_gguf/` | دو مدل GGUF + `SHA256SUMS.txt` | دارایی مأموریت؛ داخل root پروژه (مطابق قانون محل فایل) |
| ۱۱ | `results/sample/jsons/`, `results/konkour/jsons/` | شواهد خروجی (۲۰ + ۲ فایل) | مدرک اجرای واقعی |

### کدهای دست‌نخورده (عمداً)

- `classes/detection.py` → کلاس `Detection` و `SuryaDetection.detection_predictor` بدون تغییر
- `classes/result.py`, `classes/dataset.py`, `gen.py`, `utils.py`, `bench/*`
- تمام مسیر PaddleOCR و مدل‌های دانلودشدهٔ آن (فقط از مسیر اجرا خارج شد)
- EasyOCR (فقط به‌عنوان baseline، در مسیر محصول نیست)

---

## D. شواهد اجرا

### ۱) راه‌اندازی سرور

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

لاگ واقعی بارگذاری:

```
load_model: loading model '/models/surya-2.5-Q8_0.gguf'
load_model: loaded multimodal model, '/models/surya-2.5-mmproj.gguf'
load_model: initializing, n_slots = 1, n_ctx_slot = 16384
llama_server: model loaded
llama_server: listening on http://0.0.0.0:8080
```

هشدار واقعی llama.cpp (منشأ فلگ `--image-min-tokens`):

```
W load_hparams: Qwen-VL models require at minimum 1024 image tokens to function correctly on grounding tasks
W load_hparams: if you encounter problems with accuracy, try adding --image-min-tokens 1024
```

تأیید دسترسی (HTTP 200 به‌تنهایی معیار نبود — پاسخ واقعی مدل هم گرفته شد):

```
GET /health   -> {"status":"ok"}
GET /v1/models -> datalab-to/surya-ocr-2.5
```

### ۲) تست A — Recognition روی ۳ نمونه IDPL-PFOD

مدل: `surya-ocr 0.23.0` → `RecognitionPredictor([image])` → سرور محلی llama.cpp

| نمونه | نوع | Ground Truth | خروجی OCR | زمان | خطا |
|---|---|---|---|---|---|
| `test_00000.png` | متن فارسی ساده | `رسد و حتی در رودبار بسیاری از روغن هایی که بدون علامت استاندارد و پروانه` | `رسد و حتی در رودبار بسیاری از روغن هایی که بدون علامت استاندارد و پروانه` (**دقیق**) | 1.7s | — |
| `test_00100.png` | متن فارسی دشوار | `ضوابط واردات خودرو را به شورای اقتصاد ارسال کرد تا پس از بررسی، به‌منظور تصویب` | `ضوابط واردات خودرو را به شورائ اقتصاد ارسال کرد تا پس از بررسی، به منظور تصویب` (یک نویسه: شورای→شورائ) | 0.5s | — |
| `test_00250.png` | متن با اعداد/کاراکتر حساس | `دیگر از محصولات اساسی بخش کشاورزی افزود: در زمینه شکر نیز اتفاقاتی در سال های` | `دیگر از محصولات اساسی بخش کشاورزی افزود: در زمینه شکر نیز اتفاقاتی در سال های` (**دقیق**) | 0.5s | — |

**خطای مشاهده‌شده و رفع آن:** در اجرای اول (بدون `--image-min-tokens 1024`) نمونهٔ `test_00000.png` خروجی **خالی** (`blocks=0`) و نمونهٔ `test_00100.png` خروجی به‌شدت مخدوش (`موالك وازداخت خود روا به خترای الصاد...`) داد. با افزودن فلگ پیشنهادی خود llama.cpp، هر سه نمونه خروجی معتبر دادند.

### ۳) تست B — سند واقعی از طریق `main.py` (پایپ‌لاین اصلی)

**۳-الف) ۱۰ تصویر نمونهٔ پروژه** (`DATA_PATH=./data/images/sample/`):

```
Running SuryaDetection on dataset with 10 images
Saved OCR text -> ./results/sample/jsons/catalog_sample-1_ocr.json (330 chars)
Saved OCR text -> ./results/sample/jsons/catalog_sample-2_ocr.json (1116 chars)
Saved OCR text -> ./results/sample/jsons/catalog_sample-3_ocr.json (869 chars)
Saved OCR text -> ./results/sample/jsons/catalog_sample-4_ocr.json (1221 chars)
Saved OCR text -> ./results/sample/jsons/catalog_sample-5_ocr.json (794 chars)
Saved OCR text -> ./results/sample/jsons/catalog_sample-6_ocr.json (48 chars)
Saved OCR text -> ./results/sample/jsons/doc_sample2-1_ocr.json (1585 chars)
Saved OCR text -> ./results/sample/jsons/ocr_sample-1_ocr.json (1524 chars)
Saved OCR text -> ./results/sample/jsons/sample_1_ocr.json (1476 chars)
Saved OCR text -> ./results/sample/jsons/sample_2_ocr.json (1476 chars)
SuryaDetection completed for 10 images
Detection completed successfully
```

خروجی: ۱۰ فایل `*_lines.json` + ۱۰ فایل `*_ocr.json`؛ زمان کل ≈ ۴۷ ثانیه (≈ ۴.۷ ثانیه/تصویر).

**۳-ب) صفحهٔ واقعی A4 (صفحهٔ تولیدشدهٔ کنکور)** — از طریق همان `main.py`:

```
input: output_konkour/images/page_1.png
Saved OCR text -> ./results/konkour/jsons/page_1_ocr.json (1115 chars)
7.65s/it
```

۳۷ بلوک، ۱۱۱۵ کاراکتر. نمونهٔ واقعی متن (به‌همراه فرمول ریاضی به LaTeX):

```
[0] آزمون سراسری
[2] ۱- سوال ۱: مقدار x را در معادله زیر بیابید:
[7] ۲- سوال ۲: اگر a و b دو عدد صحیح باشند و b \times a = ۲۰ ، کدام گزینه می تواند حاصل a + b باشد؟
[12] ۳- سوال ۳: در شکل زیر، مساحت مثلث ABC چقدر است؟
[27] ۶- سوال ۶: حد عبارت \lim_{x \rightarrow 0} \sin(x)/x چقدر است؟
```

**نمونهٔ JSON واقعی** (`results/sample/jsons/doc_sample2-1_ocr.json`):

```json
{
  "input_path": "./data/images/sample/doc_sample2-1.png",
  "image_bbox": [0.0, 0.0, 1241.0, 1754.0],
  "text": "OCR Research &amp; Development with Vision-Language Models\n• Conducted R&amp;D on OCR pipelines using advanced Vision-Language Models (VLMs) ...",
  "blocks": [
    {
      "label": "SectionHeader",
      "bbox": [116.654, 108.748, 884.833, 145.582],
      "confidence": 0.989905812189549,
      "reading_order": 0,
      "text": "OCR Research &amp; Development with Vision-Language Models",
      "html": "<h2>OCR Research &amp; Development with Vision-Language Models</h2>"
    }
  ]
}
```

**قرارداد خروجی حفظ شد:** `*_lines.json` همان کلیدهای قبلی را دارد → `['bboxes', 'heatmap', 'affinity_map', 'image_bbox']` (تولیدشده توسط `classes/result.py` دست‌نخورده). متن در فایل جداگانه و افزایشی `*_ocr.json` است.

### ۴) تست C — پایداری Batch

| معیار | نتیجه |
|---|---|
| همهٔ ورودی‌ها پردازش شدند | ✅ ۱۰/۱۰ (سه بار متوالی) |
| خروجی برای همه تولید شد | ✅ ۱۰ `*_lines.json` + ۱۰ `*_ocr.json` |
| افزایش کنترل‌نشدهٔ حافظهٔ GPU | ❌ مشاهده نشد: 5414 → 5324 MiB |
| Crash در اجرای متوالی | ❌ مشاهده نشد |
| خطای سرور | 0 مورد (`grep -icE "error|exception|oom"` = 0) |
| وضعیت کانتینر بعد از Batch | `Up (healthy)` |

### ۵) تأیید end-to-end دستور واحد (`./run_ocr.sh`)

از حالت کاملاً تمیز (کانتینر حذف‌شده، `results/sample` پاک):

```
GPU before: 3342 MiB
[1/2] starting llama.cpp server (surya-llama) on 127.0.0.1:8080
      waiting for /health ...
      server healthy
[2/2] running pipeline: python main.py
SuryaDetection completed for 10 images
Detection completed successfully

real 0m59.060s
artifacts: 20 file (10 lines + 10 ocr)
GPU after: 5049 MiB
```

### ۶) تست مسیر خطا — قطع سرور

با `docker stop surya-llama` و اجرای `main.py`:

```
ERROR | classes.detection:detect:128 - Recognition failed for ./data/images/konkour/page_1.png:
  SpawnError: SURYA_INFERENCE_URL=http://127.0.0.1:8080/v1 is not reachable at /health.
  Start the server or unset the variable.
SUCCESS | classes.detection:detect:130 - SuryaDetection completed for 1 images
SUCCESS | __main__:<module>:53 - Detection completed successfully
```

→ خطا **قابل تشخیص** و **غیرکشنده** است؛ Detection کامل شد. سپس سرور بازگردانده شد (`server healthy`).

---

## E. محدودیت‌ها (فقط موارد مشاهده‌شده در اجرا)

1. **`--image-min-tokens 1024` اجباری است ولی پیش‌فرض Surya نیست.** بدون آن، روی برش‌های خطی IDPL خروجی خالی یا مخدوش تولید شد (مشاهدهٔ مستقیم). مقدار در `run_ocr.sh` و README ثبت شده است.
2. **دقت روی برش خط (line-crop) و صفحهٔ کامل یکسان نیست.** در ۳ نمونه: ۲ مورد دقیق، ۱ مورد یک نویسه اختلاف (`شورای`→`شورائ`). این تست اتصال بود، نه سنجش دقت.
3. **فرمول‌های ریاضی در صفحهٔ A4 همیشه درست نیستند.** نمونهٔ واقعی: `\lim_{x \rightarrow 0} \sin(x)/x` صحیح، اما برخی گزینه‌های عبارات جبری به‌شکل `\mathbb{a}` یا `{}^yab` آمدند.
4. **`&amp;` در خروجی HTML باقی می‌ماند** (خروجی خام مدل؛ unescape جزو قرارداد فعلی نیست و تغییر داده نشد).
5. **مرحلهٔ layout/YOLO با Paddle غیرفعال است** → `*_layout.json` و export مربوطه تولید نمی‌شود. برچسب‌های ساختاری (Heading/Picture/...) اکنون از بلوک‌های Surya می‌آیند.
6. **وابستگی به سرور در حال اجرا.** اگر سرور بالا نباشد، Recognition رد می‌شود (با لاگ خطا) و فقط Detection انجام می‌شود.
7. **`load_dotenv(override=True)`** باعث می‌شود متغیرهای محیطی shell نتوانند `.env` را override کنند؛ تغییر مسیر داده باید در `.env` انجام شود (در تست‌ها `.env` موقتاً ویرایش و سپس بازگردانده شد).
8. **بدون VCS.** پروژه مخزن Git نیست؛ تغییرات قابل `git diff` نیستند و بازبینی فقط با مقایسهٔ متنی ممکن است.
9. **پورت ۸۰۸۰ روی loopback ثابت است.** تعارض با سرویس دیگر بررسی نشده (در این میزبان آزاد بود).

---

## F. دستور راه‌اندازی مجدد (بعد از Restart سیستم)

```bash
cd "/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main"
./run_ocr.sh
```

همین. اسکریپت خودش: مدل‌ها را بررسی می‌کند، کانتینر `surya-llama` را می‌سازد، تا `/health` صبر می‌کند، سپس `main.py` را اجرا می‌کند.

### اجرای دستی (دو دستور)

```bash
# ۱) سرور
docker rm -f surya-llama 2>/dev/null
docker run -d --name surya-llama --gpus all \
  -p 127.0.0.1:8080:8080 \
  -v /home/metadeep-one/projects/documentocr/datasets/surya_gguf:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server-cuda \
  -m /models/surya-2.5-Q8_0.gguf \
  --mmproj /models/surya-2.5-mmproj.gguf \
  -ngl 99 --host 0.0.0.0 --port 8080 \
  --parallel 1 --ctx-size 16384 --image-min-tokens 1024 \
  --alias datalab-to/surya-ocr-2.5 --jinja --special

# ۲) پایپ‌لاین
cd "/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main"
./venv_general_ocr/bin/python main.py
```

### بررسی سلامت

```bash
curl -s http://127.0.0.1:8080/health            # -> {"status":"ok"}
curl -s http://127.0.0.1:8080/v1/models | python3 -c "import sys,json;print(json.load(sys.stdin)['data'][0]['id'])"
# -> datalab-to/surya-ocr-2.5
```

### تغییر ورودی/خروجی

در `.env` مقدار `DATA_PATH` و `JSONS_PATH` را تغییر دهید، سپس `./run_ocr.sh` (یا `main.py`) را دوباره اجرا کنید.

### توقف

```bash
docker stop surya-llama      # توقف موقت
docker rm -f surya-llama     # حذف کامل
```

---

## G. نتیجه پذیرش

| # | معیار پذیرش | وضعیت | مدرک |
|---|---|---|---|
| ۱ | Recognition واقعاً از طریق llama.cpp اجرا شود | **PASS** | `docker logs surya-llama` (مدل + mmproj لود شد، صفر خطا)؛ ۱۰ `*_ocr.json` با متن واقعی |
| ۲ | مدل از مسیر محلی بارگذاری شود | **PASS** | `-m /models/surya-2.5-Q8_0.gguf` از bind-mount `datasets/surya_gguf/`؛ `--alias` تأییدشده در `/v1/models` |
| ۳ | Detection موجود حفظ شده باشد | **PASS** | `detection_predictor` و `*_lines.json` دست‌نخورده؛ کلیدها: `bboxes, heatmap, affinity_map, image_bbox` |
| ۴ | Paddle در مسیر اصلی دخالت نداشته باشد | **PASS** | لاگ: `ENABLE_PADDLE=false -> Paddle layout stage is skipped (not called)`؛ هیچ import/اجرای Paddle در زمان اجرا |
| ۵ | حداقل یک سند واقعی توسط پایپ‌لاین اصلی خوانده شده باشد | **PASS** | `output_konkour/images/page_1.png` → `results/konkour/jsons/page_1_ocr.json` از طریق `main.py` |
| ۶ | خروجی OCR غیرخالی و قابل مشاهده تولید شده باشد | **PASS** | ۳۷ بلوک / ۱۱۱۵ کاراکتر (A4)؛ ۱۰ فایل غیرخالی (۴۸ تا ۱۵۸۵ کاراکتر) |
| ۷ | حداقل ۱۰ ورودی بدون Crash پردازش شده باشند | **PASS** | ۳ اجرای متوالی ۱۰-تصویری؛ صفر خطای سرور؛ GPU 5414→5324 MiB |
| ۸ | دستور اجرای مجدد مستند شده باشد | **PASS** | `./run_ocr.sh` (تأیید end-to-end، ۵۹ ثانیه) + README بخش «Local Surya 2.5 recognition» + بخش F همین گزارش |
| ۹ | تغییرات کد محدود و قابل بازبینی باشند | **PASS** | ۴ فایل کد/تنظیم (`detection.py` ۴ نقطه، `main.py` ۱ بلوک، `config.py` ۲ خط، `.env` ۷ خط) + ۱ اسکریپت جدید + README؛ هیچ فایل موجودی حذف نشد |

**جمع‌بندی:** ۹ از ۹ معیار پذیرش PASS. مأموریت با «موفق با محدودیت» بسته می‌شود؛ محدودیت‌ها در بخش E صرفاً موارد مشاهده‌شده هستند و هیچ‌کدام مانع تحویل متن واقعی از سند واقعی نیستند.

---

### پیوست: مسیرهای شاهد

| مورد | مسیر |
|---|---|
| مدل‌ها + checksum | `datasets/surya_gguf/` |
| خروجی ۱۰ نمونه (Batch) | `results/sample/jsons/` (۲۰ فایل) |
| خروجی صفحهٔ واقعی A4 | `results/konkour/jsons/page_1_{lines,ocr}.json` |
| اسکریپت اجرا | `generalocr /general_ocr-main/run_ocr.sh` |
| مستندات | `generalocr /general_ocr-main/README.md:29-88` |
