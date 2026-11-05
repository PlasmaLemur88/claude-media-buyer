#!/usr/bin/env python3
"""Check a cutout (a transparent webm from matte.py, Bria or any matting tool) for frames where the matte grabbed
something that is not the person: a phone held up to the lens, a laptop, a chair, a second person.

  python3 toolbox/matte_coverage.py cutout.webm [--every 0.1] [--jump 0.35] [--no-face] [--sheet cov.png] [--csv cov.csv]

For every sampled frame it measures how much of the frame the matte covers, its bounding box, and (unless
--no-face) whether a face is found inside it (YuNet, scripts/yunet.onnx). A frame is flagged when the coverage
jumps more than --jump (as a share) away from the take's median, or when no face sits inside the matte.
Prints the clean spans as "a-b,c-d" (seconds): the only windows where it is safe to show the cutout. Writes a
sheet of flagged frames over flat green. Exit 1 if anything is flagged. It measures; a person still watches."""
import argparse, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent


def frames(path, every):
    w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                             "-of", "csv=p=0", str(path)]).decode().strip().split(",")[:2])
    dec = ["-c:v", "libvpx-vp9"] if str(path).lower().endswith(".webm") else []
    p = subprocess.Popen(["ffmpeg", "-v", "error", *dec, "-i", str(path), "-vf", f"fps=1/{every}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(w*h*4)
        if len(b) < w*h*4: break
        yield i*every, np.frombuffer(b, np.uint8).reshape(h, w, 4); i += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cutout"); ap.add_argument("--every", type=float, default=0.1); ap.add_argument("--jump", type=float, default=0.35)
    ap.add_argument("--no-face", action="store_true"); ap.add_argument("--sheet"); ap.add_argument("--csv"); ap.add_argument("--min-span", type=float, default=0.4)
    a = ap.parse_args()
    det = None
    if not a.no_face:
        import cv2
        m = ROOT/"scripts"/"yunet.onnx"
        if not m.exists(): sys.exit("scripts/yunet.onnx is missing (talking_head.py downloads it); or pass --no-face")
    rows = []; keep = []
    for t, f in frames(a.cutout, a.every):
        al = f[..., 3] > 128; cov = float(al.mean()); ys, xs = np.nonzero(al)
        bb = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else None; face = None
        if not a.no_face and bb:
            import cv2
            h, w = al.shape
            if det is None: det = cv2.FaceDetectorYN.create(str(ROOT/"scripts"/"yunet.onnx"), "", (w, h), 0.7)
            rgb = np.where(al[..., None], f[..., :3], 128).astype(np.uint8)       # people only: the matte over flat grey
            _, d = det.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            face = bool(d is not None and len(d))
        rows.append([t, cov, bb, face])
        im = Image.fromarray(f); g = Image.new("RGBA", im.size, (0, 177, 64, 255)); g.alpha_composite(im)
        keep.append(g.convert("RGB").resize((int(240*im.width/im.height), 240)))   # small thumbnails only
    if not rows: sys.exit("no frames decoded (is it a transparent webm?)")
    med = float(np.median([r[1] for r in rows if r[1] > 0] or [0]))
    flags = []
    for r in rows:
        why = []
        if r[1] == 0: why.append("empty matte")
        elif med and abs(r[1] - med)/med > a.jump: why.append(f"coverage {r[1]:.3f} vs median {med:.3f}")
        if r[3] is False: why.append("no face inside the matte")
        flags.append(why)
    ok = [not w for w in flags]; spans = []; s = None
    for (t, *_), good in zip(rows, ok):
        if good and s is None: s = t
        if not good and s is not None:
            if t - s >= a.min_span: spans.append((s, t))
            s = None
    if s is not None and rows[-1][0] + a.every - s >= a.min_span: spans.append((s, rows[-1][0] + a.every))
    bad = [(r[0], w) for r, w in zip(rows, flags) if w]
    print(f"frames {len(rows)}, median coverage {med:.3f}, flagged {len(bad)}")
    for t, w in bad[:25]: print(f"  {t:6.2f}s  " + "; ".join(w))
    if len(bad) > 25: print(f"  ... {len(bad) - 25} more")
    print("clean spans:", ",".join(f"{x:.1f}-{y:.1f}" for x, y in spans) or "none")
    if a.csv:
        with open(a.csv, "w") as fh:
            fh.write("t,coverage,x0,y0,x1,y1,face,flag\n")
            for r, w in zip(rows, flags): fh.write(f"{r[0]:.2f},{r[1]:.4f},{','.join(map(str, r[2] or ('', '', '', '')))},{r[3]},{'|'.join(w)}\n")
    if bad:
        sp = pathlib.Path(a.sheet) if a.sheet else pathlib.Path(a.cutout).with_name(pathlib.Path(a.cutout).stem + "_coverage.png")
        pick = [i for i, w in enumerate(flags) if w][:24]; th = 240
        tw = keep[0].width; sheet = Image.new("RGB", (6*tw, ((len(pick) + 5)//6)*th), (255, 255, 255))
        for k, i in enumerate(pick):
            g = keep[i].copy(); ImageDraw.Draw(g).text((6, 6), f"{rows[i][0]:.1f}s", fill=(255, 255, 255)); sheet.paste(g, ((k % 6)*tw, (k//6)*th))
        sheet.save(sp); print("sheet:", sp)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
