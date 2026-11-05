#!/usr/bin/env python3
"""Safe-zone check for any render: is any on-screen text where the platform's UI will cover it?

Two ways in:
  1. Exact, inside a renderer that knows its own text boxes (compose_shots.py does this on every frame):
        from safezone import Zone
        z = Zone.for_frame(W, H, style); bad = z.check(boxes, presenter_box)
  2. Any finished video or still, by OCR (Apple Vision on a Mac, else tesseract if installed):
        python3 toolbox/safezone.py video.mp4 [--every 0.5] [--sheet out.png] [--brand-json F]
        python3 toolbox/safezone.py still.png
     Samples frames, reads every text box, and fails (exit 2) on any box outside the zone. Always writes a
     contact sheet with the forbidden areas shaded, so a person can check what OCR cannot see (logos, tiny type).

The zone comes from the active brand's presenter.safe_zone (see brandstyle.py); the 9:16 default matches
RULES.md (text inside y 290-1240, x 60-940 on 1080x1920). Anything not 9:16-ish uses the 4:5 zone."""
import argparse, json, pathlib, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style

HERE = pathlib.Path(__file__).resolve().parent


class Zone:
    def __init__(self, W, H, top, bottom, left, right):
        self.W, self.H, self.top, self.bottom, self.left, self.right = W, H, top, bottom, left, right

    @classmethod
    def for_frame(cls, W, H, style=None):
        st = style or Style.load(); t, b, l, r = st.zone(W, H); return cls(W, H, t, b, l, r)

    def check(self, boxes, presenter_box=None, tol=2):
        """boxes = [(kind, (x0, y0, x1, y1))]; returns [(reason, box)] for every text box outside the zone or over the presenter"""
        bad = []
        for kind, (x0, y0, x1, y1) in boxes:
            if x0 < self.left - tol or x1 > self.right + tol or y0 < self.top - tol or y1 > self.bottom + tol:
                bad.append(("outside safe zone", (x0, y0, x1, y1)))
            elif presenter_box and x0 < presenter_box[2] and x1 > presenter_box[0] and y0 < presenter_box[3] and y1 > presenter_box[1]:
                bad.append(("over presenter", (x0, y0, x1, y1)))
        return bad

    def shade(self, im, scale=1.0):
        """the frame with the forbidden areas tinted red"""
        im = im.convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov); s = scale; w, h = im.size
        d.rectangle([0, 0, w, self.top*s], fill=(255, 0, 0, 70)); d.rectangle([0, self.bottom*s, w, h], fill=(255, 0, 0, 70))
        d.rectangle([self.right*s, self.top*s, w, self.bottom*s], fill=(255, 0, 0, 70)); d.rectangle([0, self.top*s, self.left*s, self.bottom*s], fill=(255, 0, 0, 70))
        return Image.alpha_composite(im, ov).convert("RGB")


def sheet(frames, zone, path, cols=12, div=6):
    w, h = zone.W//div, zone.H//div; rows = max(1, (len(frames) + cols - 1)//cols)
    out = Image.new("RGB", (cols*w, rows*h), (255, 255, 255))
    for i, im in enumerate(frames): out.paste(zone.shade(im.resize((w, h)), 1/div), ((i % cols)*w, (i//cols)*h))
    out.save(path); return path


def ocr(paths):
    """{path: [(x0, y0, x1, y1, text, conf)]} or None when no OCR engine is available"""
    if shutil.which("swift") and sys.platform == "darwin":
        r = subprocess.run(["swift", str(HERE/"ocr_vision.swift"), *map(str, paths)], capture_output=True, text=True)
        res = {}
        for line in r.stdout.splitlines():
            try: j = json.loads(line)
            except ValueError: continue
            res[j["file"]] = [tuple(b) for b in j.get("boxes", [])]
        if res: return res
    if shutil.which("tesseract"):
        res = {}
        for p in paths:
            tsv = subprocess.run(["tesseract", str(p), "-", "tsv"], capture_output=True, text=True).stdout.splitlines()[1:]
            bx = []
            for row in tsv:
                c = row.split("\t")
                if len(c) == 12 and c[11].strip() and float(c[10]) > 50:
                    x, y, w, h = map(int, c[6:10]); bx.append((x, y, x + w, y + h, c[11], float(c[10])/100))
            res[str(p)] = bx
        return res
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", help="a video or a still")
    ap.add_argument("--every", type=float, default=0.5, help="seconds between sampled frames (video)")
    ap.add_argument("--sheet", help="contact sheet path (default: <media>_safezone.png)")
    ap.add_argument("--min-conf", type=float, default=0.4, help="ignore OCR boxes below this confidence")
    ap.add_argument("--brand-json", help="brand.json to take the zone from instead of the active brand")
    ap.add_argument("--ignore", action="append", default=[], help="a-b seconds to skip, e.g. a zoomed full-screen document you have judged by eye")
    ap.add_argument("--tol", type=float, default=6, help="px of OCR box padding to forgive")
    a = ap.parse_args()
    media = pathlib.Path(a.media); tmp = pathlib.Path(tempfile.mkdtemp(prefix="safezone_"))
    if media.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        shutil.copy(media, tmp/"f00000.png"); times = [0.0]
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(media), "-vf", f"fps=1/{a.every}", str(tmp/"f%05d.png")], check=True)
        times = [i*a.every for i in range(len(list(tmp.glob("f*.png"))))]
    frames = sorted(tmp.glob("f*.png"))
    if not frames: sys.exit("no frames decoded")
    W, H = Image.open(frames[0]).size; zone = Zone.for_frame(W, H, Style.load(a.brand_json))
    sp = pathlib.Path(a.sheet) if a.sheet else media.with_name(media.stem + "_safezone.png")
    sheet([Image.open(f).convert("RGB") for f in frames], zone, sp); print("sheet:", sp)
    res = ocr(frames)
    if res is None:
        print("no OCR engine (Apple Vision via swift, or tesseract): judge the sheet by eye; nothing was checked automatically"); return 3
    bad = 0
    skip = [tuple(map(float, x.split("-"))) for x in a.ignore]
    for t, f in zip(times, frames):
        if any(x <= t <= y for x, y in skip): continue
        boxes = [("text", b[:4]) for b in res.get(str(f), []) if b[5] >= a.min_conf]
        texts = {tuple(b[:4]): b[4] for b in res.get(str(f), [])}
        for why, bb in zone.check(boxes, tol=a.tol):
            bad += 1; print(f"  {t:6.2f}s  {why}: {texts.get(tuple(bb), '')!r} at {tuple(int(v) for v in bb)}")
    print(f"frames {len(frames)}, violations {bad}", "(OCR sees text only: check logos and icons on the sheet)")
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
