#!/usr/bin/env python3
"""Voice continuity check for a series: approved voice first, new take after it.

  python3 voice_ab.py out/VOICE_AB.mp4 \
      "voices/chuy_approved_take.mp3:0.2:9.5:CHUY approved" \
      "out/S2_CHUY.mp4:0:15:CHUY new episode"

Each argument is source:start:end:label. Audio-only sources (the approved
takes in voices/) play over a black frame. The operator listens to the pairs
back to back and says whether each character still sounds like himself.
Claude cannot hear, so this check always goes to the operator.
"""
import os, subprocess, sys, tempfile

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def label_png(text, path):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (720, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype(FONT, 34)
    except OSError:
        f = ImageFont.load_default()
    w = d.textlength(text, font=f); x = (720 - w) / 2
    d.rectangle([x - 16, 10, x + w + 16, 80], fill=(0, 0, 0, 160))
    d.text((x, 24), text, font=f, fill=(255, 255, 255, 255))
    im.save(path)


def main(a):
    if len(a) < 3:
        raise SystemExit(__doc__)
    out, segs = a[0], [s.rsplit(":", 3) for s in a[1:]]
    tmp = tempfile.mkdtemp()
    parts = []
    for i, (src, s, e, label) in enumerate(segs):
        s, e = float(s), float(e); d = e - s
        lp = f"{tmp}/l{i}.png"; label_png(label, lp)
        part = f"{tmp}/p{i}.mp4"
        audio_only = src.lower().endswith((".mp3", ".wav", ".m4a"))
        video_in = (["-f", "lavfi", "-t", f"{d}", "-i", "color=black:s=720x1280:r=24"] if audio_only else [])
        main_in = ["-ss", str(s), "-to", str(e), "-i", src]
        inputs = video_in + main_in + ["-i", lp]
        v, au, lab = ("0:v", "1:a", "2:v") if audio_only else ("0:v", "0:a", "1:v")
        fc = (f"[{v}]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1[b];"
              f"[b][{lab}]overlay=0:70[vo];[{au}]aformat=sample_rates=48000:channel_layouts=stereo,"
              f"afade=t=in:d=0.02,afade=t=out:st={d - 0.05}:d=0.05[ao]")
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
                        "-t", f"{d}", "-r", "24", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", part], check=True)
        parts.append(part)
    lst = f"{tmp}/list.txt"
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out],
                   check=True)
    print("wrote", out, "- the operator listens; Claude cannot judge a voice")


if __name__ == "__main__":
    main(sys.argv[1:])
