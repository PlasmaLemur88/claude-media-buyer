#!/usr/bin/env python3
"""Redact a document before it goes on screen: render a PDF (or take page images), cover every listed string,
pattern and region, optionally write replacement text in the gap, then re-read the result with OCR to prove the
listed strings are gone.

  python3 toolbox/redact.py report.pdf --out-dir red/ --string "Jane Doe" --string "123 Example St" \
        --regex "\\b\\d{3}-\\d{3}-\\d{4}\\b" --region "5:0.10,0.40,0.90,0.85" --replace "123 Example St=Your property" \
        [--style fill|bar|blur] [--dpi 200] [--rules rules.json] [--pages 1-7] [--no-verify]
  python3 toolbox/redact.py page1.png page2.png --out-dir red/ --string "..."      # images: words come from OCR

rules.json (optional, merged with the flags): {"strings": [], "regex": [], "regions": [{"page": 5, "box": [x0, y0, x1, y1]}],
"replace": {"old text": "new text"}}. A region box is a share of the page when every value is <= 1, else page pixels.

Styles: fill (the gap takes the colour beside it; default), bar (a grey placeholder line, reads as "text here"),
blur (weakest; never for numbers or names). Writes page-01.png..., words.json (the words still visible, with page-px
boxes, for doc_sweep.py highlights) and redaction_report.json. Exit 1 if a listed string was never found or OCR
still reads one after redaction."""
import argparse, glob, json, pathlib, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style
from safezone import ocr


def norm(t): return re.sub(r"^[^\w$%]+|[^\w%]+$", "", t.lower())


def pdf_pages(pdf, dpi, tmp, rng):
    first, last = (rng.split("-") + [None])[:2] if rng else (None, None)
    args = ["pdftoppm", "-r", str(dpi), "-png"] + (["-f", first] if first else []) + (["-l", last or first] if first else []) + [str(pdf), str(tmp/"p")]
    subprocess.run(args, check=True)
    imgs = sorted(tmp.glob("p-*.png"), key=lambda p: int(re.findall(r"(\d+)\.png$", p.name)[0]))
    html = tmp/"bbox.html"; subprocess.run(["pdftotext", "-bbox"] + (["-f", first, "-l", last or first] if first else []) + [str(pdf), str(html)], check=True)
    K = dpi/72; words = []
    for pg in html.read_text(errors="replace").split("<page ")[1:]:
        words.append([(float(a)*K, float(b)*K, float(c)*K, float(d)*K, re.sub(r"&amp;", "&", t))
                      for a, b, c, d, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', pg)])
    return imgs, words


def find_hits(words, strings, regexes):
    """-> {term: [(i0, i1)]} word index spans"""
    hits = {}; toks = [norm(w[4]) for w in words]
    for s in strings:
        q = [norm(x) for x in s.split() if norm(x)]; hits[s] = []
        for i in range(len(toks) - len(q) + 1):
            if toks[i:i+len(q)] == q: hits[s].append((i, i + len(q)))
    for r in regexes:
        rx = re.compile(r); key = f"/{r}/"; hits[key] = []; taken = set()
        for i in range(len(words)):
            for j in range(min(len(words), i + 8), i, -1):
                if rx.fullmatch(" ".join(w[4] for w in words[i:j])) and not taken & set(range(i, j)):
                    hits[key].append((i, j)); taken |= set(range(i, j)); break
            else:
                if i not in taken and rx.search(words[i][4]): hits[key].append((i, i + 1)); taken.add(i)
    return hits


def cover(im, box, style, st, text=""):
    x0, y0, x1, y1 = [int(v) for v in box]; pad = max(3, int((y1 - y0)*0.15)); x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0: return
    d = ImageDraw.Draw(im)
    if style == "blur": im.paste(im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(max(8, (y1 - y0)//2))), (x0, y0)); return
    col = im.getpixel((max(0, x0 - 6), (y0 + y1)//2)); d.rectangle([x0, y0, x1, y1], fill=col)
    if text:
        f = st.font("regular", (y1 - y0)*0.72); lum = sum(col[:3])/3
        d.text((x0 + pad, y0 + (y1 - y0)*0.12), text, font=f, fill=(40, 40, 40) if lum > 128 else (235, 235, 235))
    elif style == "bar":
        h = y1 - y0; d.rounded_rectangle([x0 + pad, y0 + h*0.30, x1 - pad, y0 + h*0.72], radius=int(h*0.21), fill=(222, 222, 222))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="one PDF, or page images in order"); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--string", action="append", default=[]); ap.add_argument("--regex", action="append", default=[])
    ap.add_argument("--region", action="append", default=[], help="page:x0,y0,x1,y1 (share of page if all <= 1, else px)")
    ap.add_argument("--replace", action="append", default=[], help="old=new: cover old and write new in its place")
    ap.add_argument("--rules", help="JSON file with strings / regex / regions / replace")
    ap.add_argument("--style", choices=["fill", "bar", "blur"], default="fill"); ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--pages", help="page range for a PDF, e.g. 1-7"); ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--brand-json")
    a = ap.parse_args(); st = Style.load(a.brand_json)
    rules = json.load(open(a.rules)) if a.rules else {}
    strings = list(rules.get("strings", [])) + a.string; regexes = list(rules.get("regex", [])) + a.regex
    replace = dict(rules.get("replace", {})); replace.update(dict(x.split("=", 1) for x in a.replace)); strings += [k for k in replace if k not in strings]
    regions = list(rules.get("regions", []))
    for r in a.region:
        pg, box = r.split(":"); regions.append({"page": int(pg), "box": [float(v) for v in box.split(",")]})
    out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); tmp = pathlib.Path(tempfile.mkdtemp(prefix="redact_"))
    if len(a.inputs) == 1 and a.inputs[0].lower().endswith(".pdf"):
        imgs, words = pdf_pages(a.inputs[0], a.dpi, tmp, a.pages)
    else:
        imgs = [pathlib.Path(p) for p in a.inputs]; res = ocr(imgs)
        if res is None and (strings or regexes): sys.exit("images have no text layer and no OCR engine is available: use --region only, or pass a PDF")
        words = [[b[:4] + (b[4],) for b in (res or {}).get(str(p), [])] for p in imgs]
        if res: words = [[(x0, y0, x1, y1, t) for (x0, y0, x1, y1, t) in ws] for ws in words]
    report = {"strings": {}, "regions": len(regions), "pages": len(imgs)}; kept = []; missing = []
    for n, (ip, ws) in enumerate(zip(imgs, words), 1):
        im = Image.open(ip).convert("RGB"); hits = find_hits(ws, strings, regexes); gone = set()
        for term, spans in hits.items():
            report["strings"].setdefault(term, 0); report["strings"][term] += len(spans)
            for i0, i1 in spans:
                sel = ws[i0:i1]; lines = {}
                for w in sel: lines.setdefault(round(w[1]/max(1, (w[3] - w[1]))), []).append(w)   # a match that wraps is covered line by line
                for k_, lw in enumerate(lines.values()):
                    box = (min(w[0] for w in lw), min(w[1] for w in lw), max(w[2] for w in lw), max(w[3] for w in lw))
                    cover(im, box, a.style, st, replace.get(term, "") if k_ == 0 else "")
                gone |= set(range(i0, i1))
        for r in regions:
            if r["page"] != n: continue
            b = r["box"]; b = [b[0]*im.width, b[1]*im.height, b[2]*im.width, b[3]*im.height] if max(b) <= 1 else b
            if a.style == "blur": cover(im, b, "blur", st)
            else: ImageDraw.Draw(im).rectangle([int(v) for v in b], fill=im.getpixel((max(0, int(b[0]) - 6), int(b[1]) + 2)))
            for i, w in enumerate(ws):
                if w[0] >= b[0] and w[2] <= b[2] and w[1] >= b[1] and w[3] <= b[3]: gone.add(i)
        dst = out/f"page-{n:02d}.png"; im.save(dst)
        kept.append({"file": dst.name, "w": im.width, "h": im.height, "words": [list(w) for i, w in enumerate(ws) if i not in gone]})
    json.dump(kept, open(out/"words.json", "w"))
    missing = [t for t, c in report["strings"].items() if c == 0]
    for t in missing: print(f"NOT FOUND: {t!r} (not in the text layer; if it is inside a picture, cover it with --region)")
    leaks = []
    if not a.no_verify:
        res = ocr(sorted(out.glob("page-*.png")))
        if res is None: print("verify: no OCR engine, check the pages by eye"); report["verified"] = False
        else:
            for f, boxes in res.items():
                text = " ".join(b[4] for b in boxes).lower()
                for s in strings:
                    if s.lower() in text and s not in replace.values(): leaks.append((pathlib.Path(f).name, s))
                for r in regexes:
                    if re.search(r, " ".join(b[4] for b in boxes)): leaks.append((pathlib.Path(f).name, f"/{r}/"))
            report["verified"] = True; report["leaks"] = leaks
            for f, s in leaks: print(f"LEAK: OCR still reads {s!r} on {f}")
    json.dump(report, open(out/"redaction_report.json", "w"), indent=1)
    print(f"pages {len(imgs)} -> {out}; hits " + ", ".join(f"{k!r}={v}" for k, v in report["strings"].items()) + f"; regions {len(regions)}")
    return 1 if (missing or leaks) else 0


if __name__ == "__main__":
    sys.exit(main())
