#!/usr/bin/env python3
"""Pull a clean voice out of footage that has music or noise under it (Demucs, local and free).

  separate: python3 toolbox/vocals.py separate <video-or-audio> --out-dir sep/
            -> sep/vocals.wav, sep/music.wav, and how loud the leftover music is
  ref:      python3 toolbox/vocals.py ref <video-or-audio> --out ref.wav [--start 20.5 --len 27]
            -> a 10-30 s voice reference for a clone (Seed Audio takes <= 30 s): separated, high-passed at 70 Hz,
               loudnorm -18. Without --start it takes the stretch with the most speech.
  lines:    python3 toolbox/vocals.py lines <video-or-audio> --spans 20.5-28.5,50.9-63.4 --out real.wav [--gap 0.25]
            -> the person's own recorded lines, separated and joined with short gaps: the real-voice cut to
               fall back on when a clone or a lip-sync is not approved.

Why: a clone learns whatever is in the reference, music included, and a music bed hides every pause (a take with a
bed under it showed no silence at -55 dB until the vocals were separated). Needs `demucs` (pip install demucs)."""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile


def sh(*c, **k): return subprocess.run([str(x) for x in c], check=True, **k)
def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode())


def separate(src, out_dir):
    if not shutil.which("demucs"): sys.exit("demucs is not installed: pip3 install demucs")
    out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True); tmp = pathlib.Path(tempfile.mkdtemp(prefix="vocals_"))
    wav = tmp/"in.wav"; sh("ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "2", "-ar", "44100", wav)
    sh("demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", tmp, wav, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = tmp/"htdemucs"/"in"; shutil.copy(d/"vocals.wav", out_dir/"vocals.wav"); shutil.copy(d/"no_vocals.wav", out_dir/"music.wav")
    return out_dir/"vocals.wav", out_dir/"music.wav"


def level(p):
    e = subprocess.run(["ffmpeg", "-i", str(p), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+) dB", e); return float(m.group(1)) if m else None


def pauses(p, db=-55, d=0.25):
    e = subprocess.run(["ffmpeg", "-i", str(p), "-af", f"silencedetect=n={db}dB:d={d}", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [(float(a), float(b)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", e), re.findall(r"silence_end: ([\d.]+)", e))]


def cmd_separate(a):
    v, m = separate(a.src, a.out_dir)
    print(f"vocals {v}\nmusic  {m}\nleftover music mean level {level(m)} dB (below about -60 dB means there was no bed); pauses in the vocals: {len(pauses(v))}")


def cmd_ref(a):
    v, _ = separate(a.src, pathlib.Path(a.out).parent/"_sep")
    L = min(a.len, 29.5); total = dur(v)
    if a.start is None:                                                   # the window with the least silence
        sil = pauses(v, -45, 0.3); best = (1e9, 0.0); t = 0.0
        while t + L <= total:
            s = sum(max(0, min(b, t + L) - max(x, t)) for x, b in sil); best = min(best, (s, t)); t += 0.5
        start = best[1]; print(f"picked {start:.1f}-{start + L:.1f}s ({best[0]:.1f}s of silence inside)")
    else: start = a.start
    sh("ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{L:.2f}", "-i", v, "-af", "highpass=f=70,loudnorm=I=-18:TP=-1.5:LRA=9",
       "-ac", "1", "-ar", "44100", a.out)
    print(f"wrote {a.out} ({dur(a.out):.1f}s). Listen to it: no music, no second voice, one room.")


def cmd_lines(a):
    v, _ = separate(a.src, pathlib.Path(a.out).parent/"_sep"); tmp = pathlib.Path(tempfile.mkdtemp(prefix="lines_")); parts = []
    for i, sp in enumerate(a.spans.split(",")):
        s, e = map(float, sp.split("-")); p = tmp/f"l{i}.wav"
        sh("ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", v, "-af", "afade=t=in:d=0.02,areverse,afade=t=in:d=0.04,areverse",
           "-ac", "1", "-ar", "48000", p); parts.append(p)
    gap = tmp/"gap.wav"; sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(a.gap), gap)
    ins = []; fil = ""
    for i, p in enumerate(parts):
        ins += ["-i", str(p)] + (["-i", str(gap)] if i < len(parts) - 1 else [])
    n = len(ins)//2
    sh("ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", "".join(f"[{k}:a]" for k in range(n)) + f"concat=n={n}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=9[a]",
       "-map", "[a]", "-ar", "48000", a.out)
    print(f"wrote {a.out} ({dur(a.out):.1f}s from {len(parts)} lines). On-screen spans for the face: check them with matte_coverage.py.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("separate"); s.add_argument("src"); s.add_argument("--out-dir", required=True)
    s = sp.add_parser("ref"); s.add_argument("src"); s.add_argument("--out", required=True); s.add_argument("--start", type=float); s.add_argument("--len", type=float, default=27.0)
    s = sp.add_parser("lines"); s.add_argument("src"); s.add_argument("--spans", required=True); s.add_argument("--out", required=True); s.add_argument("--gap", type=float, default=0.25)
    a = ap.parse_args(); {"separate": cmd_separate, "ref": cmd_ref, "lines": cmd_lines}[a.cmd](a)


if __name__ == "__main__":
    main()
