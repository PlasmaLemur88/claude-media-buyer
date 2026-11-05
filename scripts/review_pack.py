#!/usr/bin/env python3
"""Turn a finished render into things a reviewer can read: pictures, words and numbers.

    python3 scripts/review_pack.py out/ad_9x16.mp4
    python3 scripts/review_pack.py out/ad_9x16.mp4 --script script.txt --voice vo.wav --music bed.wav

Claude cannot press play. It reads pictures and text, so this writes, into
review/<file stem>/:
  sheet_NN.png     contact sheets, one frame per --every seconds, 4 x 5 per sheet,
                   480 px per frame so burned-in captions are readable
  first_2s.png     a full-size frame at 1.0 s (the hook, judged at phone size)
  measures.txt     duration, size, loudness of the mix (and of the voice and music
                   stems when given), black and frozen stretches (scripts/watch_take.py)
  safezone.txt     text boxes outside the platform safe zone (toolbox/safezone.py)
  transcript.txt   what is said in the render, with times (Whisper), always when it has audio
  readcheck.txt    the spoken words against the script (scripts/readcheck.py), when
                   --script is given
  pack.md          the index the reviewer reads first

It never decides pass or fail. The video-reviewer agent does that against the
brand's CHECKLIST.md. Every step that fails to run is written into pack.md
instead of stopping, so a missing tool shows up as a gap, not a silent pass.
"""
import argparse, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def probe(f):
    rc, out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type",
                   "-of", "json", str(f)])
    if rc:
        return {}
    j = json.loads(out)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": float(j.get("format", {}).get("duration", 0)), "w": v.get("width"), "h": v.get("height"),
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def lufs(f):
    rc, out = run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", "ebur128", "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    return float(m[-1]) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--script", help="the script text file, to check the spoken words")
    ap.add_argument("--voice", help="the voice stem before the mix")
    ap.add_argument("--music", help="the music stem before the mix")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between contact-sheet frames (default 1)")
    ap.add_argument("--out", help="output folder (default review/<stem>)")
    a = ap.parse_args()

    v = pathlib.Path(a.video).resolve()
    out = pathlib.Path(a.out) if a.out else ROOT / "review" / v.stem
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*"):
        if old.name != "verdict.txt":
            old.unlink()
    (out / "verdict.txt").unlink(missing_ok=True)   # an old PASS never carries over to a new render
    gaps, lines = [], []

    info = probe(v)
    if not info:
        print(f"cannot read {v}", file=sys.stderr); sys.exit(1)
    lines.append(f"file: {v}\nduration: {info['duration']:.2f} s, size: {info['w']}x{info['h']}, audio: {info['audio']}")

    rc, o = run(["ffmpeg", "-hide_banner", "-y", "-i", str(v), "-vf",
                 f"fps=1/{a.every},scale=480:-1,tile=4x5", str(out / "sheet_%02d.png")])
    if rc: gaps.append("contact sheets: ffmpeg failed")
    rc, o = run(["ffmpeg", "-hide_banner", "-y", "-ss", "1.0", "-i", str(v), "-frames:v", "1", str(out / "first_2s.png")])
    if rc: gaps.append("hook frame: ffmpeg failed")

    meas = []
    if info["audio"]:
        meas.append(f"mix loudness: {lufs(v)} LUFS integrated")
    for name, f in (("voice", a.voice), ("music", a.music)):
        if f:
            meas.append(f"{name} stem loudness: {lufs(f)} LUFS integrated")
    if a.voice and a.music:
        vl, ml = lufs(a.voice), lufs(a.music)
        if vl is not None and ml is not None:
            meas.append(f"voice minus music: {vl - ml:.1f} LU (check against the checklist's gap)")
    rc, o = run([sys.executable, str(ROOT / "scripts" / "watch_take.py"), str(v)])
    meas.append("watch_take.py (black, frozen, held frames, cuts):\n" + o.strip())
    (out / "measures.txt").write_text("\n".join(meas) + "\n")

    rc, o = run([sys.executable, str(ROOT / "toolbox" / "safezone.py"), str(v), "--sheet", str(out / "safezone.png")])
    (out / "safezone.txt").write_text(o)
    if "Traceback" in o: gaps.append("safe-zone check did not run (see safezone.txt)")

    if info["audio"]:
        try:
            import whisper
            res = whisper.load_model("base").transcribe(str(v), word_timestamps=False)
            (out / "transcript.txt").write_text("\n".join(f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text'].strip()}"
                                                          for s in res.get("segments", [])) + "\n")
        except Exception as e:
            gaps.append(f"transcript not made ({type(e).__name__}); install openai-whisper")
    if a.script:
        rc, o = run([sys.executable, str(ROOT / "scripts" / "readcheck.py"), str(v), "--script", a.script])
        (out / "readcheck.txt").write_text(o)
        if "Traceback" in o: gaps.append("readcheck did not run (see readcheck.txt)")
    else:
        gaps.append("no --script given, so the transcript is compared with on-screen text only")
    if not (a.voice and a.music):
        gaps.append("no voice and music stems, so the voice-over-music gap is only judged by ear")

    sheets = sorted(p.name for p in out.glob("sheet_*.png"))
    md = ["# Review pack", "", *lines, "", "## Read these", *[f"- {s}" for s in sheets],
          "- first_2s.png", "- measures.txt", "- safezone.txt (and safezone.png)",
          *(["- transcript.txt"] if (out / "transcript.txt").exists() else []),
          *(["- readcheck.txt"] if a.script else []), "", "## Gaps (things this pack could not check)",
          *([f"- {g}" for g in gaps] or ["- none"]), ""]
    (out / "pack.md").write_text("\n".join(md))
    print(out / "pack.md")


if __name__ == "__main__":
    main()
