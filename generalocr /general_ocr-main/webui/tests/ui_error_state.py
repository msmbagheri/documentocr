#!/usr/bin/env python3
"""Verify the DocumentOCR UI error handling when the OCR engine is down.

Two real scenarios are exercised against the running UI (no mocking):

  A) the engine is already down when the page loads
       -> header badge must show "در دسترس نیست", the alert box must be
          visible with a human-readable Persian message and the OCR button
          must be disabled.

  B) the engine dies *after* the page was loaded and a file was selected
       -> clicking "شروع OCR" must surface a friendly error (not a raw
          stack trace, and not an empty "success" result).

The llama.cpp container is always restarted in a finally block, so the
project is left exactly as it was found.

Run:
  python3 webui/tests/ui_error_state.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # .../documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-14_webui", "screenshots")
SAMPLE = os.path.join(PROJECT, "output_konkour", "images", "page_1.png")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")
HEALTH = os.environ.get("ENGINE_HEALTH", "http://127.0.0.1:8080/health")
CONTAINER = os.environ.get("ENGINE_CONTAINER", "surya-llama")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def engine_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as r:
            return r.status == 200 and json.loads(r.read().decode() or "{}").get("status") == "ok"
    except Exception:
        return False


def stop_engine() -> None:
    subprocess.run(["docker", "stop", CONTAINER], check=False, capture_output=True)


def start_engine() -> bool:
    subprocess.run(["docker", "start", CONTAINER], check=False, capture_output=True)
    for _ in range(90):
        if engine_up():
            return True
        time.sleep(2)
    return False


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    if not engine_up():
        print("engine is not running — start it first (./run_ui.sh)")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            # ------------------------------------------------------------------
            # A) engine down before the page is opened
            # ------------------------------------------------------------------
            stop_engine()
            time.sleep(1)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(URL, wait_until="networkidle")
            page.wait_for_timeout(2500)

            state = page.locator("#engine-status").get_attribute("data-state")
            check("A. موتور در سربرگ «در دسترس نیست» نشان داده می‌شود", state == "offline", f"data-state={state}")
            check("A. برچسب وضعیت موتور درست است",
                  "در دسترس نیست" in page.locator("#engine-value").inner_text(),
                  page.locator("#engine-value").inner_text())
            check("A. کادر خطا نمایش داده می‌شود", page.locator("#error-box").is_visible())
            title = page.locator("#error-title").inner_text().strip()
            check("A. پیام خطا قابل فهم و فارسی است", "در دسترس نیست" in title, title)
            check("A. دکمه OCR غیرفعال است", page.locator("#run-btn").is_disabled())
            page.screenshot(path=os.path.join(SHOTS, "10_engine_down_at_load.png"), full_page=True)
            print("saved 10_engine_down_at_load.png")
            ctx.close()

            # ------------------------------------------------------------------
            # B) engine dies while the page is open (real request failure)
            # ------------------------------------------------------------------
            start_engine()
            time.sleep(1)
            ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
            page2 = ctx2.new_page()
            page2.goto(URL, wait_until="networkidle")
            page2.wait_for_timeout(1200)
            page2.set_input_files("#file-input", SAMPLE)
            page2.wait_for_timeout(600)
            check("B. دکمه OCR در حالت سالم فعال است", page2.locator("#run-btn").is_enabled())

            stop_engine()  # engine dies right before the request
            page2.locator("#run-btn").click()
            page2.wait_for_selector("#error-box:not([hidden])", timeout=60_000)
            page2.wait_for_timeout(600)

            title2 = page2.locator("#error-title").inner_text().strip()
            check("B. خطای قطع سرور با پیام فارسی نشان داده می‌شود",
                  "در دسترس نیست" in title2, title2)
            check("B. نتیجه خالی به‌عنوان موفقیت نمایش داده نمی‌شود",
                  page2.locator("#result").is_hidden())
            hint = page2.locator("#error-hint").inner_text().strip()
            check("B. راهنمای عملی برای کاربر نمایش داده می‌شود", len(hint) > 10, hint)
            page2.screenshot(path=os.path.join(SHOTS, "11_engine_down_mid_request.png"), full_page=True)
            print("saved 11_engine_down_mid_request.png")

            # the engine comes back -> the UI must recover by itself (health poll)
            start_engine()
            page2.wait_for_function(
                "() => document.getElementById('engine-status').dataset.state === 'ready'",
                timeout=45_000,
            )
            check("B. پس از بازگشت سرویس، وضعیت موتور «آماده به کار» می‌شود",
                  page2.locator("#engine-status").get_attribute("data-state") == "ready")
            page2.wait_for_function(
                "() => !document.getElementById('run-btn').disabled", timeout=30_000
            )
            check("B. پس از بازگشت سرویس، دکمه OCR دوباره فعال می‌شود (تلاش مجدد)",
                  page2.locator("#run-btn").is_enabled())
            ctx2.close()
        finally:
            browser.close()
            print("restarting engine ...")
            ok = start_engine()
            check("موتور پس از تست دوباره در دسترس است", ok)

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
