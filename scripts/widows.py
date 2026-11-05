#!/usr/bin/env python3
"""Flag widows in HTML-rendered stills: any text block whose last rendered line is a single word.

    python3 scripts/widows.py still.html                          # 1080x1920 viewport
    python3 scripts/widows.py still.html --size 1080x1350         # 4:5
    python3 scripts/widows.py out/*.html --size 1080x1920 --json widows.json

Exit code = number of widows found (capped at 99), so a build script can refuse to ship.

FROM A STILL BUILDER (Playwright, Python), check each page right before the screenshot:

    import sys; sys.path.insert(0, "<engine>/scripts")
    from widows import find_widows
    ...
    page.set_viewport_size({"width": W, "height": H}); page.goto("file://" + html)
    bad = find_widows(page)            # [] when clean; else [{"text", "widow", "lines", "tag", "cls", "box"}, ...]
    if bad: raise SystemExit(f"widow in {html}: {bad}")
    page.screenshot(path=jpg)

From Node/Playwright, load scripts/widows.js as a string and page.evaluate(src, {selector, tolerance, minWords}).

Prevention that usually fixes it: `text-wrap: balance` on the text blocks (Chrome 114+), or a non-breaking space
between the last two words. The check still runs, because balance does not guarantee it at every size.
Web fonts must have loaded before the check (the CLI waits for document.fonts.ready).
Needs: pip install playwright && python3 -m playwright install chromium
"""
import argparse
import json
import pathlib
import sys

JS = (pathlib.Path(__file__).resolve().parent / "widows.js").read_text()
DEFAULT_SELECTOR = "div,p,h1,h2,h3,h4,h5,h6,li,blockquote,figcaption,td"


def find_widows(page, selector=DEFAULT_SELECTOR, tolerance=6, min_words=3):
    """Run the check on a loaded Playwright page. Returns a list of widow records ([] when clean)."""
    return page.evaluate(JS, {"selector": selector, "tolerance": tolerance, "minWords": min_words})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="+", type=pathlib.Path)
    ap.add_argument("--size", default="1080x1920", help="viewport WxH, the still's pixel size")
    ap.add_argument("--selector", default=DEFAULT_SELECTOR, help="CSS selector of blocks to judge")
    ap.add_argument("--tolerance", type=int, default=6, help="px: words whose tops differ less are on one line")
    ap.add_argument("--min-words", type=int, default=3, help="skip blocks shorter than this (labels, prices)")
    ap.add_argument("--json", help="write results here")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    W, H = (int(x) for x in a.size.lower().split("x"))
    results, total = {}, 0
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H})
        for f in a.html:
            pg.goto(f.resolve().as_uri())
            pg.evaluate("document.fonts.ready")
            bad = find_widows(pg, a.selector, a.tolerance, a.min_words)
            results[str(f)] = bad
            total += len(bad)
            print(f"{f}: {'clean' if not bad else f'{len(bad)} widow(s)'}")
            for b in bad:
                print(f"  <{b['tag']}{'.' + b['cls'] if b['cls'] else ''}> last line is just \"{b['widow']}\"  ({b['lines']} lines): {b['text']}")
        br.close()
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(results, indent=1))
    sys.exit(min(total, 99))


if __name__ == "__main__":
    main()
