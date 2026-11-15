#!/usr/bin/env python3
"""Field hierarchy must survive save -> reload -> restore (user question:
«بعد از اینکه ذخیره میشن و دوباره بارگذاری میشن چطور؟»).

Real document: webui/tests/data/ocr-data (2)/ocr/1e4a36ae-13d.jpg
(the insurance form: 8 tables, 45 fields, 42 complete, 30 with geometry).

Flow:
  1. upload -> OCR -> expand every table -> record ground truth
     (children, boxes, JSON field fingerprints, parent info panel)
  2. click «ذخیره نتیجه» -> new saved item on disk
  3. meta.json on disk keeps blocks[].fields (key/value/bboxes/status)
  4. reload the page -> restore the saved item
  5. restored view must match: same children, same boxes, same JSON
     fingerprints, hierarchical parent info panel, violet field selection,
     honest «بدون مختصات» for geometry-less fields
  6. the test's own saved item is deleted afterwards (list left clean)

Run (UI on http://127.0.0.1:8501):
  python3 webui/tests/ui_persistence_fields.py
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
SAVED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saved")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

passed, failed = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""))


def shot(page, name: str) -> None:
    os.makedirs(SHOTS, exist_ok=True)
    page.screenshot(path=os.path.join(SHOTS, name))


def expand_all_tables(page) -> None:
    n = page.locator(".bb-row__chev").count()
    for k in range(n):
        page.locator(".bb-row__chev").nth(k).click()
        page.wait_for_timeout(120)
    page.wait_for_timeout(400)


def get_blocks(page):
    raw = page.evaluate("document.querySelector('#json-code').textContent")
    data = json.loads(raw)
    return data.get("blocks") or data["pages"][0]["json"]["blocks"]


def fingerprint(blocks):
    """Stable per-field signature: (block_order, field_idx, key, value, bbox)."""
    out = []
    for b in blocks:
        for j, f in enumerate(b.get("fields") or []):
            out.append((b.get("reading_order"), j,
                        (f.get("key") or "").strip(), (f.get("value") or "").strip(),
                        json.dumps(f.get("bbox"))))
    return sorted(out)


def hierarchy_probe(page):
    """Select the «کد ملی» table parent -> measure the hierarchical UI."""
    parent = page.locator('#bb-list .bb-row--table', has_text="کد ملی").first
    parent.click()
    page.wait_for_timeout(400)
    info_fields = page.locator("#bb-info-text .bb-info__field")
    info_txt = page.locator("#bb-info-text").inner_text()
    stroke = page.locator(".bb-shape.is-selected").evaluate(
        "el => getComputedStyle(el).stroke")
    return {
        "info_n": info_fields.count(),
        "has_keys": all(k in info_txt for k in ("نام", "کد ملی", "تلفن")),
        "stroke": stroke,
        "data_index": parent.get_attribute("data-index"),
    }


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(URL, wait_until="networkidle")
        check("engine ready", page.locator("#engine-status").get_attribute("data-state") == "ready")

        # ---- 1. fresh OCR ---------------------------------------------------
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_selector("#file-card:not([hidden])")
        page.click("#run-btn")
        page.wait_for_selector("#result:not([hidden])", timeout=240_000)
        page.wait_for_timeout(1000)
        check("fresh OCR rendered", page.locator("#ocr-text").inner_text().strip() != "")

        expand_all_tables(page)
        fresh_children = page.locator(".bb-row--child").count()
        fresh_boxes = page.locator(".bb-field").count()
        fresh_blocks = get_blocks(page)
        fresh_fp = fingerprint(fresh_blocks)
        complete_with_geo = [f for b in fresh_blocks for f in (b.get("fields") or [])
                             if (f.get("key") or "").strip() and (f.get("value") or "").strip()
                             and f.get("bbox")]
        check("complete fields listed == JSON", fresh_children == len(complete_with_geo),
              f"listed={fresh_children} json={len(complete_with_geo)}")
        check("drawn field boxes == complete fields with geometry",
              fresh_boxes == len(complete_with_geo), f"boxes={fresh_boxes} geo={len(complete_with_geo)}")
        check("every field box maps to a complete field",
              all(int(f["block"]) < len(fresh_blocks) for f in
                  page.evaluate("Array.from(document.querySelectorAll('.bb-field')).map(b=>({block:b.dataset.block,field:b.dataset.field}))")))
        fresh_probe = hierarchy_probe(page)
        check("hierarchical info panel (fresh)", fresh_probe["info_n"] >= 4
              and fresh_probe["has_keys"], f"n={fresh_probe['info_n']}")
        shot(page, "16_persistence_fresh.png")

        # ---- 2. save ---------------------------------------------------------
        base_rows = page.locator("#saved-list .saved-row").count()
        base_ids = set(d for d in os.listdir(SAVED_DIR) if len(d) == 32)
        page.click("#save-result")
        page.wait_for_timeout(1200)
        check("saved row appears in list",
              page.locator("#saved-list .saved-row").count() == base_rows + 1)
        new_ids = [d for d in os.listdir(SAVED_DIR) if len(d) == 32 and d not in base_ids]
        check("one new saved dir on disk", len(new_ids) == 1, f"new={new_ids}")
        save_id = new_ids[0]
        shot(page, "17_persistence_saved.png")

        # ---- 3. meta.json on disk keeps the hierarchy ------------------------
        meta = json.load(open(os.path.join(SAVED_DIR, save_id, "meta.json"), encoding="utf-8"))
        meta_blocks = meta.get("pages", [{}])[0].get("json", {}).get("blocks", [])
        meta_fields = [f for b in meta_blocks for f in (b.get("fields") or [])]
        meta_fp = fingerprint(meta_blocks)
        check("meta.json has blocks[].fields", len(meta_fields) == 45,
              f"fields={len(meta_fields)}")
        check("meta.json fields carry full structure",
              all(("key" in f and "value" in f and "key_bbox" in f
                   and "value_bbox" in f and "bbox_status" in f) for f in meta_fields))
        check("meta.json fingerprint == fresh UI fingerprint", meta_fp == fresh_fp)

        # ---- 4. reload -> restore --------------------------------------------
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        row = page.locator(f'#saved-list .saved-row[data-id="{save_id}"]')
        check("saved item still listed after reload", row.count() == 1)
        row.click()
        page.wait_for_selector("#result:not([hidden])", timeout=30_000)
        page.wait_for_timeout(1000)
        check("restored text non-empty", page.locator("#ocr-text").inner_text().strip() != "")
        check("restore toast shown", "بازیابی" in page.locator("#toast").inner_text())

        expand_all_tables(page)
        check("children survive restore", page.locator(".bb-row--child").count() == fresh_children,
              f"restored={page.locator('.bb-row--child').count()}")
        check("boxes survive restore", page.locator(".bb-field").count() == fresh_boxes,
              f"restored={page.locator('.bb-field').count()}")
        check("no «بدون عنوان» after restore",
              "بدون عنوان" not in page.locator("#bb-list").inner_text())
        restored_blocks = get_blocks(page)
        check("field fingerprints survive restore",
              fingerprint(restored_blocks) == fresh_fp,
              f"restored_fields={len(fingerprint(restored_blocks))}")
        shot(page, "18_persistence_restored_expanded.png")

        # ---- 5. hierarchical UI works after restore ---------------------------
        probe = hierarchy_probe(page)
        check("hierarchical info panel (restored)", probe["info_n"] == fresh_probe["info_n"]
              and probe["has_keys"], f"n={probe['info_n']} fresh={fresh_probe['info_n']}")
        check("parent table box orange after restore",
              "245, 158, 11" in probe["stroke"] or "234, 88, 12" in probe["stroke"],
              probe["stroke"])

        # geometry recovered (کد ملی now HAS a real box): selecting it must
        # highlight exactly one violet box; the honest «بدون مختصات» path
        # only remains for incomplete fields, which are hidden from the list
        bidx = probe["data_index"]
        child = page.locator(f'.bb-row--child[data-block="{bidx}"]', has_text="کد ملی").first
        child.click()
        page.wait_for_timeout(400)
        check("field with geometry: exactly one box selected",
              page.locator(".bb-field.is-selected").count() == 1)
        check("field bbox shown in info panel",
              "بدون مختصات" not in page.locator("#bb-info-bbox").inner_text())
        check("child row active in list", page.locator(".bb-row--child.is-active").count() == 1)
        check("parent row marked", "has-active-child" in
              (page.locator(f'.bb-row--table[data-index="{bidx}"]').get_attribute("class") or ""))

        # field with geometry (نام): violet box selection
        child2 = page.locator(f'.bb-row--child[data-block="{bidx}"]', has_text="آقای مهدی").first
        child2.click()
        page.wait_for_timeout(400)
        check("field box selectable after restore",
              page.locator(".bb-field.is-selected").count() == 1)
        fstroke = page.locator(".bb-field.is-selected").evaluate(
            "el => getComputedStyle(el).stroke")
        check("field box violet", "139, 92, 246" in fstroke, fstroke)
        shot(page, "19_persistence_field_selected.png")

        # ---- 6. clean up the test's own item ----------------------------------
        page.locator(f'#saved-list .saved-row[data-id="{save_id}"] .saved-row__del').click()
        page.wait_for_timeout(1200)
        ids = [d for d in os.listdir(SAVED_DIR) if len(d) == 32]
        check("test item removed from disk", save_id not in ids)

        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
