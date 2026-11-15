# DocumentOCR — ذخیره و بازیابی نتایج OCR (Saved Results)

**تاریخ:** 2026-11-15 · **دامنه:** Web UI (بک‌اند + فرانت) · **پایپ‌لاین OCR: دست‌نخورده**

## ۱. نیاز کاربر

پس از بارگذاری فایل و اجرای OCR، کاربر بتواند نتیجه را **ذخیره** کند؛ موارد ذخیره‌شده در یک **لیست** نمایش داده شوند و هر زمان خواست، همان نتیجه را **بازیابی** کند (پایدار در برابر reload و ری‌استارت سرور).

## ۲. پیاده‌سازی

### بک‌اند (`webui/server.py`)
- ذخیره‌سازی روی دیسک: `webui/saved/<id>/` شامل `meta.json` (نتیجهٔ کامل OCR: متن، بلوک‌ها، لایه‌ها، JSON موتور، ابعاد تصویر) + `page_<n>.jpg` (پیش‌نمایش هر صفحه).
- **Publish اتمیک:** ابتدا در `<id>.partial` نوشته می‌شود، سپس rename → ذخیرهٔ ناقص هرگز دیده نمی‌شود.
- API ها:
  | روش | مسیر | کار |
  |---|---|---|
  | POST | `/api/saved` | ذخیرهٔ نتیجه (بدنه = همان پاسخ `/api/ocr`) |
  | GET | `/api/saved` | فهرست خلاصه (جدید→قدیم) |
  | GET | `/api/saved/<id>` | بازیابی کامل — دقیقاً همان شکل پاسخ `/api/ocr` + `preview` بازتولیدشده از فایل JPEG |
  | DELETE | `/api/saved/<id>` | حذف مورد |
- امنیت/محدودیت: `id` فقط hex32 سرساخته (ضد path traversal)، حداکثر ۵۰ مورد (`WEBUI_MAX_SAVED_ITEMS`)، حداکثر حجم بدنه = `MAX_UPLOAD_BYTES`، اعتبارسنجی ساختار payload.
- `preview` ها در متا ذخیره نمی‌شوند (decode به JPEG واقعی) تا `meta.json` لاغر بماند؛ در GET دوباره data-url می‌شوند.

### فرانت (`static/`)
- دکمهٔ **«ذخیره نتیجه»** در نوار اکشن نتیجه؛ فقط پس از OCR موفق فعال می‌شود.
- کارت **«نتایج ذخیره‌شده»** در ستون بارگذاری: نام فایل، تاریخ/ساعت شمسی، تعداد کاراکتر/صفحه؛ کلیک روی ردیف = بازیابی؛ دکمهٔ حذف روی هر ردیف.
- برای تصاویر (برخلاف PDF که preview سروری دارد)، کلاینت خودش preview JPEG ≤۱۵۰۰px با canvas می‌سازد تا آیتم ذخیره‌شده کاملاً self-contained باشد.
- بازیابی: `state.result` از سرور پر می‌شود → همان مسیر `renderResult` → متن، JSON، آمار و **BoundingBoxViewer** (لایهٔ SVG با viewBox مختصات موتور — دقیقاً مثل نتیجهٔ زنده) همه بازسازی می‌شوند.

## ۳. اجرا (Playwright — واقعی، بدون mock)

`webui/tests/ui_saved_results.py` — ۱۵/۱۵ PASS:

| # | بررسی | نتیجه |
|---|---|---|
| 1 | آماده‌بودن موتور + بارگذاری سند واقعی (`output_konkour/images/page_1.png`) | PASS |
| 2 | OCR واقعی و رندر نتیجه | PASS |
| 3 | دکمهٔ ذخیره فعال + کلیک ذخیره | PASS |
| 4 | ردیف در لیست ظاهر شد (count=1) | PASS |
| 5 | فایل روی دیسک (`meta.json` + `page_1.jpg`) | PASS |
| 6 | **پایداری پس از reload صفحه** (count=1) | PASS |
| 7 | بازیابی با کلیک: متن، JSON، ۳۷ بلوک، فریم bbox | PASS |
| 8 | Toast «نتیجهٔ ذخیره‌شدهٔ page_1.png بازیابی شد.» | PASS |
| 9 | حذف: از لیست و از دیسک پاک شد | PASS |

**رگرسیون:** `ui_smoke.py` 36/36 PASS · `ui_bbox_viewer.py` 35/35 PASS → هیچ قابلیت قبلی نشکسته است.

## ۴. شواهد تصویری

`docs/reports/2026-11-15_SavedResults/screenshots/`:
`01_uploaded.png` · `02_ocr_result.png` · `03_saved_in_list.png` · `04_list_after_reload.png` · `05_restored_result.png` · `06_restored_bbox_viewer.png` · `07_after_delete.png`

## ۵. اجرای مجدد

```bash
cd "/home/metadeep-one/projects/documentocr/generalocr /general_ocr-main"
./run_ui.sh                        # UI روی 127.0.0.1:8501 (موتور را هم چک/بالا می‌آورد)
python3 webui/tests/ui_saved_results.py   # تست E2E ذخیره/لیست/بازیابی/حذف
```

## ۶. تغییرات فایل‌ها

| فایل | تغییر |
|---|---|
| `webui/server.py` | + SAVED_ROOT، چهار تابع store، ۴ مسیر API، `do_DELETE` |
| `webui/static/index.html` | + دکمهٔ ذخیره، + کارت نتایج ذخیره‌شده |
| `webui/static/app.js` | + ماژول saved-results (ذخیره/لیست/بازیابی/حذف) |
| `webui/static/styles.css` | + استایل `.saved-row` |
| `webui/tests/ui_saved_results.py` | جدید (تست E2E) |

بکاپ قبل از تغییر: `backups/2026-11-15_pre_saved_results.tar.gz`
پایپ‌لاین OCR، موتور، مدل‌ها و فرمت خروجی: **بدون تغییر**.
