#!/usr/bin/env python3
"""Lock a generated construction/change clip so only the build area can move (no trees, sky, cars or neighbours
popping in). Proven 26 Sep 2026 on Veo 3.1 time-lapses (see guide/MOTION.md).
Mask = where the designed before/after stills differ (dilated, feathered). Outside the mask every frame shows the
clip's own first frame (same light as the video), inside it shows the video. python3 scripts/lock_background.py <clip.mp4> <before.png> <after.png> <out.mp4> [x0,y0,x1,y1 ROI: only this box may change]"""
import sys, subprocess, numpy as np
from PIL import Image, ImageFilter
clip, before, after, out = sys.argv[1:5]
W, H = map(int, subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",clip]).decode().strip().split(","))
b = np.asarray(Image.open(before).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32)
a = np.asarray(Image.open(after).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32)
bs = np.asarray(Image.fromarray(b.astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))).astype(np.float32)
as_ = np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))).astype(np.float32)
m = Image.fromarray(((np.abs(as_ - bs).mean(2) > 40)*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.MaxFilter(31))
import os as _os
if _os.environ.get("CLIPMASK"):  # CLIPMASK=1: mask from where the clip itself changes (use when stills don't line up)                                   # change area = where the clip itself changes vs its first frame (max over 1 s samples)
    fr = subprocess.run(["ffmpeg","-v","error","-i",clip,"-vf","fps=1","-f","rawvideo","-pix_fmt","rgb24","-"], capture_output=True).stdout
    fs = [np.asarray(Image.frombytes("RGB", (W, H), fr[i*W*H*3:(i+1)*W*H*3]).filter(ImageFilter.GaussianBlur(10))).astype(np.float32) for i in range(len(fr)//(W*H*3))]
    dm = np.max([np.abs(f - fs[0]).mean(2) for f in fs[1:]], axis=0)
    m = Image.fromarray(((dm > 30)*255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.MaxFilter(31))
if len(sys.argv) > 5:
    rx0, ry0, rx1, ry1 = map(int, sys.argv[5].split(",")); roi = Image.new("L", (W, H), 0); roi.paste(255, (rx0, ry0, rx1, ry1))
    m = Image.fromarray(np.minimum(np.asarray(m), np.asarray(roi)))
print("change area", m.getbbox(), f"{np.asarray(m).mean()/255*100:.1f}% of frame")
M = np.asarray(m.filter(ImageFilter.GaussianBlur(24))).astype(np.float32)[..., None]/255
STILL = a                                                                  # outside the build: the finished still, so no tree or sky can change
if _os.environ.get("PLATE") == "first":                                    # or the clip's own first frame (matches the start state)
    STILL = np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",clip,"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"], capture_output=True).stdout, np.uint8).reshape(H, W, 3).astype(np.float32)
rd = subprocess.Popen(["ffmpeg","-v","error","-i",clip,"-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
fps = subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=r_frame_rate","-of","csv=p=0",clip]).decode().strip()
wr = subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",fps,"-i","-","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",out], stdin=subprocess.PIPE)
first = None; n = 0
while True:
    raw = rd.stdout.read(W*H*3)
    if len(raw) < W*H*3: break
    f = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
    wr.stdin.write((STILL*(1-M) + f*M).astype(np.uint8).tobytes()); n += 1
wr.stdin.close(); wr.wait(); print("wrote", out, n, "frames")
