# گزارش نهایی مأموریت UI/UX — DocumentOCR Web UI

- **تاریخ:** ۲۰۲۶-۱۱-۱۴
- **زیرپروژه:** `/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main`
- **مأموریت:** ساخت رابط کاربری وب فارسی/RTL متصل به موتور واقعی Surya 2.5 + llama.cpp
- **مدل پاسخ‌دهنده:** `opencode/deepseek-v4.1-flash-free`

---

## A. وضعیت نهایی

**موفق با محدودیت** — رابط کاربری کامل، اجراشدنی و **واقعاً متصل به موتور OCR** تحویل شد.

| بخش | وضعیت | مدرک |
|---|---|---|
| بک‌اند (بدون وابستگی جدید) | ✅ کار می‌کند | `webui/server.py` — فقط `http.server` استاندارد |
| رابط فارسی/RTL تک‌صفحه | ✅ کار می‌کند | `webui/static/index.html` |
| اتصال به موتور واقعی | ✅ کار می‌کند | ۳۷ بلوک / ۱۱۱۵ کاراکتر از صفحهٔ کنکور در ۸.۱ ثانیه |
| وضعیت واقعی سرویس در سربرگ | ✅ کار می‌کند | پروب `/health` واقعی، پول ۸ ثانیه‌ای |
| بارگذاری + پیش‌نمایش + بزرگ‌نمایی | ✅ کار می‌کند | `02_file_selected_desktop.png` |
| متن فارسی، JSON، کپی، دانلود TXT/JSON | ✅ کار می‌کند | ۳۲/۳۲ تست، فایل‌های دانلودشده |
| PDF چندصفحه‌ای | ✅ کار می‌کند | ۲ صفحه، ۲۴ ثانیه، ۸/۸ تست |
| مدیریت خطای قطع سرور | ✅ کار می‌کند | ۱۲/۱۲ تست، دو سناریوی واقعی |
| چیدمان دسکتاپ/موبایل بدون بریدگی | ✅ کار می‌کند | بدون اسکرول افقی در ۱۴۴۰/۱۰۲۴/۷۶۸/۳۹۰ |
| **مسیر OCR موجود** | ✅ **دست‌نخورده** | diff با backup: `main.py`, `config.py`, `.env`, `run_ocr.sh`, `classes/*` همگی `UNCHANGED` |

**موارد مسدود:** هیچ‌کدام از قابلیت‌های درخواستی مسدود نیست.

---

## B. وضعیت پیش از توسعه (بررسی مستقل)

| مورد | وضعیت واقعی |
|---|---|
| فریم‌ورک وب موجود | ❌ هیچ FastAPI/Flask/Express در پروژه نبود |
| Playwright | ✅ نسخهٔ ۱.۶۱.۰ به‌صورت global + chromium در `~/.cache/ms-playwright` (بدون نصب جدید) |
| فونت فارسی محلی | ✅ `Vazirmatn-Regular/Bold.ttf` در `~/.local/share/fonts/` |
| زیرساخت PDF | ✅ واقعی: `pdf_utils.pdf_to_images` + `pdf2image` + `pdftoppm` (poppler) روی سیستم |
| فرمت‌های تصویری | ✅ Pillow: png, jpg, jpeg, webp, tiff, bmp, gif |
| وب‌سرور | ❌ نبود → تصمیم: `http.server` استاندارد (صفر وابستگی، آفلاین) |
| نسخهٔ Git | ❌ مخزن Git نیست → backup دستی در `backups/2026-11-14_pre_webui.tar.gz` |

**پشتیبان‌گیری قبل از تغییر:** `backups/2026-11-14_pre_webui.tar.gz` (۱۱ KB، شامل ۱۰ فایل اصلی پایپ‌لاین).

---

## C. تصمیم‌های معماری

1. **بدون فریم‌ورک جدید** — بک‌اند با `http.server` (کتابخانهٔ استاندارد پایتون). دلیل: پروژه هیچ وب‌فریم‌ورکی ندارد و مأموریت افزودن React/Vite/FastAPI را ممنوع کرده است.
2. **بازاستفاده از منطق موجود** — `webui/server.py` مستقیماً `classes.detection.SuryaDetection` را import می‌کند؛ هیچ کد OCR دوباره پیاده‌سازی نشده است.
3. **سریال‌سازی پردازش‌ها** — یک `threading.Lock` سراسری، چون llama.cpp با `--parallel 1` اجرا می‌شود (خواستهٔ صریح مأموریت).
4. **قرارداد خروجی دست‌نخورده** — UI فقط `*_ocr.json` را می‌خواند؛ `*_lines.json` و مسیر `results/` تغییری نکرده‌اند.
5. **بدون تماس شبکهٔ بیرونی در زمان اجرا** — فونت Vazirmatn به‌صورت محلی در `webui/static/fonts/` سرو می‌شود.

---

## D. تغییرات پروژه

### D.1 فایل‌های جدید

| فایل | خطوط | توضیح |
|---|---|---|
| `webui/server.py` | ۴۹۲ | بک‌اند: `/api/health`, `/api/config`, `POST /api/ocr` |
| `webui/static/index.html` | ۲۰۱ | ساختار تک‌صفحه (سربرگ، بارگذاری، پیش‌نمایش، نتیجه) |
| `webui/static/styles.css` | ۸۸۲ | طراحی مینیمال SaaS، RTL، واکنش‌گرا |
| `webui/static/app.js` | ۷۴۳ | منطق رابط: آپلود، وضعیت‌ها، نمایش نتیجه، کپی/دانلود |
| `webui/static/fonts/Vazirmatn-Regular.ttf` | — | فونت محلی (۱۲۰ KB) |
| `webui/static/fonts/Vazirmatn-Bold.ttf` | — | فونت محلی (۱۲۱ KB) |
| `run_ui.sh` | ۶۷ | اجرای یک‌دستوری UI + بالا آوردن موتور در صورت نیاز |
| `webui/tests/ui_smoke.py` | ۲۶۵ | ۳۲ تست عملکردی مرورگر |
| `webui/tests/ui_screenshots.py` | ۱۱۷ | اسکرین‌شات‌های شواهد (قبل/بعد OCR، دسکتاپ/موبایل) |
| `webui/tests/ui_pdf_check.py` | ۸۹ | تست PDF چندصفحه‌ای |
| `webui/tests/ui_error_state.py` | ۱۶۲ | تست واقعی قطع سرور (دو سناریو) |
| `webui/tests/data/sample_2pages.pdf` | — | سند PDF نمونه (۵۱۳ KB) |
| `backups/2026-11-14_pre_webui.tar.gz` | — | پشتیبان وضعیت قبل از توسعه |

### D.2 فایل‌های تغییرکرده

| فایل | تغییر | دلیل فنی |
|---|---|---|
| `README.md` | +۸۰ خط (هیچ خطی حذف نشد) | مستندسازی دستور اجرا، API، معماری و تست‌ها |

### D.3 فایل‌های دست‌نخورده (با diff نسبت به backup اثبات شده)

`main.py` · `config.py` · `.env` · `run_ocr.sh` · `classes/detection.py` · `classes/dataset.py` · `classes/result.py` — همگی **UNCHANGED**.

> «اصل مهم: منطق OCR موجود را مجدداً پیاده‌سازی نکن» — این تغییر با diff بایت‌به‌بایت اثبات شده است.

---

## E. نحوهٔ اتصال UI به موتور OCR

```
مرورگر ──POST /api/ocr──► webui/server.py  (http.server استاندارد)
                              │
                              ├─ ۱) آپلود → .webui_tmp/<job-uuid>/
                              ├─ ۲) PDF → pdf_utils.pdf_to_images (همان کد موجود)
                              ├─ ۳) SuryaDetection.detect()   ← همان کلاس پروژه
                              ├─ ۴) خواندن <stem>_ocr.json      ← خروجی واقعی موتور
                              └─ ۵) پاک‌سازی پوشهٔ موقت در finally
                                        │
                                   llama.cpp :8080 (Surya 2.5 GGUF)
```

- **بدون shell**: هیچ `subprocess`/`os.system` با ورودی کاربر وجود ندارد؛ نام فایل با `safe_stem()` پاک‌سازی می‌شود.
- **بدون کانتینر جدید برای هر درخواست**: یک کانتینر بلندمدت `surya-llama` (همان که `run_ocr.sh` می‌سازد) استفاده می‌شود.
- **مسیرشماری موقت**: هر کار پوشهٔ یکتا دارد؛ در `finally` حذف می‌شود؛ پوشه‌های کهنه‌تر از ۱ ساعت در شروع سرور پاک می‌شوند.
- **تشخیص خطا**: `HttpError` با کد و پیام فارسی (503 `engine_unavailable`، 415 `unsupported_type`، 422 `unreadable_image`، 422 `no_text`). خروجی خالی هرگز «موفقیت» گزارش نمی‌شود.

### API واقعی (نمونهٔ واقعی)

```json
{"ok": true, "file": "پیش_نویسی_آزمون.png", "kind": "image", "page_count": 1,
 "elapsed_ms": 8135, "pipeline_ms": 8113,
 "pages": [{"page": 1, "text": "آزمون سراسری\nصفحه ۱\n۱- سوال ۱: …",
            "blocks": 37, "chars": 1115, "image_size": [2480, 3508],
            "json": { …محتوای واقعی <stem>_ocr.json… }}]}
```

---

## F. شواهد اجرا

### F.1 تست‌های اجراشده (مرورگر واقعی، Playwright موجود)

| فایل تست | نتیجه | پوشش |
|---|---|---|
| `webui/tests/ui_smoke.py` | **۳۲/۳۲ PASS** | باز شدن صفحه، وضعیت موتور، آپلود، پیش‌نمایش، بزرگ‌نمایی، اجرای واقعی OCR، متن فارسی، JSON + هایلایت، کپی متن، کپی JSON، دانلود TXT، دانلود JSON، بدون اسکرول افقی در ۱۴۴۰/۱۰۲۴/۷۶۸/۳۹۰، چیدمان تک‌ستونهٔ موبایل، عدم بریدگی کارت‌ها |
| `webui/tests/ui_pdf_check.py` | **۸/۸ PASS** | پیش‌نمایش PDF، نشان «۲ صفحه پردازش شد»، تب‌های صفحه، متن صفحهٔ ۱ و ۲، تعویض صفحه |
| `webui/tests/ui_error_state.py` | **۱۲/۱۲ PASS** | سناریوی A: موتور خاموش هنگام بارگذاری صفحه؛ سناریوی B: موتور در حین درخواست خاموش می‌شود؛ بازیابی خودکار پس از بازگشت سرویس |

### F.2 زمان پردازش واقعی

| ورودی | زمان | خروجی |
|---|---|---|
| تصویر A4 کنکور (`page_1.png`) | **۸.۱ ثانیه** | ۳۷ بلوک / ۱۱۱۵ کاراکتر |
| PDF دو صفحه‌ای | **۲۴.۰ ثانیه** | صفحهٔ ۱: ۳۷ بلوک / ۱۴۰۴ کاراکتر — صفحهٔ ۲: ۴ بلوک / ۱۵۸۵ کاراکتر |

### F.3 نمونهٔ متن واقعی استخراج‌شده از UI

```
آزمون سراسری
صفحه ۱
۱- سوال ۱: مقدار x را در معادله زیر بیابید:
الف) گزینه الف: ۵ = x
ب) گزینه ب: ۱۰ = x
ج) گزینه ج: ۱۵ = x
۶- سوال ۶: حد عبارت \lim_{x \rightarrow 0} \sin(x)/x چقدر است؟
```

### F.4 اسکرین‌شات‌ها (شواهد بصری)

`docs/reports/2026-11-14_webui/screenshots/`

| فایل | محتوا |
|---|---|
| `01_initial_desktop.png` | حالت اولیه — سربرگ، وضعیت موتور «آماده به کار»، باکس بارگذاری، Placeholder پیش‌نمایش |
| `02_file_selected_desktop.png` | فایل انتخاب‌شده + کارت نام/حجم |
| `03_result_desktop_viewport.png` | نتیجهٔ واقعی OCR + متن فارسی |
| `04_result_text_card.png` | کارت «متن استخراج‌شده» |
| `05_result_json_panel.png` | JSON واقعی با Syntax Highlighting |
| `06_result_desktop_full.png` | کل صفحه پس از OCR (دسکتاپ) |
| `07_mobile_initial.png` | حالت اولیه (موبایل ۳۹۰) |
| `08_mobile_result_full.png` | نتیجهٔ کامل (موبایل) — تک‌ستونه، بدون بریدگی |
| `09_pdf_two_pages_result.png` | نتیجهٔ PDF دو صفحه‌ای با تب‌های صفحه |
| `10_engine_down_at_load.png` | حالت خطا: موتور خاموش → پیام فارسی، دکمهٔ غیرفعال |
| `11_engine_down_mid_request.png` | حالت خطا: قطع سرور حین درخواست |
| `smoke/` | خروجی کامل ۳۲ تست (شامل فایل‌های دانلودشدهٔ TXT/JSON) |

### F.5 تأیید عدم تغییر مسیر OCR

```
$ diff backup/<file> <file>   →   UNCHANGED  main.py
                                       UNCHANGED  config.py
                                       UNCHANGED  .env
                                       UNCHANGED  run_ocr.sh
                                       UNCHANGED  classes/detection.py
                                       UNCHANGED  classes/dataset.py
                                       UNCHANGED  classes/result.py
```

---

## G. محدودیت‌های واقعی (مشاهده‌شده در اجرا)

1. **پردازش سریال**: به دلیل `--parallel 1` در llama.cpp، هم‌زمانی درخواست‌ها پشتیبانی نمی‌شود؛ UI پیام «در حال پردازش» نشان می‌دهد و دکمه قفل می‌شود.
2. **محدودیت ۲۵ مگابایت** برای هر فایل آپلودی (`WEBUI_MAX_UPLOAD_BYTES`).
3. **حافظهٔ GPU**: مصرف پایدار ~۵.۰–۵.۴ GB از ۴۹ GB (نشتی مشاهده نشد).
4. **دقت مدل** (از مأموریت قبلی): فرمول‌های جبری گاهی به `\mathbb{a}` / `{}^yab` تبدیل می‌شوند؛ کاراکتر `&` به‌صورت `&amp;` در JSON خام باقی می‌ماند (متن نمایشی در UI درست است).
5. **سرور UI تک‌پروسه‌ای**: `http.server` برای استفادهٔ تیمی/هم‌زمان مناسب نیست (این مأموریت تک‌کاربره بود).
6. **بدون احراز هویت**: طبق محدودهٔ مأموریت، UI فقط روی `127.0.0.1` گوش می‌دهد.
7. **PDF رندرشده با `pdftoppm`**: PDFهای اسکن‌شده بدون لایهٔ متن با کیفیت ۲۰۰ DPI رندر می‌شوند (قابل تنظیم در `server.py`).

---

## H. دستور راه‌اندازی مجدد پس از Restart

```bash
# ۱) رابط کاربری (موتور OCR را هم در صورت نیاز بالا می‌آورد)
cd "/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main"
./run_ui.sh
# → http://127.0.0.1:8501
```

```bash
# ۲) فقط موتور OCR (بدون رابط)
./run_ocr.sh
```

```bash
# ۳) فقط بالا آوردن کانتینر llama.cpp
docker start surya-llama
curl -sf http://127.0.0.1:8080/health   # {"status":"ok"}
```

```bash
# ۴) اجرای تست‌های مرورگر (اختیاری)
python3 webui/tests/ui_smoke.py
python3 webui/tests/ui_pdf_check.py
python3 webui/tests/ui_error_state.py
```

---

## I. نتیجهٔ پذیرش

| # | معیار پذیرش | وضعیت | مدرک |
|---|---|---|---|
| ۱ | باز شدن صفحهٔ اصلی | **PASS** | `01_initial_desktop.png` · تست ۱ |
| ۲ | بارگذاری یک تصویر | **PASS** | `02_file_selected_desktop.png` · تست ۷–۹ |
| ۳ | نمایش صحیح پیش‌نمایش (+ بزرگ‌نمایی، بدون کشیدگی) | **PASS** | تست ۱۰–۱۳ · `object-fit` حفظ نسبت ابعاد |
| ۴ | اجرای واقعی OCR از طریق UI | **PASS** | ۸.۱ ثانیه، ۳۷ بلوک · `03_result_desktop_viewport.png` |
| ۵ | نمایش متن فارسی | **PASS** | تست ۱۵ · متن «آزمون سراسری…» |
| ۶ | نمایش JSON واقعی + هایلایت | **PASS** | تست ۱۷–۱۸ · `05_result_json_panel.png` |
| ۷ | کپی متن | **PASS** | تست ۲۰ (۱۱۱۵ کاراکتر در کلیپ‌بورد) |
| ۸ | دانلود TXT | **PASS** | تست ۲۳ (`page_1_ocr.txt`, ۱۶۷۹ B) |
| ۹ | دانلود JSON | **PASS** | تست ۲۴ (`page_1_ocr.json`, ۳۷ بلوک، JSON معتبر) |
| ۱۰ | مدیریت خطای قطع سرور | **PASS** | ۱۲/۱۲ · `10_…`, `11_…` · پیام فارسی، بدون نتیجهٔ خالی |
| ۱۱ | بررسی رزولوشن دسکتاپ | **PASS** | ۱۴۴۰/۱۰۲۴/۷۶۸ — بدون اسکرول افقی، بدون بریدگی |
| ۱۲ | بررسی رزولوشن موبایل | **PASS** | ۳۹۰ — تک‌ستونه، همهٔ کارت‌ها داخل صفحه |
| ۱۳ | حداقل یک سند واقعی از طریق UI | **PASS** | صفحهٔ کنکور + PDF دو صفحه‌ای |
| ۱۴ | اتصال واقعی به موتور (بدون داده ساختگی) | **PASS** | JSON خروجی = محتوای واقعی `<stem>_ocr.json` |
| ۱۵ | بدون کانتینر/مدل جدید | **PASS** | همان `surya-llama` و همان GGUFها؛ ۰ دانلود |
| ۱۶ | `run_ocr.sh` و مسیر CLI خراب نشده | **PASS** | diff با backup: `UNCHANGED` |
| ۱۷ | اسکرین‌شات قبل و بعد از OCR | **PASS** | ۱۱ تصویر در `docs/reports/2026-11-14_webui/screenshots/` |
| ۱۸ | README به‌روز | **PASS** | بخش «Web UI (DocumentOCR)» |
| ۱۹ | مستندات راه‌اندازی پس از Restart | **PASS** | بخش H |
| ۲۰ | بدون بریدگی/مخفی‌سازی محتوا | **PASS** | تست ۲۶–۲۷ · `line-clamp` استفاده نشده |

**نتیجه: ۲۰ از ۲۰ معیار پذیرش PASS.**

تعریف موفقیت مأموریت («کاربر بدون آموزش سند را بارگذاری کند، دکمهٔ OCR را بزند و خروجی واقعی را در صفحه ببیند») با شواهد اجرایی محقق شده است.

---
Models this task: opencode/deepseek-v4.1-flash-free
This session tokens: (tracked in ledger)
Worktree total tokens: (tracked in ledger)
Responded by: opencode/deepseek-v4.1-flash-free
