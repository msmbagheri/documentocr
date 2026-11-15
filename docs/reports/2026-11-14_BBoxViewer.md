# کامپوننت Visual Bounding Box Viewer — گزارش مأموریت تکمیلی

- **تاریخ:** 2026-11-14
- **دامنه:** افزودن نمایشگر بصری کادرها به صفحهٔ نتیجهٔ UI موجود (بدون تغییر موتور/مدل/معماری)
- **پشتیبان قبل از تغییر:** `backups/2026-11-14_pre_bbox_viewer.tar.gz`

---

## ۱. بررسی ساختار داده (خروجی واقعی، قبل از پیاده‌سازی)

| فایل | کلیدهای واقعی مشاهده‌شده | نتیجه |
|---|---|---|
| `results/konkour/jsons/page_1_ocr.json` | `input_path, image_bbox:[0,0,2480,3508], text, blocks[{label,bbox,confidence,reading_order,text,html}]` | مختصات در فضای پیکسلی تصویر اصلی؛ polygon در بلوک‌ها **ندارد** |
| `results/konkour/jsons/page_1_lines.json` | `bboxes[37]{bbox,polygon,confidence}, heatmap, affinity_map, image_bbox` | خطوط Detection با polygon چهارضلعی؛ همهٔ مختصات داخل بازهٔ تصویر (۰ خارج از بازه) |
| `results/jsons/doc_sample2-1_lines.json` | `image, lines, avg_confidence, bboxes[{bbox,confidence}]` | ساختار هر دو شکل (dict/array) در خواندن پشتیبانی شد |

**دو لایه از هم تفکیک شدند:** OCR Blocks (تحلیل ساختار سند) ≠ Detection Lines (خروجی detector). heatmap/affinity_map حجیم‌اند و هرگز به UI ارسال نمی‌شوند.

## ۲. پیاده‌سازی

### بک‌اند (`webui/server.py` — ~۷۰ خط اضافه)
- `collect_layers()`: از `<stem>_lines.json` واقعی فقط `bboxes` (+polygon/confidence) را می‌خواند؛ سقف ۳۰۰۰ کادر؛ علامت `truncated`.
- اعتبارسنجی: `_boxes_within()` همهٔ مختصات بلوک‌ها و خطوط را با ابعاد واقعی تصویر (تلورانس ۱.۵px) می‌سنجد → `blocks_valid` / `layers.valid`. **هیچ اصلاح بی‌صدایی انجام نمی‌شود؛** دادهٔ نامعتبر با هشدار به UI می‌رسد.
- هر صفحه: `image_size` (ابعاد موتور) + `layers` + `blocks_valid`.

### فرانت (`index.html + styles.css + app.js`)
- کارت «بررسی بصری کادرها» داخل همان بخش نتیجه؛ گرید دوستونه (تصویر + پنل جانبی)، موبایل تک‌ستونه.
- **دقت مختصات:** SVG با `viewBox="0 0 W H"` برابر فضای موتور و `preserveAspectRatio="none"` روی قاب دقیقاً هم‌اندازهٔ تصویر → نگاشت ۱:۱ مستقل از زوم/اسکرول؛ stroke ها `vector-effect: non-scaling-stroke`.
- رنگ‌ها: بلوک OCR آبی، خط Detection سبز، کادر انتخاب‌شده نارنجی؛ fill شفاف تا متن تصویر دیده شود؛ شمارهٔ ترتیب با halo سفید.
- تعامل: کلیک روی کادر → انتخاب + پنل اطلاعات (label، reading order، confidence، متن کامل، bbox) + دکمهٔ کپی؛ کلیک روی ردیف فهرست → انتخاب + اسکرول خودکار به کادر؛ hover دوطرفه (ردیف↔کادر)؛ کلیک روی فضای خالی → لغو انتخاب.
- کنترل‌ها: نمایش/مخفی بلوک‌ها، خطوط، شماره‌ها + زوم −/＋/تناسب (۰.۵×–۴×) + drag-to-pan.
- زوم/پن روی «قاب هم‌اندازهٔ تصویر» پیاده شد (نه object-fit) تا الزام ۶.۴ برآورده شود.

## ۳. نتایج تست (اجرای واقعی مرورگر — بدون دادهٔ ساختگی)

| تست | نتیجه | مدرک |
|---|---|---|
| صفحه کنکور (۳۷ بلوک) | ۳۷ rect + ۳۷ شماره + ۳۷ ردیف | `ui_bbox_viewer.py` چک ۲–۶ |
| انطباق مختصات ۶ کادر اول با JSON موتور | حداکثر خطا **۰.۰ پیکسل** (تلورانس ≤۲px) | چک ۱۰ |
| پایداری زیر زوم ۱۲۵٪ | انحراف ۰.۰px | چک ۱۱ |
| سند نمونه (doc_sample2-1، ۴ بلوک) | ۴ rect، انحراف زوم ۰.۰px | `04_sample_doc_boxes.png` |
| کلیک کادر → متن/label/confidence/order + کپی | PASS (کلیپ‌بورد = متن واقعی) | چک ۱۴–۱۹ |
| فهرست → انتخاب + اسکرول به کادر | PASS | چک ۲۰–۲۳ |
| hover دوطرفه | PASS | چک ۲۴ |
| لایه‌ها: بلوک‌ها/خطوط/شماره‌ها on-off | PASS (۳۷ خط واقعی) | چک ۲۵–۳۱ |
| لغو انتخاب با کلیک فضای خالی | PASS | چک ۳۲ |
| رگرسیون امکانات قبلی | **ui_smoke.py 36/36 PASS** | آپلود/متن/JSON/دانلود سالم |
| بدون اسکرول افقی/بریدگی (۱۴۴۰ و ۳۹۰) | PASS | چک ۳۳–۳۴ |

**جمع: `ui_bbox_viewer.py` ۳۵/۳۵ PASS + `ui_smoke.py` ۳۶/۳۶ PASS.** هیچ خطای JS در هیچ اجرایی ثبت نشد.

## ۴. فایل‌های تغییر یافته

| فایل | تغییر |
|---|---|
| `webui/server.py` | +۷۰ خط: `collect_layers`, `_boxes_within`, فیلدهای `layers/blocks_valid/image_size` |
| `webui/static/index.html` | کارت viewer (کادرها، کنترل‌ها، فهرست، پنل اطلاعات) |
| `webui/static/styles.css` | +~۳۰۰ خط استایل viewer + واکنش‌گرای موبایل |
| `webui/static/app.js` | +~۳۰۰ خط: رندر SVG، زوم/پن، انتخاب دوطرفه، هشدارها |
| `webui/tests/ui_bbox_viewer.py` | جدید (۳۵ چک) |
| `README.md` | بخش Bounding-box viewer + دستور تست |
| `classes/*`, `main.py`, `run_ocr.sh` | **دست‌نخورده** |

## ۵. شواهد تصویری

`docs/reports/2026-11-14_bbox_viewer/screenshots/`:
- `01_konkour_boxes_full.png` — صفحهٔ کنکور با تمام ۳۷ کادر (نمای کامل)
- `02_konkour_boxes_viewer.png` — کراپ کارت viewer دسکتاپ
- `03_konkour_boxes_mobile.png` — موبایل ۳۹۰px
- `04_sample_doc_boxes.png` — سند نمونه با ۴ کادر

## ۶. محدودیت‌های واقعی

1. برای صفحات PDF، تصویر viewer از JPEG پیش‌نمایش سرور (≤۱۵۰۰px) می‌آید؛ به‌دلیل نگاشت viewBox انطباق دقیق حفظ می‌شود (تست شد) و فقط وضوح تصویر پایین‌تر است.
2. در این پایپ‌لاین بلوک‌های OCR فاقد polygon هستند (فقط bbox) — polygon فقط برای خطوط Detection موجود و نمایش داده می‌شود.
3. سقف ۳۰۰۰ کادر در لایهٔ خطوط (با هشدار صریح در UI در صورت برخورد).

## ۷. اجرا

همان دستور قبلی — بدون گام جدید:
```bash
cd "/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main" && ./run_ui.sh
# http://127.0.0.1:8501  →  OCR را اجرا کنید؛ کارت «بررسی بصری کادرها» در بخش نتیجه است
```
