#!/usr/bin/env python3
"""Check a VO take for intonation problems you would otherwise have to hear.

    python3 scripts/prosody.py brands/<slug>/assets/audio/vo_101.mp3 brands/<slug>/assets/words/101.json

Reports, per sentence-final word, whether pitch RISES or FALLS across the word.
A statement should fall. A rising terminal on a statement is uptalk: it makes
the line sound uncertain or like a question, and it is the single most common
way a TTS take sounds "off" while every word is still correct.

Also flags long gaps and words delivered much faster or slower than the take's
own average, which is how dropped or rushed phrases show up numerically.

Rule of thumb from the takes measured so far: anything above +6 Hz across a
sentence-final word is audible as uptalk. The fix that works: regenerate with
lower exaggeration, and replace any ellipsis before the offending sentence with
a hard stop.

THIS DOES NOT REPLACE LISTENING. It catches a defect class that ears miss on a
tired third pass; ears catch everything it cannot measure.
"""
import json
import sys
import warnings

import librosa
import numpy as np

warnings.filterwarnings("ignore")

UPTALK_HZ = 6.0
LONG_GAP_S = 0.9


def main(wav_path: str, words_path: str) -> None:
    y, sr = librosa.load(wav_path, sr=22050)
    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=350, sr=sr, frame_length=1024)
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    words = json.load(open(words_path))

    def contour(a: float, b: float):
        m = (times >= a) & (times < b) & voiced
        v = f0[m]
        return v[~np.isnan(v)]

    print(f"{wav_path}  ({words[-1]['e']:.2f}s, {len(words)} words)\n")
    print("SENTENCE ENDINGS  (a statement should fall)")
    problems = 0
    for w in words:
        if not w["w"].endswith((".", "?", "!")):
            continue
        # A question SHOULD rise. Flagging it was a false positive on a hook.
        if w["w"].endswith("?"):
            continue
        v = contour(w["s"], w["e"])
        if len(v) < 6:
            print(f"  {w['s']:6.2f}  {w['w']:<14} not enough voiced pitch to measure")
            continue
        half = len(v) // 2
        delta = v[half:].mean() - v[:half].mean()
        if delta > UPTALK_HZ:
            tag, bad = "RISES  <-- uptalk", True
        elif delta < -UPTALK_HZ:
            tag, bad = "falls", False
        else:
            tag, bad = "flat", False
        problems += bad
        print(f"  {w['s']:6.2f}  {w['w']:<14} {v.mean():5.0f} Hz  {delta:+6.1f} Hz  {tag}")

    print("\nLONG GAPS  (a stutter or a dropped phrase often hides in one)")
    for i in range(1, len(words)):
        gap = words[i]["s"] - words[i - 1]["e"]
        if gap >= LONG_GAP_S:
            print(f"  {words[i-1]['e']:6.2f}  {gap:.2f}s after {words[i-1]['w']!r}")

    durs = np.array([w["e"] - w["s"] for w in words])
    slow = [w for w, d in zip(words, durs) if d > durs.mean() + 3 * durs.std()]
    if slow:
        print("\nUNUSUALLY LONG WORDS  (whisper collapsing speech it failed to transcribe)")
        for w in slow:
            print(f"  {w['s']:6.2f}  {w['w']!r} spans {w['e']-w['s']:.2f}s")

    print(f"\n{problems} uptalk problem(s)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: prosody.py <vo.wav> <words.json>")
    main(sys.argv[1], sys.argv[2])
