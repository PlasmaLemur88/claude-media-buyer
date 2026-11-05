#!/usr/bin/env python3
"""Capture any web page (or a local HTML file) as a clean image: pop-ups, cookie bars, sticky headers, ads and
newsletter boxes hidden; optional text redaction; the whole page, one screen, or a single element.

Use it for: an article or report page as a scrolling card in compose_shots.py, one UI element (a search box, a
form field, a button) with a transparent background for type_overlay.py, or a page to sweep with doc_sweep.py.

  python3 toolbox/capture_page.py <url-or-file> --out card.png [--full] [--mobile "iPhone 14 Pro"]
         [--selector "form input"] [--transparent] [--headline "h1"] [--redact "Jane Doe" --redact-regex "\\d{3}-\\d{4}"]
         [--redact-selector ".author"] [--redact-style box|blur] [--hide ".promo"] [--wait 4000] [--accept-consent]

Consent banners: by default it clicks Reject / Decline / Necessary-only style buttons and then hides whatever is
left; it never clicks Accept unless you pass --accept-consent. If a consent wall still blocks the article, do not
screenshot around it: build a quote card with the article's exact words (quote_card.py) and cite the outlet.

Prints a JSON line you can paste under "cards" in a shot list: file, x0, x1, headline_y (image px), source."""
import argparse, asyncio, json, pathlib, re, sys

HIDE_CSS = ("[class*='modal'],[class*='popup'],[class*='overlay'],[id*='modal'],[class*='newsletter'],[class*='sticky'],"
            "[class*='cookie'],[id*='cookie'],[class*='consent'],[id*='consent'],[class*='ad-'],[id*='ad-'],[class*='advert'],"
            "[class*='banner'],iframe,[class*='paywall'],[class*='subscribe-']{display:none !important} "
            "body,html{overflow:auto !important}")
REJECT = ["button:has-text('Reject all')", "button:has-text('Reject')", "button:has-text('Decline')", "button:has-text('Necessary only')",
          "button:has-text('Only necessary')", "button:has-text('Use necessary cookies only')", "button:has-text('Continue without accepting')",
          "[aria-label='Close']", "button:has-text('No thanks')", "button:has-text('×')"]
ACCEPT = ["#onetrust-accept-btn-handler", "button:has-text('Accept')", "button:has-text('Agree')", "button:has-text('Got it')"]

REDACT_JS = r"""
([terms, regexes, selectors, style]) => {
  const hits = {}; terms.forEach(t => hits[t] = 0); regexes.forEach(r => hits['/' + r + '/'] = 0); selectors.forEach(s => hits[s] = 0);
  const rects = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  const pats = terms.map(t => [t, new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')]).concat(regexes.map(r => ['/' + r + '/', new RegExp(r, 'g')]));
  for (const n of nodes) {
    const s = n.textContent; if (!s || !s.trim()) continue;
    for (const [key, re] of pats) {
      re.lastIndex = 0; let m;
      while ((m = re.exec(s)) !== null) {
        if (!m[0].length) { re.lastIndex++; continue; }
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        for (const c of r.getClientRects()) rects.push([c.left + scrollX, c.top + scrollY, c.width, c.height]);
        hits[key]++;
      }
    }
  }
  for (const sel of selectors) for (const el of document.querySelectorAll(sel)) {
    const c = el.getBoundingClientRect(); rects.push([c.left + scrollX, c.top + scrollY, c.width, c.height]); hits[sel]++;
  }
  for (const [x, y, w, h] of rects) {
    const d = document.createElement('div');
    d.style.cssText = `position:absolute;left:${x-3}px;top:${y-2}px;width:${w+6}px;height:${h+4}px;z-index:2147483647;border-radius:4px;` +
      (style === 'blur' ? 'backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);background:rgba(128,128,128,.15);' : 'background:#9a9a9a;');
    document.body.appendChild(d);
  }
  return hits;
}
"""


def target_url(t):
    p = pathlib.Path(t)
    return p.resolve().as_uri() if p.exists() else t


async def run(a):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        if a.mobile: ctx = await b.new_context(**pw.devices[a.mobile])
        else:
            ctx = await b.new_context(viewport={"width": a.width, "height": a.height}, device_scale_factor=a.dpr,
                                      user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36")
        pg = await ctx.new_page()
        r = await pg.goto(target_url(a.target), wait_until="domcontentloaded", timeout=60000)
        await pg.wait_for_timeout(a.wait)
        for sel in (ACCEPT if a.accept_consent else []) + REJECT:
            try: await pg.locator(sel).first.click(timeout=600)
            except Exception: pass
        await pg.keyboard.press("Escape")
        if not a.no_default_hide: await pg.add_style_tag(content=HIDE_CSS)
        if a.hide: await pg.add_style_tag(content=",".join(a.hide) + "{display:none !important}")
        if a.transparent: await pg.add_style_tag(content="html,body{background:transparent !important}")
        await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(600)
        hits = {}
        if a.redact or a.redact_regex or a.redact_selector:
            hits = await pg.evaluate(REDACT_JS, [a.redact or [], a.redact_regex or [], a.redact_selector or [], a.redact_style])
        out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        dpr = await pg.evaluate("devicePixelRatio"); head_y = None
        if a.selector:
            el = pg.locator(a.selector).first
            await el.screenshot(path=str(out), omit_background=a.transparent)
        else:
            await pg.screenshot(path=str(out), full_page=a.full, omit_background=a.transparent)
        if a.headline:
            loc = pg.locator(a.headline).first
            try: head_y = await loc.evaluate("e => e.getBoundingClientRect().top + (window.scrollY || 0)")
            except Exception:
                try: head_y = await pg.get_by_text(a.headline).first.evaluate("e => e.getBoundingClientRect().top + (window.scrollY || 0)")
                except Exception: print("headline not found:", a.headline)
        from PIL import Image
        w = Image.open(out).width
        info = {"file": str(out), "x0": 0, "x1": w, "headline_y": int(head_y*dpr) if head_y is not None else 0, "source": a.source or ""}
        print("status", r.status if r else None, "|", (await pg.title())[:80])
        for k, v in hits.items():
            print(f"redacted {k!r}: {v} hit(s)" + ("   <- NOT FOUND in the page text (it may be inside an image: cover it with --redact-selector or a region)" if v == 0 else ""))
        print(json.dumps(info))
        await b.close()
        return 1 if any(v == 0 for v in hits.values()) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="URL or path to a local .html file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--full", action="store_true", help="whole scrollable page (for a scrolling card or a sweep)")
    ap.add_argument("--mobile", help='Playwright device name, e.g. "iPhone 14 Pro"')
    ap.add_argument("--width", type=int, default=1200); ap.add_argument("--height", type=int, default=1500); ap.add_argument("--dpr", type=float, default=2)
    ap.add_argument("--selector", help="capture only this element (CSS)")
    ap.add_argument("--transparent", action="store_true", help="transparent page background (element captures for overlays)")
    ap.add_argument("--headline", help="CSS selector or visible text whose top becomes headline_y in the printed JSON")
    ap.add_argument("--source", help='source line to print in the JSON, e.g. "Outlet · 16 Sep 2026"')
    ap.add_argument("--redact", action="append", help="exact text to cover (case-insensitive); repeat for more")
    ap.add_argument("--redact-regex", action="append", help="JavaScript regex to cover; repeat for more")
    ap.add_argument("--redact-selector", action="append", help="CSS selector whose elements are covered; repeat for more")
    ap.add_argument("--redact-style", choices=["box", "blur"], default="box")
    ap.add_argument("--hide", action="append", help="extra CSS selector to hide; repeat for more")
    ap.add_argument("--no-default-hide", action="store_true", help="do not hide pop-ups, banners and iframes")
    ap.add_argument("--wait", type=int, default=3000, help="ms to wait after load")
    ap.add_argument("--accept-consent", action="store_true", help="allow clicking Accept on consent banners (off by default)")
    a = ap.parse_args()
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
