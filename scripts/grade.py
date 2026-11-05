#!/usr/bin/env python3
"""Grade and grain pass — the realism step, done in code rather than prompts.

    python3 scripts/grade.py in.mp4 out.mp4              # default look
    python3 scripts/grade.py in.mp4 out.mp4 --strong     # for shiny close-ups
    python3 scripts/grade.py --compare in.mp4            # before/after stills

Why this exists: AI video is mathematically clean, and clean is the tell. Real
sensors add grain and real lenses do not deliver sculpted contrast. Knocking
contrast and saturation down and laying grain back on is the single biggest
realism win available in post, and it costs one ffmpeg pass.

Import chain() to fold it into an assembly script instead of running twice:

    from grade import chain
    subprocess.run(["ffmpeg", "-i", src, "-vf", chain(), "-c:a", "copy", dst])

A note on the skin fix. Premiere's HSL Secondary lets you eyedropper the shiny
forehead and pull only that. ffmpeg has no eyedropper, so --strong uses
selectivecolor on reds and yellows, which is where skin highlights live. It is
blunter and it applies to the whole frame, so use it only on tight faces where
the shine actually reads.

Grain of 6/255 is about 2.4%, at the low end of the 3-8% range, because most
model output already carries some texture and stacking reads as noise.
"""
import argparse
import subprocess
import sys

# Contrast and saturation come DOWN: AI renders both too punchy, which is what
# makes skin look sculpted. gamma_r nudged up warms the midtones a touch.
BASE_EQ = "eq=contrast=0.94:saturation=0.92:gamma_r=1.01"

# alls = strength, allf=t+u = temporal + uniform, so the grain moves between
# frames like real grain instead of sitting on the image like a static overlay.
BASE_NOISE = "noise=alls=6:allf=t+u"

# Blunt stand-in for an HSL-secondary skin pull.
SKIN_PULL = "selectivecolor=reds=0 0 0 -0.12:yellows=0 0 0 -0.10"


def chain(strong: bool = False) -> str:
    parts = [BASE_EQ]
    if strong:
        parts.append(SKIN_PULL)
    parts.append(BASE_NOISE)
    return ",".join(parts)


def run(src: str, dst: str, strong: bool = False, crf: int = 17) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", chain(strong),
           "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "copy", dst]
    subprocess.run(cmd, check=True)
    print(f"graded {src} -> {dst}  ({'strong' if strong else 'base'})")


def compare(src: str, at: float = 1.0) -> None:
    """Write before/after stills so the numbers can be judged by eye."""
    stem = src.rsplit(".", 1)[0]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", src,
                    "-frames:v", "1", "-q:v", "2", f"{stem}_before.jpg"], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", src,
                    "-frames:v", "1", "-vf", chain(), "-q:v", "2",
                    f"{stem}_after.jpg"], check=True)
    print(f"wrote {stem}_before.jpg and {stem}_after.jpg")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--strong", action="store_true",
                    help="add the blunt skin-highlight pull, for tight faces")
    ap.add_argument("--compare", action="store_true",
                    help="write before/after stills instead of a video")
    ap.add_argument("--at", type=float, default=1.0, help="timestamp for --compare")
    a = ap.parse_args()

    if a.compare:
        compare(a.src, a.at)
        return 0
    if not a.dst:
        ap.error("dst required unless --compare")
    run(a.src, a.dst, a.strong)
    return 0


if __name__ == "__main__":
    sys.exit(main())
