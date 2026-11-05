#!/usr/bin/env python3
"""Lip-sync a voice that is longer than the one continuous take you have, without looping or stitching mid-face.

scripts/talking_head.py needs one stretch of the raw take as long as the voice plus 1.5 s. When the script runs
longer, this splits the voice in two at a word gap that falls where the presenter is OFF screen (a full-screen
insert, a document sweep), lip-syncs each part from its own window of the take, and joins them there. The join
is never seen, so the two windows can come from different moments of the take.

  plan: python3 toolbox/split_lipsync.py plan --work W --source take.mov --voice voice.wav --words voice.json --hidden 50.0-58.0
  run:  python3 toolbox/split_lipsync.py run  --work W --source take.mov --voice voice.wav --words voice.json --hidden 50.0-58.0
        [--split 54.0] [--matte local|bria] [--dry-run]

--hidden: spans of the FINAL voice timeline (seconds) where the presenter is not on screen; the split must fall in
one. `plan` and `run --dry-run` pick the split and both windows (local face tracking, free) and print the cost;
`run` then crops, lip-syncs each part (sync.so v2 pro on fal, ~$5 per output minute), pastes the mouth back, joins
with the concat filter and cuts the presenter out (matte.py locally by default; --matte bria costs ~$0.14/s).
Every step resumes: finished parts are skipped on a re-run. Reuses scripts/talking_head.py for crop, sync, paste."""
import argparse, json, math, pathlib, subprocess, sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import numpy as np


def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode())


def gaps(words_json, min_gap=0.12):
    ws = [w for s in json.load(open(words_json))["segments"] for w in s.get("words", [])]
    return [((a["end"] + b["start"])/2, b["start"] - a["end"]) for a, b in zip(ws, ws[1:]) if b["start"] - a["end"] >= min_gap]


def face_track(source):
    import talking_head as th, cv2
    det = th._detector(540, 960); t, w = [], []
    for i, f in enumerate(th._frames(source, fps=10)):
        _, d = det.detect(cv2.resize(cv2.cvtColor(f, cv2.COLOR_RGB2BGR), (540, 960)))
        t.append(i/10); w.append(float(max(d, key=lambda r: r[2])[2]*2) if d is not None and len(d) else np.nan)
    return np.array(t), np.array(w)


def best_window(t, w, L, avoid=None):
    """steadiest face-size stretch of length L; avoid = (a, b) span to stay out of when there is room"""
    cands = []
    for s in np.arange(0, t[-1] - L + 0.01, 0.5):
        m = (t >= s) & (t < s + L); v = w[m]
        if np.isnan(v).mean() > 0.2: continue
        cv = float(np.nanstd(v)/np.nanmean(v)); overlap = avoid is not None and s < avoid[1] and s + L > avoid[0]
        cands.append((overlap, cv, float(s)))
    if not cands: return None
    return min(cands)


def plan(a):
    src_len = dur(a.source); v_len = dur(a.voice); hidden = [tuple(map(float, h.split("-"))) for h in a.hidden]
    print(f"take {src_len:.1f}s, voice {v_len:.1f}s")
    if v_len + 1.5 <= src_len and not a.force:
        print("one window is enough: use scripts/talking_head.py (pass --force to split anyway)"); return None
    if a.split is not None: split = a.split
    else:
        ok = [(abs(g - v_len/2), g) for g, gl in gaps(a.words) if any(x <= g <= y for x, y in hidden)
              and g + 1.5 <= src_len and v_len - g + 1.5 <= src_len]
        if not ok: sys.exit("no word gap inside a --hidden span leaves both parts shorter than the take minus 1.5 s: "
                            "shorten the script, add a full-screen insert where the split can go, or get a longer take")
        split = min(ok)[1]
    if not any(x <= split <= y for x, y in hidden): print(f"WARNING: split {split:.2f}s is not inside a --hidden span; the join will be visible")
    lens = [split, v_len - split]
    if max(lens) + 1.5 > src_len: sys.exit(f"a part is {max(lens):.1f}s; the take allows {src_len - 1.5:.1f}s per part")
    print(f"split at {split:.2f}s: parts {lens[0]:.2f}s + {lens[1]:.2f}s; finding a face window for each (local, free)")
    t, w = face_track(a.source); wins = []
    for k, L in enumerate(lens):
        b = best_window(t, w, L + 1.5, (wins[0], wins[0] + lens[0] + 1.5) if wins else None)
        if b is None: sys.exit(f"part {k}: no stretch of the take with a steady, visible face for {L + 1.5:.1f}s")
        wins.append(b[2]); print(f"part {k}: voice {0 if k == 0 else split:.2f}-{split if k == 0 else v_len:.2f}s -> take window {b[2]:.1f}-{b[2] + L + 1.5:.1f}s"
                                  f" (size variation {b[1]:.3f}{', overlaps part 0' if b[0] else ''})")
    cost = v_len/60*5 + (math.ceil(v_len)*0.14 if a.matte == "bria" else 0)
    print(f"split at {split:.2f}s; estimated spend ~${cost:.2f} (sync.so v2 pro ~$5/min" + (", Bria ~$0.14/s)" if a.matte == "bria" else "; matte local, free)"))
    return split, lens, wins


def run(a):
    p = plan(a)
    if p is None or a.dry_run or a.cmd == "plan":
        if a.dry_run: print("DRY RUN: nothing sent to fal"); return
        return
    import talking_head as th
    split, lens, wins = p; W = pathlib.Path(a.work); W.mkdir(parents=True, exist_ok=True); parts = []
    for k, (ss, to) in enumerate([(0, split), (split, None)]):
        P = W/f"part{k}"; P.mkdir(exist_ok=True); ns = SimpleNamespace(work=P, source=a.source, script=None, ref=None)
        if not (P/"voice.wav").exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(ss)] + (["-to", str(to)] if to else []) + ["-i", a.voice, "-ar", "48000", str(P/"voice.wav")], check=True)
        if not (P/"window.json").exists():
            json.dump({"t0": wins[k], "len": dur(P/"voice.wav") + 1.5, "cv": None}, open(P/"window.json", "w"))
        th.crop(ns); th.sync(ns); th.paste(ns); parts.append(P/"talking_head.mp4")
    joined = W/"talking_head.mp4"
    if not joined.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(parts[0]), "-i", str(parts[1]), "-i", a.voice, "-filter_complex",
                        "[0:v]fps=30,setpts=PTS-STARTPTS[a];[1:v]fps=30,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]",
                        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(joined)], check=True)
    print(f"joined {dur(joined):.2f}s (voice {dur(a.voice):.2f}s)")
    cut = W/"cutout.webm"
    if not cut.exists():
        if a.matte == "bria": th.cutout(SimpleNamespace(work=W, source=a.source, script=None, ref=None))
        else: subprocess.run([sys.executable, str(ROOT/"scripts"/"matte.py"), str(joined), str(cut)], check=True)
    print("cutout", cut, "- next: toolbox/matte_coverage.py", cut, "and scripts/syncnet_qa.py on each part")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("plan", "run"):
        s = sp.add_parser(n); s.add_argument("--work", required=True); s.add_argument("--source", required=True); s.add_argument("--voice", required=True)
        s.add_argument("--words", required=True, help="Whisper word json of the voice"); s.add_argument("--hidden", action="append", required=True, help="a-b seconds with the presenter off screen")
        s.add_argument("--split", type=float); s.add_argument("--matte", choices=["local", "bria"], default="local"); s.add_argument("--force", action="store_true")
        s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(); run(a)


if __name__ == "__main__":
    main()
