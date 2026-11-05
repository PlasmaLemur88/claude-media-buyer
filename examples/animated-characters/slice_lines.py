#!/usr/bin/env python3
"""Cut one speaker's take into one clip per line, ready to stagger in the edit.

  python3 slice_lines.py out/CH_CHUY.mp4 out/lines/chuy

Whisper finds every word; a silence longer than --gap (default 0.8 s) ends a
line. It prints each line with its times so you can check them against the
script before cutting: the model sometimes ad-libs a word ("ándale", "boom")
or merges two lines, and you fix that by passing --cuts with your own times.

  python3 slice_lines.py out/CH_CHUY.mp4 --words     # every word with its time
  python3 slice_lines.py out/CH_CHUY.mp4 out/lines/chuy --cuts 0.2-3.9,4.3-9.1

A fast take often runs two lines together with no pause. Then print the words,
find the first word of each line, and pass those times as --cuts.

Every clip gets a 20 ms fade in and a 60 ms fade out, which is what stopped
clicks at the cuts in the shipped example.
"""
import pathlib, subprocess, sys


def lines_from_whisper(src, gap):
    import whisper
    r = whisper.load_model("small.en").transcribe(str(src), word_timestamps=True, language="en")
    words = [w for s in r["segments"] for w in s.get("words", [])]
    out, cur = [], []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > gap:
            out.append(cur); cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [(l[0]["start"], l[-1]["end"], "".join(w["word"] for w in l).strip()) for l in out]


def cut(src, a, b, dst):
    pad_a, pad_b = max(0.0, a - 0.05), b + 0.12
    d = pad_b - pad_a
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{pad_a:.3f}", "-i", str(src), "-t", f"{d:.3f}",
                    "-af", f"afade=t=in:d=0.02,afade=t=out:st={d - 0.06:.3f}:d=0.06",
                    "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    str(dst)], check=True)


def main(a):
    if len(a) == 2 and a[1] == "--words":
        import whisper
        r = whisper.load_model("small.en").transcribe(a[0], word_timestamps=True, language="en")
        for w in (w for seg in r["segments"] for w in seg.get("words", [])):
            print(f"{w['start']:6.2f}-{w['end']:6.2f} {w['word'].strip()}")
        return
    if len(a) < 2:
        raise SystemExit(__doc__)
    src, prefix = pathlib.Path(a[0]), pathlib.Path(a[1])
    gap = float(a[a.index("--gap") + 1]) if "--gap" in a else 0.8
    if "--cuts" in a:
        spans = [tuple(map(float, s.split("-"))) + ("",) for s in a[a.index("--cuts") + 1].split(",")]
    else:
        spans = lines_from_whisper(src, gap)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for i, (s, e, text) in enumerate(spans, 1):
        dst = f"{prefix}_{i:02d}.mp4"
        cut(src, s, e, dst)
        print(f"{i:02d}  {s:6.2f}-{e:6.2f}  {text}  -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
