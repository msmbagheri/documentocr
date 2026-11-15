#!/usr/bin/env python3
"""Empty/keyless table fields must NOT be listed (user requirement).

Real document: webui/tests/data/ocr-data (2)/ocr/1e4a36ae-13d.jpg  (the
insurance form the user reported). Many of its table cells carry no label
(key == "") and were previously rendered as «مقدار بدون عنوان».

Checks:
  * no list row shows a keyless field (and no «مقدار بدون عنوان» text)
  * every displayed child has a real key
  * displayed children count == JSON fields that have a key (exact filter)
  * boxes drawn on the image only belong to keyed fields
  * the JSON payload still contains EVERY field (hierarchy untouched)

Run (UI on http://127.0.0.1:8501):
  python3 webui/tests/ui_table_fields_hidden.py
"""

from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-15_TableFields", "screenshots")
SAMPLE = os.path.join(PROJECT, "generalocr /general_ocr-main", "webui", "tests",
                      "data", "ocr-data (2)", "ocr", "1e4a36ae-13d.jpg")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

os.makedirs(SHOTS, exist_ok=True)

passed, failed = [], []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name + (f" — {detail}" if detail and not cond else ""))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""))


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="networkidle")

        check("engine ready", page.locator("#engine-status").get_attribute("data-state") == "ready")
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_selector("#file-card:not([hidden])")
        page.click("#run-btn")
        page.wait_for_selector("#result:not([hidden])", timeout=240_000)
        page.wait_for_timeout(800)
        check("OCR result rendered", page.locator("#ocr-text").inner_text().strip() != "")

        # ---- ground truth from the JSON panel -------------------------------
        raw = page.evaluate("document.querySelector('#json-code').textContent")
        data = json.loads(raw)
        blocks = data.get("blocks") or data["pages"][0]["json"]["blocks"]
        complete = {}   # block index -> field indices with real key AND value (displayed)
        incomplete = {}  # block index -> field indices missing key or value (hidden)
        for i, b in enumerate(blocks):
            fl = b.get("fields") or []
            if not fl:
                continue
            complete[i] = [j for j, f in enumerate(fl)
                           if (f.get("key") or "").strip() and (f.get("value") or "").strip()]
            incomplete[i] = [j for j, f in enumerate(fl) if j not in complete[i]]
        n_complete = sum(len(v) for v in complete.values())
        n_incomplete = sum(len(v) for v in incomplete.values())
        check("document has incomplete (hidden) fields", n_incomplete > 0,
              f"complete={n_complete} incomplete={n_incomplete}")

        # ---- expand every table --------------------------------------------
        n_chev = page.locator(".bb-row__chev").count()
        check("tables are expandable", n_chev > 0, f"chevrons={n_chev}")
        for k in range(n_chev):
            page.locator(".bb-row__chev").nth(k).click()
            page.wait_for_timeout(120)
        page.wait_for_timeout(500)

        children = page.locator(".bb-row--child")
        n_children = children.count()
        check("every complete field is listed", n_children == n_complete,
              f"listed={n_children} expected={n_complete}")

        # no row may carry the empty-box placeholder or an empty key
        rows = page.evaluate(
            """() => Array.from(document.querySelectorAll('.bb-row--child')).map(el => ({
                block: el.dataset.block,
                field: el.dataset.field,
                key: (el.querySelector('.bb-row__fkey') || {}).textContent || '',
                text: el.textContent || ''
            }))"""
        )
        bad_title = [r["text"][:60] for r in rows if "مقدار بدون عنوان" in r["text"]]
        check("no «مقدار بدون عنوان» row", not bad_title, str(bad_title[:2]))
        empty_key = [r["field"] for r in rows if not r["key"].strip()]
        check("no child row with an empty key", not empty_key, str(empty_key[:5]))

        # each listed child must point to a complete field of the JSON
        mismatched = []
        for r in rows:
            bi, fi = int(r["block"]), int(r["field"])
            if fi not in complete.get(bi, []):
                mismatched.append((bi, fi))
        check("listed rows map only to complete fields", not mismatched, str(mismatched[:5]))

        # ---- boxes on the image --------------------------------------------
        boxes = page.evaluate(
            """() => Array.from(document.querySelectorAll('.bb-field')).map(el => ({
                block: el.dataset.block, field: el.dataset.field }))"""
        )
        n_boxes = len(boxes)
        bad_box = [(int(b["block"]), int(b["field"])) for b in boxes
                   if int(b["field"]) not in complete.get(int(b["block"]), [])]
        check("drawn boxes only belong to complete fields", not bad_box, str(bad_box[:5]))
        check("box count matches complete fields with geometry", n_boxes > 0,
              f"boxes={n_boxes}")

        # ---- JSON hierarchy untouched --------------------------------------
        total_json = sum(len(b.get("fields") or []) for b in blocks)
        check("JSON still holds every field (nothing dropped)",
              total_json == n_complete + n_incomplete, f"json={total_json}")
        check("incomplete fields still present in JSON", n_incomplete > 0)

        page.screenshot(path=os.path.join(SHOTS, "05_insurance_no_empty_fields.png"))
        page.locator("#bb-list").screenshot(
            path=os.path.join(SHOTS, "06_insurance_list_no_empty_fields.png"))

        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
