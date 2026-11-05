#!/usr/bin/env python3
"""Pacing check and fix for a voice read, BEFORE lip-sync.

  python3 scripts/pace.py check voice.wav [voice.json] [--speed 1.07]
      words per second as played, and the number of real pauses (> 0.35 s)
  python3 scripts/pace.py pad voice.wav voice.json out.wav
      lengthen short pauses: 0.55 s after . ? !  and 0.30 s after a comma. Same words, same voice.

Calibrated on a client ad set (Sep 2026): reads that land well run 2.9-3.5 words/s as played with 7+ pauses
a minute. One ran 4.15 with 5 pauses and read as rushed; padding added 6.2 s and brought it to 3.4.
voice.json is Whisper output with word timestamps (whisper <wav> --word_timestamps True --output_format json).
After padding, re-run Whisper and the lip-sync on the new wav, and render without a speed-up."""
import sys, json, subprocess
def words(js): return [w for s in json.load(open(js))["segments"] for w in s["words"]]
def check(wav, js, speed):
    w = words(js); span = w[-1]["end"] - w[0]["start"]
    pauses = sum(1 for a, b in zip(w, w[1:]) if b["start"] - a["end"] > 0.35)
    wps = len(w) / span * speed
    print(f"{len(w)} words, {wps:.2f} words/s as played at {speed}x, {pauses} pauses > 0.35 s"
          + ("  <- rushed: pad it" if wps > 3.6 or pauses < len(w) / 25 else "  ok"))
def pad(wav, js, out):
    w = words(js); pts = []
    for a, b in zip(w, w[1:]):
        t = a["word"].strip(); g = b["start"] - a["end"]; tgt = 0.55 if t[-1:] in ".?!" else 0.30 if t.endswith(",") else 0
        if tgt and g < tgt: pts.append(((a["end"] + b["start"]) / 2, tgt - g))
    sr, ch = subprocess.check_output(["ffprobe","-v","error","-show_entries","stream=sample_rate,channels","-of","csv=p=0",wav]).decode().split(",")[:2]
    fl, parts, prev = "", [], 0.0
    for k, (t, p) in enumerate(pts):
        fl += f"[0:a]atrim={prev}:{t},asetpts=PTS-STARTPTS[a{k}];aevalsrc=0:d={p}:s={sr}:c={'mono' if ch.strip()=='1' else 'stereo'}[s{k}];"; parts += [f"[a{k}]", f"[s{k}]"]; prev = t
    fl += f"[0:a]atrim={prev},asetpts=PTS-STARTPTS[z];"; parts.append("[z]")
    subprocess.run(["ffmpeg","-y","-v","error","-i",wav,"-filter_complex",fl+"".join(parts)+f"concat=n={len(parts)}:v=0:a=1[o]","-map","[o]",out], check=True)
    print(f"padded {len(pts)} pauses, +{sum(p for _, p in pts):.2f} s -> {out}")
if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["check"] and len(a) >= 3: check(a[1], a[2], float(a[a.index("--speed")+1]) if "--speed" in a else 1.0)
    elif a[:1] == ["pad"] and len(a) == 4: pad(a[1], a[2], a[3])
    else: sys.exit(__doc__)
