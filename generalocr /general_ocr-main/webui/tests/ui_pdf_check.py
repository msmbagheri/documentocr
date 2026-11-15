#!/usr/bin/env python3
"""Verify multi-page PDF support in the DocumentOCR UI (real pipeline).

The PDF is split by the project's existing ``pdf_utils.pdf_to_images`` and
every page goes through the same Surya 2.5 + llama.cpp pipeline as images.

Run:
  python3 webui/tests/ui_pdf_check.py
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # .../documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-14_webui", "screenshots")
PDF = os.path.join(ROOT, "webui", "tests", "data", "sample_2pages.pdf")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    if not os.path.isfile(PDF):
        print(f"pdf missing: {PDF}")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 980})
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(800)

        page.set_input_files("#file-input", PDF)
        page.wait_for_timeout(900)
        check("نام فایل PDF نمایش داده می‌شود", "sample_2pages" in page.locator("#file-name").inner_text())
        check("پیش‌نمایش PDF فعال می‌شود", page.locator("#preview-pdf").is_visible())

        page.locator("#run-btn").click()
        page.wait_for_selector("#result:not([hidden])", timeout=300_000)
        page.wait_for_timeout(2500)

        badge = page.locator("#result-badge").inner_text()
        check("نشان «۲ صفحه پردازش شد» نمایش داده می‌شود", "۲" in badge and "صفحه" in badge, badge)

        tabs = page.locator(".page-tab")
        check("تب‌های صفحه ساخته می‌شوند", tabs.count() == 2, f"{tabs.count()} tabs")

        text1 = page.locator("#ocr-text").inner_text()
        check("متن صفحهٔ ۱ استخراج شده است", "آزمون سراسری" in text1, f"{len(text1)} chars")

        tabs.nth(1).click()
        page.wait_for_timeout(900)
        text2 = page.locator("#ocr-text").inner_text()
        check("متن صفحهٔ ۲ استخراج شده است", len(text2) > 200 and "OCR Research" in text2, f"{len(text2)} chars")
        check("تعویض صفحه متن را عوض می‌کند", text1 != text2)

        stats = page.locator(".stat").count()
        check("اطلاعات پردازش صفحهٔ ۲ به‌روز شد", stats >= 5, f"{stats} stats")

        page.screenshot(path=os.path.join(SHOTS, "09_pdf_two_pages_result.png"), full_page=True)
        print("saved 09_pdf_two_pages_result.png")
        ctx.close()
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
