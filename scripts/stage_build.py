#!/usr/bin/env python3
"""Deterministic construction reveal from three matching stills (before / framing / finished). Only the build area changes:
the framing rises from the ground up, then the finished structure rises over it and holds. No generative motion, so nothing can pop.
python3 stage_build.py <before.png> <mid.png> <after.png> <out.mp4> [x0,y0,x1,y1 ROI: only this box may change]"""
import sys, subprocess, numpy as np
from PIL import Image, ImageFilter
bp, mp, ap, out = sys.argv[1:5]; W, H, FPS, DUR = 1080, 1920, 30, 8.0
def load(p): return Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
B, M, A = load(bp), load(mp), load(ap)
def diff(x, y):
    xs, ys = [np.asarray(i.filter(ImageFilter.GaussianBlur(10))).astype(np.float32) for i in (x, y)]; return np.abs(xs - ys).mean(2) > 36
area = Image.fromarray(((diff(A, B) | diff(M, B))*255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.MaxFilter(31))
if len(sys.argv) > 5:   # optional x0,y0,x1,y1: only this box may change (keeps a neighbour's pool from popping in)
    rx0, ry0, rx1, ry1 = map(int, sys.argv[5].split(",")); roi = Image.new("L", (W, H), 0); roi.paste(255, (rx0, ry0, rx1, ry1))
    area = Image.fromarray(np.minimum(np.asarray(area), np.asarray(roi)))
x0, y0, x1, y1 = area.getbbox(); print("build area", (x0, y0, x1, y1))
Mk = np.asarray(area.filter(ImageFilter.GaussianBlur(20))).astype(np.float32)[..., None]/255
b, m, a = [np.asarray(i).astype(np.float32) for i in (B, M, A)]
base = a                                                     # everything outside the build area is the finished photo, fixed
def rise(lo, hi, p):
    """lo -> hi revealed bottom-up across the build box; soft 90 px edge"""
    if p <= 0: return lo
    if p >= 1: return hi
    edge = 90; cut = y1 + edge - (y1 - y0 + 2*edge)*p
    ys = np.arange(H, dtype=np.float32)[:, None, None]; k = np.clip((ys - cut)/edge + 0.5, 0, 1)
    return lo*(1 - k) + hi*k
def ease(p): p = min(1, max(0, p)); return 0.5 - 0.5*np.cos(np.pi*p)
wr = subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",out], stdin=subprocess.PIPE)
for n in range(int(DUR*FPS)):
    t = n/FPS
    inner = rise(b, m, ease((t - 0.8)/1.8)) if t < 3.1 else rise(m, a, ease((t - 3.1)/1.9))
    wr.stdin.write((base*(1 - Mk) + inner*Mk).astype(np.uint8).tobytes())
wr.stdin.close(); wr.wait(); print("wrote", out)
