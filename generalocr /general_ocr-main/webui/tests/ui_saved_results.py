#!/usr/bin/env python3
"""End-to-end Playwright test: save OCR result -> list -> restore -> delete.

Real pipeline, no mocks. Verifies the user flow:
  1. upload a real document image
  2. run OCR -> result renders
  3. click "ذخیره نتیجه" -> item appears in the saved list (server-side file)
  4. reload the page -> the saved list still shows the item (persistence)
  5. click the saved row -> full result renders again (text + JSON + bbox viewer)
  6. delete -> item disappears from the list and from disk

Run (UI on http://127.0.0.1:8501):
  python3 webui/tests/ui_saved_results.py
"""

from __future__ import annotations

import os
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # …/documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-15_SavedResults", "screenshots")
SAMPLE = os.path.join(PROJECT, "output_konkour", "images", "page_1.png")
SAVED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saved")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

os.makedirs(SHOTS, exist_ok=True)

passed, failed = [], []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name + (f" — {detail}" if detail and not cond else ""))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""))


def shot(page, name: str):
    page.screenshot(path=os.path.join(SHOTS, name), full_page=False)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="networkidle")

        # -- 1. upload + OCR ------------------------------------------------
        check("engine ready badge", page.locator("#engine-status").get_attribute("data-state") == "ready")
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_selector("#file-card:not([hidden])")
        shot(page, "01_uploaded.png")

        page.click("#run-btn")
        page.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page.wait_for_timeout(800)
        check("OCR result rendered", page.locator("#ocr-text").inner_text().strip() != "")
        check("save button enabled after OCR", page.locator("#save-result").is_enabled())
        shot(page, "02_ocr_result.png")

        # -- 2. save ---------------------------------------------------------
        # The saved list may already contain the user's own results: every
        # count below is relative to that baseline (nothing is ever purged).
        base_rows = page.locator("#saved-list .saved-row").count()
        base_ids = set(d for d in os.listdir(SAVED_DIR) if len(d) == 32)
        page.click("#save-result")
        page.wait_for_timeout(1200)
        rows = page.locator("#saved-list .saved-row")
        check("saved row appears in list", rows.count() == base_rows + 1, f"count={rows.count()}")
        check("save button re-enabled", page.locator("#save-result").is_enabled())
        shot(page, "03_saved_in_list.png")

        # server-side artifact really on disk
        ids = [d for d in os.listdir(SAVED_DIR) if len(d) == 32]
        new_ids = [d for d in ids if d not in base_ids]
        check("saved dir exists on disk", len(new_ids) == 1, f"new={new_ids} all={ids}")
        check("meta.json on disk", bool(new_ids) and os.path.isfile(
            os.path.join(SAVED_DIR, new_ids[0], "meta.json")))

        # -- 3. persistence across reload ------------------------------------
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        rows = page.locator("#saved-list .saved-row")
        check("list persists after reload", rows.count() == base_rows + 1, f"count={rows.count()}")
        shot(page, "04_list_after_reload.png")

        # -- 4. restore -------------------------------------------------------
        rows.first.click()
        page.wait_for_selector("#result:not([hidden])", timeout=30_000)
        page.wait_for_timeout(1000)
        text = page.locator("#ocr-text").inner_text().strip()
        check("restored text non-empty", text != "")
        check("restored JSON present", "input_path" in page.locator("#json-code").inner_text())
        bb_rows = page.locator("#bb-list .bb-row")
        check("restored bbox viewer blocks", bb_rows.count() > 0, f"blocks={bb_rows.count()}")
        frame_hidden = page.locator("#bb-frame").get_attribute("hidden")
        check("bbox frame visible", frame_hidden is None)
        toast_text = page.locator("#toast").inner_text()
        check("restore toast shown", "بازیابی" in toast_text, toast_text)
        shot(page, "05_restored_result.png")
        # scroll to the bbox viewer for evidence
        page.locator("#bb-stage").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        shot(page, "06_restored_bbox_viewer.png")

        # -- 5. delete ---------------------------------------------------------
        page.locator("#saved-list .saved-row .saved-row__del").first.click()
        page.wait_for_timeout(1200)
        rows = page.locator("#saved-list .saved-row")
        check("row removed from list after delete", rows.count() == base_rows,
              f"count={rows.count()} base={base_rows}")
        ids = [d for d in os.listdir(SAVED_DIR) if len(d) == 32]
        check("dir removed from disk", set(ids) == base_ids, f"ids={ids}")
        shot(page, "07_after_delete.png")

        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
