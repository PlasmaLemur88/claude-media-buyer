#!/usr/bin/env python3
"""Build a plain article-style card from exact quoted words, for sources you cannot screenshot cleanly (consent
walls, paywalls, pages that time out, pop-ups over the headline). Outlet name as plain text, never its logo.

  python3 toolbox/quote_card.py --out card.png --outlet "Outlet" --date "16 Sep 2026" \
      --headline "The headline, word for word" [--quote "A quoted line, word for word"] [--byline "By A. Writer"] \
      [--width 1179] [--brand-json F]

The words must be copied exactly from the source; paraphrase on a card that looks like a news page is a
misquote. Keep the URL and access date in the ad's copy sheet. Prints the shot-list "cards" JSON line."""
import argparse, json, pathlib, sys
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > 1 and len(lines[-1].split()) == 1:                  # no widow: pull one word down from the line above
        prev = lines[-2].split()
        if len(prev) > 1: lines[-2] = " ".join(prev[:-1]); lines[-1] = prev[-1] + " " + lines[-1]
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True); ap.add_argument("--outlet", required=True); ap.add_argument("--date", default="")
    ap.add_argument("--headline", required=True); ap.add_argument("--quote", default=""); ap.add_argument("--byline", default="")
    ap.add_argument("--width", type=int, default=1179); ap.add_argument("--brand-json")
    a = ap.parse_args(); st = Style.load(a.brand_json); W = a.width; M = int(0.07*W)
    im = Image.new("RGB", (W, 3000), (255, 255, 255)); d = ImageDraw.Draw(im); ink = (20, 20, 20); grey = (110, 110, 110)
    y = int(0.06*W); head_y = y
    d.text((M, y), a.outlet.upper(), font=st.font("heavy", 0.045*W), fill=ink); y += int(0.075*W)
    d.line([(M, y), (W - M, y)], fill=(220, 220, 220), width=3); y += int(0.05*W)
    fh = st.font("bold", 0.068*W)
    for ln in wrap(d, a.headline, fh, W - 2*M): d.text((M, y), ln, font=fh, fill=ink); y += int(fh.size*1.18)
    y += int(0.03*W); fs = st.font("regular", 0.032*W)
    meta = " · ".join(x for x in (a.byline, a.date) if x)
    if meta: d.text((M, y), meta, font=fs, fill=grey); y += int(fs.size*1.6)
    if a.quote:
        y += int(0.04*W); fq = st.font("regular", 0.050*W); q0 = y
        for ln in wrap(d, f"“{a.quote}”", fq, W - 2*M - int(0.05*W)): d.text((M + int(0.05*W), y), ln, font=fq, fill=ink); y += int(fq.size*1.3)
        d.rectangle([M, q0, M + 8, y], fill=st.color("highlight"))
    y += int(0.08*W)
    for _ in range(6):                                                    # grey body lines: the page reads as an article without inventing text
        d.rounded_rectangle([M, y, W - M - (0 if _ % 3 else int(0.2*W)), y + 18], radius=9, fill=(232, 232, 232)); y += 46
    im = im.crop((0, 0, W, y + int(0.05*W))); out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); im.save(out)
    src = " · ".join(x for x in (a.outlet, a.date) if x)
    print(json.dumps({"file": str(out), "x0": 0, "x1": W, "headline_y": head_y, "source": src}))


if __name__ == "__main__":
    main()
