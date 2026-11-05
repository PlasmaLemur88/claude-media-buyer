#!/usr/bin/env python3
"""Cinematic drone bed in C Phrygian. Original composition, zero rights risk.

    python3 scripts/bed.py [out.wav]    # default: motion-graphics/public/audio/bed_phrygian.wav

Harmony, matched to a reference ad by per-second FFT (45-400 Hz):
    0-3s  C   (C2 C3 G3)      i
    3-4s  Db  (Db3 F3 F4)     bII  <- the Neapolitan doing all the work
    4-6s  Eb  (Eb2 Bb3 C4)    III
    6-8s  C   (C2 C3 C4)      i
    8-9s  Db  (Db2 F3 C4)     bII

No percussion, no melody. Sustained pad over a C pedal, so it loops without a
downbeat and the wrap is inaudible under a read of any length.

Output: motion-graphics/public/audio/bed_phrygian.wav. Not kept in git: setup.sh and
motion-graphics/build.sh run this when the file is missing.
"""
import pathlib

import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as sig

import sys
OUT = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else
       pathlib.Path(__file__).resolve().parent.parent / "motion-graphics" / "public" / "audio" / "bed_phrygian.wav")
SR = 48000
DUR = 10.0
N = int(SR * DUR)
t = np.arange(N) / SR


def hz(name):
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "D#": 3, "E": 4, "F": 5,
             "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "G#": 8, "A": 9, "Bb": 10, "B": 11}
    p, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** (((o + 1) * 12 + names[p] - 69) / 12.0)


# (start, end, [notes]) — overlapping so chords crossfade into each other
CHORDS = [
    (0.0, 3.4, ["C2", "C3", "G3", "C4"]),
    (2.8, 4.4, ["Db2", "Db3", "F3", "F4"]),
    (3.9, 6.4, ["Eb2", "Bb3", "C4", "G4"]),
    (5.9, 8.4, ["C2", "C3", "G3", "C4"]),
    (7.9, 10.0, ["Db2", "Db3", "F3", "C4"]),
]

# harmonic weights — mild sawtooth, warm not buzzy
HARMONICS = [(1, 1.0), (2, 0.45), (3, 0.22), (4, 0.12), (5, 0.07), (6, 0.04)]
DETUNE = [-6.0, 0.0, 6.0]  # cents, three-voice unison for width


def env(start, end, attack=0.9, release=1.1):
    """Smooth raised-cosine envelope over [start, end]."""
    e = np.zeros(N)
    i0, i1 = int(start * SR), min(int(end * SR), N)
    if i1 <= i0:
        return e
    e[i0:i1] = 1.0
    a = int(attack * SR)
    if a > 0:
        k = min(a, i1 - i0)
        e[i0:i0 + k] *= 0.5 * (1 - np.cos(np.linspace(0, np.pi, k)))
    r = int(release * SR)
    if r > 0:
        k = min(r, i1 - i0)
        e[i1 - k:i1] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, k)))
    return e


left = np.zeros(N)
right = np.zeros(N)

for start, end, notes in CHORDS:
    e = env(start, end)
    for ni, name in enumerate(notes):
        f0 = hz(name)
        # roll off the upper voices so the low end stays the anchor
        voice_gain = 1.0 if ni == 0 else 0.55 / (1 + 0.35 * ni)
        for di, cents in enumerate(DETUNE):
            f = f0 * 2 ** (cents / 1200.0)
            # slow drift so it never sounds static
            drift = 1 + 0.0007 * np.sin(2 * np.pi * (0.07 + 0.013 * ni) * t + ni)
            phase = 2 * np.pi * f * t * drift + (ni * 1.7 + di * 0.9)
            v = np.zeros(N)
            for h, amp in HARMONICS:
                if f * h > 9000:
                    break
                v += amp * np.sin(phase * h)
            v *= e * voice_gain
            # spread the detuned voices across the stereo field
            pan = 0.5 + 0.32 * (di - 1)
            left += v * (1 - pan)
            right += v * pan

# air layer: filtered noise, very low, gives the pad some breath
rng = np.random.default_rng(3)
noise = rng.standard_normal(N)
b, a = sig.butter(2, [180 / (SR / 2), 2400 / (SR / 2)], btype="band")
noise = sig.lfilter(b, a, noise)
noise *= 0.06 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t))
left += noise
right += sig.lfilter(b, a, rng.standard_normal(N)) * 0.06

# Slow lowpass sweep, opens toward the Eb then closes — movement without a
# melody. Filtering block-by-block with a re-designed filter clicks at every
# block edge (a ~23 Hz ratchet). Instead: filter the whole signal at a few fixed
# cutoffs and crossfade between them. Each layer is continuous and the weights
# are smooth, so the result has no discontinuities anywhere.
stereo = np.stack([left, right])
cut_lo, cut_hi = 900.0, 3200.0
sweep = cut_lo + (cut_hi - cut_lo) * (0.5 - 0.5 * np.cos(2 * np.pi * t / DUR))

BANDS = np.geomspace(cut_lo, cut_hi, 9)
layers = []
for fc in BANDS:
    bb, aa = sig.butter(2, fc / (SR / 2), btype="low")
    layers.append(sig.lfilter(bb, aa, stereo, axis=1))

out = np.zeros_like(stereo)
idx = np.interp(sweep, BANDS, np.arange(len(BANDS)))
lo = np.clip(np.floor(idx).astype(int), 0, len(BANDS) - 2)
frac = idx - lo
for k in range(len(BANDS) - 1):
    m = lo == k
    if not m.any():
        continue
    w = np.zeros(N)
    w[m] = 1 - frac[m]
    out += layers[k] * w
    w = np.zeros(N)
    w[m] = frac[m]
    out += layers[k + 1] * w

# master fades, and normalise to leave headroom for VO
master = env(0.0, DUR, attack=1.4, release=1.6)
out *= master
out /= np.abs(out).max()
out *= 0.72

OUT.parent.mkdir(parents=True, exist_ok=True)
wav.write(str(OUT), SR, (out.T * 32767).astype(np.int16))
print(f"wrote {OUT}")
