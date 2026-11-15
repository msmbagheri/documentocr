#!/usr/bin/env python3
"""BoundingBoxViewer tests for the DocumentOCR web UI (real pipeline, no mocks).

Verifies the following requirements from the mission:
  * the original document image is shown, aspect preserved
  * OCR blocks are drawn as SVG boxes at the exact engine coordinates
  * detection lines are drawn as a separate layer (when data is valid)
  * boxes stay aligned when zoomed (relative positions unchanged)
  * clicking a box selects it and shows its text / label / confidence / order
  * clicking a list row selects + scrolls to the box; hover highlights it
  * layer toggles (blocks / lines / numbers) work
  * no horizontal overflow and no clipped cards on desktop + mobile

Run (UI must be up on http://127.0.0.1:8501):
  python3 webui/tests/ui_bbox_viewer.py
"""

from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = os.path.dirname(os.path.dirname(ROOT))  # …/documentocr
SHOTS = os.path.join(PROJECT, "docs", "reports", "2026-11-14_bbox_viewer", "screenshots")
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
            document.querySelectorAll('.card, .stat').forEach(el => {
                if (el.offsetParent === null) return;
                if (el.scrollWidth > el.clientWidth + 1) offenders.push(el.className);
            });
            return {w: de.scrollWidth, c: de.clientWidth, offenders};
        }"""
    )
    ok = data["w"] <= data["c"] + 1 and not data["offenders"]
    return ok, json.dumps(data)


def engine_json(page):
    return json.loads(page.locator("#json-code").inner_text())


def rect_rel(page, index):
    """Relative position/size of a box (and no-zoom img) inside the frame."""
    return page.evaluate(
        """(i) => {
            const r = document.querySelector('.bb-shape[data-index="' + i + '"]').getBoundingClientRect();
            const f = document.getElementById('bb-frame').getBoundingClientRect();
            return [ (r.left-f.left)/f.width, (r.top-f.top)/f.height, r.width/f.width, r.height/f.height ];
        }""",
        str(index),
    )


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    if not os.path.isfile(SAMPLE):
        print(f"sample missing: {SAMPLE}")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 980},
                                  device_scale_factor=1,
                                  permissions=["clipboard-read", "clipboard-write"],
                                  accept_downloads=True)
        page = ctx.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        page.goto(URL, wait_until="networkidle")
        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_timeout(400)
        page.click("#run-btn")
        page.wait_for_selector("#result:not([hidden])", timeout=180_000)
        page.wait_for_selector("#bb-img:not([hidden])", timeout=30_000)
        page.wait_for_timeout(1200)

        check("۱. بدون خطای جاوااسکریپت در صفحه", not page_errors, "; ".join(page_errors[:3]))
        j = engine_json(page)
        blocks = sorted(j["blocks"], key=lambda b: b["reading_order"])
        W, H = j["image_bbox"][2], j["image_bbox"][3]
        check("۲. خروجی واقعی: ۳۷ بلوک", len(blocks) == 37, f"{len(blocks)}")

        n_rects = page.locator(".bb-shape").count()
        check("۳. کادرهای بلوک OCR در SVG رسم شده‌اند", n_rects == len(blocks), f"{n_rects} rects")
        check("۴. ردیف‌های فهرست بلوک‌ها ساخته شده‌اند", page.locator(".bb-row").count() == len(blocks),
              f"{page.locator('.bb-row').count()} rows")
        check("۵. شماره‌ها روی کادرها نمایش داده شده‌اند", page.locator(".bb-num").count() == len(blocks))
        check("۶. تعداد در برچسب چیپ نمایش داده شده", "۳۷" in page.locator("#bb-count").inner_text(),
              page.locator("#bb-count").inner_text())
        check("۷. کنترل خطوط Detection فعال است (داده معتبر)",
              page.locator("#bb-lines-wrap").is_visible())
        check("۸. هشدار مختصات نمایش داده نشده", page.locator("#bb-warning").is_hidden())
        check("۹. نسبت ابعاد تصویر حفظ شده",
              (W / H) - (page.locator("#bb-img").evaluate("el => el.naturalWidth/el.naturalHeight")) < 0.01)

        # exact coordinate match (engine space -> screen)
        idx_ok = []
        for i in range(min(len(blocks), 6)):
            b = blocks[i]["bbox"]
            exp = [b[0] / W, b[1] / H, (b[2] - b[0]) / W, (b[3] - b[1]) / H]
            rel = rect_rel(page, i)
            diff = max(abs(a - e) for a, e in zip(rel, exp))
            idx_ok.append(diff * W <= 2.0)  # <= 2px in engine space
        check("۱۰. مختصات کادرها دقیقاً با موتور مطابق‌اند (۶ کادر اول)", all(idx_ok),
              f"diffs(px): {[round(d * W, 2) for d in idx_ok if d is not None]}" if False else "ok")

        # zoom keeps alignment
        page.click("#bb-zoom-in")
        page.wait_for_timeout(300)
        rel_zoom = rect_rel(page, 0)
        exp0 = [blocks[0]["bbox"][0] / W, blocks[0]["bbox"][1] / H,
                (blocks[0]["bbox"][2] - blocks[0]["bbox"][0]) / W,
                (blocks[0]["bbox"][3] - blocks[0]["bbox"][1]) / H]
        dzoom = max(abs(a - e) for a, e in zip(rel_zoom, exp0)) * W
        check("۱۱. پس از بزرگ‌نمایی کادرها سر جای خود باقی می‌مانند (≤۲px)", dzoom <= 2.0, f"{round(dzoom,2)}px")
        check("۱۲. برچسب زوم به‌روز می‌شود", page.locator("#bb-zoom-label").inner_text() not in ("۱۰۰٪",),
              page.locator("#bb-zoom-label").inner_text())
        page.click("#bb-zoom-fit")
        page.wait_for_timeout(300)
        check("۱۳. دکمه تناسب زوم را برمی‌گرداند", page.locator("#bb-zoom-label").inner_text() == "۱۰۰٪",
              page.locator("#bb-zoom-label").inner_text())

        # click a box on the image -> info panel
        page.locator("#bb-stage").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        page.locator('.bb-shape[data-index="0"]').click()
        page.wait_for_timeout(300)
        info = page.locator("#bb-info")
        check("۱۴. کلیک روی کادر، پنل اطلاعات را باز می‌کند", info.is_visible())
        check("۱۵. متن بلوک انتخاب‌شده نمایش داده می‌شود",
              blocks[0]["text"].strip() in page.locator("#bb-info-text").inner_text(),
              page.locator("#bb-info-text").inner_text()[:40])
        check("۱۶. برچسب بلوک و ترتیب خواندن نمایش داده می‌شود",
              blocks[0]["label"] in page.locator("#bb-info-label").inner_text(), page.locator("#bb-info-label").inner_text())
        check("۱۷. اطمینان (confidence) نمایش داده می‌شود",
              "اطمینان" in page.locator("#bb-info-conf").inner_text() and "٪" in page.locator("#bb-info-conf").inner_text(),
              page.locator("#bb-info-conf").inner_text())
        check("۱۸. کپی متن بلوک فعال شد", page.locator("#bb-copy-text").is_enabled())
        clip_ok = False
        page.locator("#bb-copy-text").click()
        page.wait_for_timeout(400)
        clip = page.evaluate("() => navigator.clipboard.readText()")
        clip_ok = clip.strip() == blocks[0]["text"].strip()
        check("۱۹. کپی متن بلوک همان متن واقعی است", clip_ok, f"{len(clip)} chars")

        # select from list -> indicates selection, scrolls
        page.locator("#bb-list .bb-row").nth(12).click()
        page.wait_for_timeout(600)
        active = page.locator("#bb-list .bb-row.is-active").count()
        sel_rect = page.locator(".bb-shape.is-selected").count()
        check("۲۰. انتخاب از فهرست ردیف را فعال می‌کند", active == 1)
        check("۲۱. انتخاب از فهرست کادر را در تصویر برجسته می‌کند", sel_rect == 1)
        check("۲۲. اطلاعات بلوک انتخاب‌شده از فهرست به‌روز می‌شود",
              blocks[12]["text"].strip()[:30] in page.locator("#bb-info-text").inner_text())
        scrolled = page.evaluate(
            """() => {
                const r = document.querySelector('.bb-shape.is-selected').getBoundingClientRect();
                const s = document.getElementById('bb-stage').getBoundingClientRect();
                return r.top >= s.top - 5 && r.bottom <= s.bottom + 5;
            }"""
        )
        check("۲۳. پس از انتخاب، کادر داخل نمای قابل‌دید اسکرول می‌شود", scrolled)

        # hover row -> highlight
        page.locator("#bb-list .bb-row").nth(5).hover()
        page.wait_for_timeout(250)
        check("۲۴. هاور روی ردیف، کادر را موقتاً هایلایت می‌کند",
              page.locator('.bb-shape.is-hover').count() >= 1)

        # layer toggles
        n_blocks_before = page.locator(".bb-shape").count()
        page.uncheck("#bb-show-blocks")
        page.wait_for_timeout(200)
        check("۲۵. خاموش‌کردن بلوک‌ها کادرها را پنهان می‌کند", page.locator(".bb-shape").count() == 0)
        page.check("#bb-show-blocks")
        page.wait_for_timeout(200)
        check("۲۶. روشن‌کردن بلوک‌ها کادرها را برمی‌گرداند", page.locator(".bb-shape").count() == n_blocks_before)
        n_lines = page.locator(".bb-line, .bb-poly").count()
        check("۲۷. لایه خطوط Detection رسم شده است (داده واقعی)", n_lines >= 10, f"{n_lines} lines")
        page.uncheck("#bb-show-lines")
        page.wait_for_timeout(200)
        check("۲۸. خاموش‌کردن خطوط، لایهٔ خطوط را پنهان می‌کند",
              page.locator(".bb-line, .bb-poly").count() == 0)
        page.check("#bb-show-lines")
        page.wait_for_timeout(200)
        check("۲۹. روشن‌کردن خطوط، لایه را برمی‌گرداند",
              page.locator(".bb-line, .bb-poly").count() == n_lines)
        page.uncheck("#bb-show-nums")
        page.wait_for_timeout(200)
        check("۳۰. خاموش‌کردن شماره‌ها، اعداد را پنهان می‌کند", page.locator(".bb-num").count() == 0)
        page.check("#bb-show-nums")
        page.wait_for_timeout(200)
        check("۳۱. روشن‌کردن شماره‌ها، اعداد را برمی‌گرداند", page.locator(".bb-num").count() == len(blocks))

        # deselect on empty image area (svg covers the img; click its empty corner)
        page.locator("#bb-stage").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        page.locator("#bb-svg").click(position={"x": 6, "y": 6})
        page.wait_for_timeout(250)
        check("۳۲. کلیک روی فضای خالی، انتخاب را پاک می‌کند",
              page.locator(".bb-shape.is-selected").count() == 0 and page.locator("#bb-info").is_hidden())

        # no overflow / no clipped cards (desktop)
        ok, detail = no_overflow(page)
        check("۳۳. بدون اسکرول افقی و بریدگی (دسکتاپ)", ok, detail)
        page.evaluate("window.scrollTo(0, document.getElementById('bb-list').getBoundingClientRect().top + scrollY - 120)")
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(SHOTS, "01_konkour_boxes_full.png"), full_page=True)
        page.screenshot(path=os.path.join(SHOTS, "02_konkour_boxes_viewer.png"),
                        clip=page.locator(".card--viewer").bounding_box())

        # mobile
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(600)
        ok, detail = no_overflow(page)
        check("۳۴. بدون اسکرول افقی و بریدگی (موبایل ۳۹۰)", ok, detail)
        layout = page.evaluate(
            """() => {
                const cols = [...document.querySelectorAll('.bb-grid > *')].map(e => Math.round(e.getBoundingClientRect().width));
                return cols;
            }"""
        )
        check("۳۵. موبایل: تصویر و فهرست تک‌ستونه", len(layout) == 2 and abs(layout[0] - layout[1]) < 2, str(layout))
        page.locator("#bb-list").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SHOTS, "03_konkour_boxes_mobile.png"), full_page=True)

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
