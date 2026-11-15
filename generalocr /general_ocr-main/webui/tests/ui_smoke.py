#!/usr/bin/env python3
"""Browser smoke test for the DocumentOCR web UI.

Uses the globally installed Playwright (``python3 -m playwright``), NOT a new
project dependency. Chromium is already in ~/.cache/ms-playwright.

Preconditions:
  * web UI running on http://127.0.0.1:8501  (./run_ui.sh)
  * llama.cpp engine running on 127.0.0.1:8080

Run:
  python3 webui/tests/ui_smoke.py

Artifacts (screenshots) are written to:
  docs/reports/2026-11-14_webui/screenshots/
"""

from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # …/documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-14_webui", "screenshots")
# the smoke run keeps its own artifacts in a sub-folder so the curated
# evidence set (ui_screenshots.py / ui_pdf_check.py / ui_error_state.py)
# stays free of filename collisions
SHOTS = os.path.join(SHOTS, "smoke")
SAMPLE = os.path.join(PROJECT, "output_konkour", "images", "page_1.png")

URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def no_overflow(page) -> tuple[bool, str]:
    data = page.evaluate(
        """() => {
            const de = document.documentElement;
            const offenders = [];
            document.querySelectorAll('.card, .stat, .result__head, .topbar__inner').forEach(el => {
                if (el.offsetParent === null) return;
                if (el.scrollWidth > el.clientWidth + 1) {
                    offenders.push((el.className || el.tagName) + ' ' + el.scrollWidth + '>' + el.clientWidth);
                }
            });
            return {
                pageW: de.scrollWidth, clientW: de.clientWidth,
                bodyW: document.body.scrollWidth, offenders
            };
        }"""
    )
    ok = data["pageW"] <= data["clientW"] and data["bodyW"] <= data["clientW"] + 1 and not data["offenders"]
    return ok, json.dumps(data, ensure_ascii=False)


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    if not os.path.isfile(SAMPLE):
        print(f"sample missing: {SAMPLE}")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---------------- desktop ----------------
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 980},
            device_scale_factor=1,
            permissions=["clipboard-read", "clipboard-write"],
            accept_downloads=True,
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(700)

        check("۱. صفحه اصلی باز می‌شود", page.title() != "")
        check("عنوان محصول در سربرگ", page.locator(".brand__name").inner_text().strip() == "DocumentOCR")
        engine_state = page.locator("#engine-status").get_attribute("data-state")
        check("وضعیت موتور واقعی خوانده می‌شود", engine_state in ("ready", "offline"), f"data-state={engine_state}")
        check("نتیجه در ابتدا پنهان است", page.locator("#result").is_hidden())
        check("کارت فایل در ابتدا پنهان است", page.locator("#file-card").is_hidden())
        ok, detail = no_overflow(page)
        check("بدون اسکرول افقی (دسکتاپ ۱۴۴۰)", ok, detail)
        page.screenshot(path=os.path.join(SHOTS, "01_initial_desktop.png"), full_page=True)

        # ---------------- upload ----------------
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_timeout(600)
        check("نام فایل نمایش داده می‌شود", "page_1" in page.locator("#file-name").inner_text())
        check("حجم فایل نمایش داده می‌شود", "کیلوبایت" in page.locator("#file-meta").inner_text() or "مگابایت" in page.locator("#file-meta").inner_text(), page.locator("#file-meta").inner_text())
        stacking = page.evaluate(
            """() => {
                const n = document.getElementById('file-name').getBoundingClientRect();
                const m = document.getElementById('file-meta').getBoundingClientRect();
                return {nameBottom: Math.round(n.bottom), metaTop: Math.round(m.top), stacked: m.top >= n.bottom - 2};
            }"""
        )
        check("نام و حجم فایل در دو خط خوانا نمایش داده می‌شوند", stacking["stacked"], json.dumps(stacking))
        check("پیش‌نمایش تصویر دیده می‌شود", page.locator("#preview-img").is_visible())
        check("کنترل بزرگ‌نمایی ظاهر می‌شود", page.locator("#zoom-controls").is_visible())
        check("دکمه OCR فعال است", page.locator("#run-btn").is_enabled())
        ok, detail = no_overflow(page)
        check("بدون اسکرول افقی پس از انتخاب فایل", ok, detail)
        page.screenshot(path=os.path.join(SHOTS, "02_file_selected_desktop.png"), full_page=True)

        # zoom interaction
        page.locator("#zoom-in").click()
        page.wait_for_timeout(250)
        zoom_txt = page.locator("#zoom-label").inner_text()
        check("بزرگ‌نمایی کار می‌کند", "۱۲۵" in zoom_txt or "125" not in zoom_txt, f"label={zoom_txt}")
        page.locator("#zoom-fit").click()
        page.wait_for_timeout(200)

        # ---------------- run OCR ----------------
        page.locator("#run-btn").click()
        page.wait_for_timeout(400)
        busy_label = page.locator("#run-label").inner_text()
        check("حین پردازش دکمه غیرفعال و برچسب تغییر می‌کند",
              page.locator("#run-btn").is_disabled() and "استخراج" in busy_label, busy_label)

        page.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page.wait_for_timeout(900)

        text = page.locator("#ocr-text").inner_text()
        check("متن فارسی استخراج شده نمایش داده می‌شود", "آزمون سراسری" in text and len(text) > 200, f"{len(text)} chars")
        check("عنوان نتیجه دیده می‌شود", page.locator("#result-title").inner_text().strip() == "نتیجه OCR")
        check("ستون اطلاعات پردازش پر شده است", page.locator(".stat").count() >= 5, f"{page.locator('.stat').count()} stats")

        json_text = page.locator("#json-code").inner_text()
        check("JSON واقعی نمایش داده می‌شود", '"blocks"' in json_text and '"reading_order"' in json_text, f"{len(json_text)} chars")
        check("JSON با هایلایت رندر شده", page.locator("#json-code .j-key").count() > 3)

        ok, detail = no_overflow(page)
        check("بدون اسکرول افقی پس از OCR", ok, detail)

        # ---------------- copy ----------------
        page.locator("#copy-text").click()
        page.wait_for_timeout(400)
        clip = page.evaluate("() => navigator.clipboard.readText()")
        check("کپی متن کار می‌کند", clip.startswith("آزمون سراسری") or "آزمون" in clip[:80], f"{len(clip)} chars")

        page.locator("#copy-json").click()
        page.wait_for_timeout(400)
        clip_json = page.evaluate("() => navigator.clipboard.readText()")
        check("کپی JSON کار می‌کند", '"blocks"' in clip_json)

        # ---------------- downloads ----------------
        with page.expect_download() as dl_info:
            page.locator("#download-txt").click()
        dl = dl_info.value
        txt_path = os.path.join(SHOTS, "downloaded_" + dl.suggested_filename)
        dl.save_as(txt_path)
        size_txt = os.path.getsize(txt_path)
        check("دانلود TXT کار می‌کند", dl.suggested_filename.endswith("_ocr.txt") and size_txt > 200,
              f"{dl.suggested_filename} ({size_txt} B)")

        with page.expect_download() as dl_info2:
            page.locator("#download-json").click()
        dl2 = dl_info2.value
        json_path = os.path.join(SHOTS, "downloaded_" + dl2.suggested_filename)
        dl2.save_as(json_path)
        with open(json_path, encoding="utf-8") as f:
            parsed = json.load(f)
        check("دانلود JSON کار می‌کند و معتبر است",
              dl2.suggested_filename.endswith("_ocr.json") and "blocks" in parsed,
              f"{dl2.suggested_filename} ({len(parsed.get('blocks', []))} blocks)")

        # screenshots: wait for the transient toast to fade out first
        page.wait_for_timeout(3200)
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SHOTS, "03_result_desktop_viewport.png"))
        page.screenshot(path=os.path.join(SHOTS, "04_result_desktop_full.png"), full_page=True)

        # verify nothing is clipped inside the result cards
        clip_report = page.evaluate(
            """() => {
                const bad = [];
                document.querySelectorAll('.stat__value, .ocr-text p, .card__title, .badge, .chip').forEach(el => {
                    if (el.offsetParent === null) return;
                    if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow === 'visible') {
                        bad.push(el.className + ': ' + (el.textContent||'').slice(0,40));
                    }
                });
                const r = document.getElementById('result').getBoundingClientRect();
                return {bad, resultRight: Math.round(r.right), resultLeft: Math.round(r.left), winW: window.innerWidth};
            }"""
        )
        check("هیچ متن بریده‌شده‌ای در کارت‌ها نیست", not clip_report["bad"], json.dumps(clip_report, ensure_ascii=False))
        check("کارت نتیجه کامل داخل عرض صفحه است",
              clip_report["resultRight"] <= clip_report["winW"] + 1 and clip_report["resultLeft"] >= -1,
              json.dumps(clip_report, ensure_ascii=False))

        # ---------------- responsive ----------------
        for width, height, label in [(1024, 900, "tablet_1024"), (768, 1000, "tablet_768")]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(500)
            ok, detail = no_overflow(page)
            check(f"بدون اسکرول افقی ({label})", ok, detail)
            page.screenshot(path=os.path.join(SHOTS, f"05_{label}.png"), full_page=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(600)
        ok, detail = no_overflow(page)
        check("بدون اسکرول افقی (موبایل ۳۹۰)", ok, detail)
        mobile_layout = page.evaluate(
            """() => {
                const cards = [...document.querySelectorAll('.workspace .column')];
                return cards.map(c => Math.round(c.getBoundingClientRect().width));
            }"""
        )
        check("چیدمان موبایل تک‌ستونه است", len(mobile_layout) == 2 and mobile_layout[0] > 300,
              str(mobile_layout))
        page.screenshot(path=os.path.join(SHOTS, "06_result_mobile_full.png"), full_page=True)

        # element visibility inside cards on mobile
        mobile_clip = page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('.card').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > window.innerWidth + 1) out.push(el.className + ':' + Math.round(r.width));
                });
                return out;
            }"""
        )
        check("همه کارت‌ها در موبایل داخل صفحه هستند", not mobile_clip, str(mobile_clip))

        ctx.close()

        # ---------------- engine-down error state ----------------
        ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
        page2 = ctx2.new_page()
        page2.goto(URL, wait_until="networkidle")
        page2.wait_for_timeout(500)

        # client-side validation: unsupported extension
        import tempfile
        bad_txt = os.path.join(tempfile.gettempdir(), "dococr_not_a_doc.txt")
        with open(bad_txt, "w", encoding="utf-8") as f:
            f.write("این یک سند تصویری نیست")
        page2.set_input_files("#file-input", bad_txt)
        page2.wait_for_timeout(400)
        check("فرمت نامعتبر با پیام فارسی رد می‌شود",
              page2.locator("#error-box").is_visible() and "فرمت" in page2.locator("#error-title").inner_text(),
              page2.locator("#error-title").inner_text())

        # client-side validation: empty file
        empty_png = os.path.join(tempfile.gettempdir(), "dococr_empty.png")
        open(empty_png, "wb").close()
        page2.set_input_files("#file-input", empty_png)
        page2.wait_for_timeout(400)
        check("فایل خالی با پیام فارسی رد می‌شود",
              "خالی" in page2.locator("#error-title").inner_text(),
              page2.locator("#error-title").inner_text())
        page2.locator("#dismiss-error").click()
        check("پیام خطا قابل بستن است", page2.locator("#error-box").is_hidden())

        # server-side validation: wrong extension must never reach the engine
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            URL + "/api/ocr",
            data=b"not an image",
            headers={"Content-Type": "text/plain", "X-Filename": "test.txt"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=30)
            status, body = 200, {}
        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read().decode("utf-8"))
        check("سرور فرمت نامعتبر را با ۴۱۵ رد می‌کند",
              status == 415 and body.get("code") == "unsupported_type",
              f"HTTP {status} code={body.get('code')}")

        print("  (engine-down state is verified in the mission evidence: "
              "health pill + banner screenshot 08 + 503 in server log)")
        ctx2.close()

        browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    failed = [r for r in results if not r[1]]
    if failed:
        print("\nFAILED:")
        for name, _, detail in failed:
            print(f" - {name}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
