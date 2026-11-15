#!/usr/bin/env python3
"""Capture the DocumentOCR UI screenshots required by the mission.

Uses the globally installed Playwright (no new project dependency) and the
chromium already cached in ~/.cache/ms-playwright.

Preconditions:
  * web UI running on http://127.0.0.1:8501  (./run_ui.sh)
  * llama.cpp engine running on 127.0.0.1:8080

Run:
  python3 webui/tests/ui_screenshots.py

Output (all inside the project reports folder):
  docs/reports/2026-11-14_webui/screenshots/
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # .../documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-14_webui", "screenshots")
SAMPLE = os.path.join(PROJECT, "output_konkour", "images", "page_1.png")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")


def shot(page, name: str, full_page: bool = False) -> str:
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path, full_page=full_page)
    print(f"saved {path}")
    return path


def unstick(page) -> None:
    """Neutralise the sticky header.

    Chromium renders a ``position: sticky`` header at its scrolled position
    inside a full-page screenshot, which looks like a duplicated header in the
    middle of the document. Freezing it for the capture keeps the evidence
    screenshots faithful to what the user actually sees.
    """
    page.add_style_tag(content=".topbar { position: static !important; }")


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    if not os.path.isfile(SAMPLE):
        print(f"sample missing: {SAMPLE}")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ----------------------------- desktop -----------------------------
        ctx = browser.new_context(viewport={"width": 1440, "height": 980}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(900)
        shot(page, "01_initial_desktop.png", full_page=True)

        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_timeout(800)
        shot(page, "02_file_selected_desktop.png", full_page=True)

        page.locator("#run-btn").click()
        page.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page.wait_for_timeout(3400)  # let the transient toast fade
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(300)
        shot(page, "03_result_desktop_viewport.png")

        # element screenshots (scroll into view automatically -> no clip bugs)
        page.locator("#result .card").nth(0).screenshot(
            path=os.path.join(SHOTS, "04_result_text_card.png")
        )
        print("saved 04_result_text_card.png")
        page.locator("#json-view").screenshot(path=os.path.join(SHOTS, "05_result_json_panel.png"))
        print("saved 05_result_json_panel.png")

        unstick(page)
        shot(page, "06_result_desktop_full.png", full_page=True)
        ctx.close()

        # ----------------------------- mobile ------------------------------
        ctx2 = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page2 = ctx2.new_page()
        page2.goto(URL, wait_until="networkidle")
        page2.wait_for_timeout(900)
        shot(page2, "07_mobile_initial.png", full_page=True)

        page2.set_input_files("#file-input", SAMPLE)
        page2.wait_for_timeout(800)
        page2.locator("#run-btn").click()
        page2.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page2.wait_for_timeout(3400)
        unstick(page2)
        shot(page2, "08_mobile_result_full.png", full_page=True)
        ctx2.close()

        browser.close()

    print("\nall screenshots written to", SHOTS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
