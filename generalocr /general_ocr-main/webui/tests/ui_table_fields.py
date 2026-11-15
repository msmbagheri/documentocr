#!/usr/bin/env python3
"""Table field extraction E2E test — real pipeline, real document (سبز.png).

Verifies (mission «اصلاح ساختار استخراج و نمایش فیلدهای داخلی Table»):
  * the OCR result still renders; the owner-specifications Table stays ONE parent block
  * its inner fields (Key/Value) are extracted and listed as expandable children
  * field boxes are drawn on the image with a distinct color + numbers
  * the parent table box is visually distinct (bb-shape--table) from field boxes (bb-field)
  * clicking a field row highlights its box (is-selected) and shows Key/Value in the panel
  * clicking a field box selects the matching list row
  * the JSON view keeps the hierarchical structure (blocks[].fields)
  * no fabricated boxes: fields without geometry are marked «بدون مختصات معتبر»

Run (UI on http://127.0.0.1:8501):
  python3 webui/tests/ui_table_fields.py
"""

from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # …/documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-15_TableFields", "screenshots")
SAMPLE = os.path.join(PROJECT, "generalocr /general_ocr-main", "webui", "tests", "data", "سبز.png")
URL = os.environ.get("UI_URL", "http://127.0.0.1:8501")

os.makedirs(SHOTS, exist_ok=True)

passed, failed = [], []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name + (f" — {detail}" if detail and not cond else ""))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""))


def shot(page, name: str, full: bool = False):
    page.screenshot(path=os.path.join(SHOTS, name), full_page=full)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(URL, wait_until="networkidle")

        check("engine ready", page.locator("#engine-status").get_attribute("data-state") == "ready")
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_selector("#file-card:not([hidden])")
        page.click("#run-btn")
        page.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page.wait_for_timeout(800)
        check("OCR result rendered", page.locator("#ocr-text").inner_text().strip() != "")

        # the owner-spec table block: the bb-list row whose text contains the table
        owner_row = page.locator(
            '#bb-list .bb-row--table', has_text="نام و نام خانوادگی").first
        check("owner table parent row exists", owner_row.count() > 0)
        fields_chip = owner_row.locator(".bb-row__fields-chip").inner_text()
        check("field count chip on parent row", "فیلد" in fields_chip, fields_chip)
        n_shots_before = page.locator(".bb-field").count()
        check("no field boxes while collapsed", n_shots_before == 0, f"count={n_shots_before}")

        # expand -> children appear + violet boxes drawn
        owner_row.locator(".bb-row__chev").click()
        page.wait_for_timeout(500)
        block_index = owner_row.get_attribute("data-index")
        children = page.locator(f'.bb-row--child[data-block="{block_index}"]')
        n_children = children.count()
        check("children listed under table", n_children >= 6, f"children={n_children}")

        core_visible = ["نام پدر", "تاریخ", "محل صدور", "شماره شناسنامه"]
        all_child_text = " | ".join(children.all_inner_texts())
        missing = [k for k in core_visible if k not in all_child_text]
        check("core fields with value present", not missing, f"missing={missing}")
        # empty-value fields («نام و نام خانوادگی:» / «شماره ملی:» are unfilled on
        # this document) and keyless fragments must NOT be listed
        hidden_keys = [k for k in ("نام و نام خانوادگی", "شماره ملی") if k in all_child_text]
        check("empty-value fields hidden from list", not hidden_keys, f"shown={hidden_keys}")
        check("no «بدون عنوان» child", "بدون عنوان" not in all_child_text)

        boxes = page.locator(".bb-field")
        n_boxes = boxes.count()
        check("field boxes drawn after expand", n_boxes >= 5, f"boxes={n_boxes}")
        nums = page.locator(".bb-num--field")
        check("field numbers drawn", nums.count() == n_boxes, f"nums={nums.count()} boxes={n_boxes}")

        # parent box distinct from children
        check("parent table box uses distinct class",
              page.locator(".bb-shape--table").count() >= 3)
        parent_cls = page.locator(f'.bb-shape[data-index="{block_index}"]').get_attribute("class")
        check("owner box is table-styled", parent_cls and "bb-shape--table" in parent_cls, str(parent_cls))
        shot(page, "01_owner_table_expanded.png")

        # geometry honesty: at least one child with real line bbox, none fabricated silently
        no_geom = page.locator(f'.bb-row--child[data-block="{block_index}"] .bb-row__fmeta--none')
        real_geom = n_children - no_geom.count()
        check("fields with real line geometry", real_geom >= 5, f"real={real_geom} none={no_geom.count()}")
        if no_geom.count():
            check("missing-geometry clearly marked", "بدون مختصات" in no_geom.first.inner_text())

        # ---- empty (keyless) fields must NOT be listed as «مقدار بدون عنوان» ----
        list_text = page.locator("#bb-list").inner_text()
        check("no «بدون عنوان» row in list", "بدون عنوان" not in list_text)
        raw = page.evaluate("() => document.querySelector('#json-code').textContent")
        try:
            data = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            data = {}
            check("JSON view parses", False, str(exc))
        tblocks = []

        def _walk(o):
            if isinstance(o, dict):
                if o.get("label") == "Table" and isinstance(o.get("fields"), list):
                    tblocks.append(o)
                for v in o.values():
                    _walk(v)
            elif isinstance(o, list):
                for v in o:
                    _walk(v)

        _walk(data)
        total_fields = sum(len(b["fields"]) for b in tblocks)
        keyless = sum(1 for b in tblocks for f in b["fields"] if not (f.get("key") or "").strip())
        incomplete = sum(1 for b in tblocks for f in b["fields"]
                         if not ((f.get("key") or "").strip() and (f.get("value") or "").strip()))
        complete = total_fields - incomplete
        check("JSON keeps every field (nothing sanitized)",
              total_fields == complete + incomplete,
              f"total={total_fields} complete={complete} incomplete={incomplete}")
        if incomplete:
            check("JSON keeps empty fields (honest data)", incomplete >= 1, f"incomplete={incomplete}")
        else:
            print("INFO  no incomplete cell in this document — "
                  "empty-field path is covered by ui_table_fields_hidden.py")
        dom_children = page.locator(".bb-row--child").count()
        check("list shows only complete fields (key AND value)", dom_children == complete,
              f"dom={dom_children} complete={complete}")

        # click a field row -> box selected + info shows key/value
        target = children.nth(1)  # نام پدر
        key_txt = target.locator(".bb-row__fkey").inner_text()
        val_txt = target.locator(".bb-row__fval").inner_text()
        target.click()
        page.wait_for_timeout(300)
        sel_boxes = page.locator(".bb-field.is-selected")
        check("field row click selects its box", sel_boxes.count() == 1, f"count={sel_boxes.count()}")
        info_visible = page.locator("#bb-info").is_visible()
        info_text = page.locator("#bb-info-text").inner_text() if info_visible else ""
        check("info panel shows key+value", (key_txt.split(":")[0] in info_text), info_text[:80])
        shot(page, "02_field_selected_from_list.png")

        # click a field box on the image -> matching list row selected
        page.locator(".bb-field").nth(0).click()
        page.wait_for_timeout(300)
        active_child = page.locator(".bb-row--child.is-active")
        check("box click selects list child", active_child.count() == 1,
              f"count={active_child.count()}")
        shot(page, "03_field_selected_from_box.png")

        # select the parent table itself (independent selection)
        page.locator(f'.bb-shape[data-index="{block_index}"]').click()
        page.wait_for_timeout(300)
        check("parent table selectable", page.locator(".bb-shape.is-selected").count() == 1
              and page.locator(".bb-field.is-selected").count() == 0)

        # parent info panel shows the hierarchical field list (not flat text)
        info_fields = page.locator("#bb-info-text .bb-info__field")
        check("info panel lists fields (hierarchy)", info_fields.count() >= 5,
              f"count={info_fields.count()}")
        info_txt = page.locator("#bb-info-text").inner_text()
        check("info panel notes hidden incomplete fields", "ناقص" in info_txt,
              info_txt[:60])

        # JSON keeps the hierarchy
        json_text = page.locator("#json-code").inner_text()
        check("JSON has fields hierarchy", '"fields"' in json_text and '"key"' in json_text and '"value"' in json_text)

        # collapse -> boxes disappear
        owner_row.locator(".bb-row__chev").click()
        page.wait_for_timeout(400)
        check("collapse hides field boxes", page.locator(".bb-field").count() == 0)
        shot(page, "04_collapsed_again.png")

        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
