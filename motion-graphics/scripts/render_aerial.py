#!/usr/bin/env python3
"""Burn a static persona text block + the brand lockup onto a clip.

Text is plain system font, all on screen at once, no sequential reveal and no
design flourish: the Instagram text-tool look. Only the lockup is branded: the
active brand's mark and wordmark font, from `aerial_static` in its brand.json.

Usage:
  python3 scripts/render_aerial.py <in.mp4> <persona_key> <out.mp4>

  python3 scripts/render_aerial.py public/aerial/aerial_coast.mp4 \\
      <persona_key> out/test.mp4

Persona keys are aerial_static.copy in the active brand's brand.json, plus the
variants built below: <key>_v2 (hooks[key] as paragraph 1), <key>_paid and
<key>_paid_v2. Edit brand.json to change the words, not this file.

Needs Pillow (`pip install -r requirements.txt`), ffmpeg and an active brand
(`python3 scripts/brand.py use <slug>` from the engine root). It needs a piece
of FOOTAGE to burn text onto: there are samples in public/aerial/, and you can
use your own clip or generate one with scripts/generate.py.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
MG = Path(__file__).resolve().parent.parent
ACTIVE = MG / "src" / "brand.active.json"
if not ACTIVE.exists():
    sys.exit("no active brand: run python3 scripts/brand.py use <slug>")
B = json.loads(ACTIVE.read_text())
S = B.get("aerial_static") or {}
PUBLIC = MG / "public"
SF = "/System/Library/Fonts/SFNS.ttf"

# Meta Reels chrome covers roughly the top 14% and bottom 20%
SAFE_TOP, SAFE_BOTTOM = int(H * 0.14), int(H * 0.795)

# SF Pro is what Instagram Stories "Classic" renders in on iOS (Roboto on
# Android), so this is the native-app look rather than an approximation.
BODY = 62
LINE = 1.16
GAP = 0.55         # paragraph gap, keeps it reading as one block
WIDTH = 0.88       # share of frame the text block fills
STROKE = 4         # hard black outline, not a soft shadow

# Variants. <key>_v2 changes ONLY paragraph 1 (a declarative hook in the second
# person instead of a third-person "For X who..."), so the hook is the single
# variable under test. <key>_paid keeps paragraph 1 byte-identical, so the
# offer is the single variable. <key>_paid_v2 is the paid twin of the _v2 hook.
COPY = {k: list(v) for k, v in (S.get("copy") or {}).items()}
HOOKS = S.get("hooks") or {}
PAID = S.get("paid") or {}
BASE = list(COPY)
COPY.update({f"{k}_v2": [HOOKS[k], *COPY[k][1:]] for k in BASE if k in HOOKS})
if PAID.get("offer"):
    COPY.update({
        f"{k}_paid": [p for p in (COPY[k][0], PAID.get("prefix", "") + COPY[k][1],
                                  PAID["offer"], PAID.get("close", "")) if p]
        for k in BASE if len(COPY[k]) > 1
    })
    COPY.update({f"{k}_paid_v2": [HOOKS[k], *COPY[f"{k}_paid"][1:]]
                 for k in BASE if k in HOOKS and f"{k}_paid" in COPY})


def font(path, size, weight):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def overlay(key):
    """One RGBA layer: static text block + branded lockup."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    max_w = int(W * WIDTH)

    # The block lives above the lockup, not in the whole safe band, or a tall
    # V2 would collide with it. Shrink the type until it fits that space.
    lock_y = int(H * 0.735)
    avail = (lock_y - 70) - SAFE_TOP

    for size in range(BODY, 33, -2):
        body = font(SF, size, "Heavy")
        lh, gap = int(size * LINE), int(size * GAP)
        rows = [wrap(d, p, body, max_w) for p in COPY[key]]
        total = sum(len(r) * lh for r in rows) + gap * (len(rows) - 1)
        if total <= avail:
            break

    y = SAFE_TOP + (avail - total) // 2

    yy = y
    for r in rows:
        for ln in r:
            x = (W - d.textlength(ln, font=body)) / 2
            d.text((x, yy), ln, font=body, fill=(255, 255, 255, 255),
                   stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
            yy += lh
        yy += gap

    # --- lockup: [mark] Wordmark  /  tag line ---
    word = S.get("wordmark") or B.get("brand", {}).get("name", "")
    wfont = str(PUBLIC / S["wordmark_font"]) if S.get("wordmark_font") else SF
    lora = font(wfont, 76, S.get("wordmark_variation") or "Bold")
    tw = d.textlength(word, font=lora)
    ms = 78 if S.get("lockup_mark") else 0
    lx = (W - (ms + (20 if ms else 0) + tw)) / 2
    ly = lock_y
    if ms:
        mark = Image.open(PUBLIC / S["lockup_mark"]).convert("RGBA").resize((ms, ms), Image.LANCZOS)
        img.alpha_composite(mark, (int(lx), int(ly + 8)))
        d = ImageDraw.Draw(img)
    d.text((lx + ms + (20 if ms else 0), ly), word, font=lora, fill=(255, 255, 255, 255),
           stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))

    sub = font(SF, 34, "Semibold")
    # "_paid" is anywhere in the key, not just the end: founder_paid_v2 is a
    # paid cut too, and an endswith() check once gave it the free lockup.
    tag = S.get("tag_paid", "") if "_paid" in key else S.get("tag_free", "")
    if tag:
        d.text(((W - d.textlength(tag, font=sub)) / 2, ly + 96), tag, font=sub,
               fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    return img


def main():
    if len(sys.argv) != 4:
        sys.exit(f"usage: render_aerial.py <in.mp4> <persona_key> <out.mp4>\nkeys: {', '.join(COPY) or 'none (fill aerial_static in brand.json)'}")
    src, key, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    if key not in COPY:
        sys.exit(f"unknown persona key {key!r}. keys: {', '.join(COPY)}")
    png = Path(dst).with_suffix(".overlay.png")
    overlay(key).save(png)

    subprocess.run([
        # -loop 1 is required: a single-frame image gives fade= no timeline to
        # act on, so alpha stays at its t=0 value (0) and overlay repeats that
        # transparent frame for the whole clip.
        "ffmpeg", "-y", "-v", "error", "-i", src, "-loop", "1", "-i", str(png),
        "-filter_complex",
        "[1]format=rgba,fade=in:st=0.35:d=0.55:alpha=1[ov];"
        "[0][ov]overlay=0:0:format=auto",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst,
    ], check=True)
    png.unlink()
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
