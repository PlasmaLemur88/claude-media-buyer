#!/usr/bin/env python3
"""SyncNet lip-sync TIMING check (setup + how to read it: guide/LIPSYNC.md, "QA"). python3 syncnet_qa.py <name> <video> <audio> [chunk_s]
Tracks the face (YuNet), makes a 224px crop at 25 fps (SyncNet pipeline: square 1.8x face width), muxes the audio,
scores the whole clip and each chunk: AV offset (frames, 0 = in sync) and confidence (higher = clearer sync)."""
import sys, os, json, subprocess, pathlib, numpy as np, cv2, types, logging
logging.disable(logging.WARNING)
HERE = pathlib.Path(os.environ.get("SYNCNET_DIR", pathlib.Path(__file__).parent.parent/"tools"/"syncnet")); sys.path.insert(0, str(HERE/"syncnet_python"))
from SyncNetInstance import SyncNetInstance
name, vid, aud = sys.argv[1:4]; CH = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
W, H = [int(v) for v in subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",vid]).decode().replace("\n",",").split(",") if v.strip()][:2]
raw = subprocess.run(["ffmpeg","-v","error","-i",vid,"-vf","fps=25","-f","rawvideo","-pix_fmt","bgr24","-"], capture_output=True).stdout
n = len(raw)//(W*H*3); yn = cv2.FaceDetectorYN.create(str(pathlib.Path(__file__).parent/"yunet.onnx"), "", (W//2, H//2), 0.6)
box = np.full((n, 3), np.nan)
for i in range(n):
    fr = np.frombuffer(raw[i*W*H*3:(i+1)*W*H*3], np.uint8).reshape(H, W, 3); _, d = yn.detect(cv2.resize(fr, (W//2, H//2)))
    if d is not None and len(d): b = max(d, key=lambda r: r[2])*2; box[i] = (b[0]+b[2]/2, b[1]+b[3]/2, max(b[2], b[3]))
ok = ~np.isnan(box[:,0])
for j in range(3): box[:,j] = np.convolve(np.interp(np.arange(n), np.flatnonzero(ok), box[ok,j]), np.ones(5)/5, mode="same")
T = HERE/"tmp"/name; T.mkdir(parents=True, exist_ok=True); crop = T/"crop.avi"
wr = subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","bgr24","-s","224x224","-r","25","-i","-","-i",aud,"-c:v","mpeg4","-q:v","2","-ac","1","-ar","16000","-shortest",str(crop)], stdin=subprocess.PIPE)
for i in range(n):
    fr = np.frombuffer(raw[i*W*H*3:(i+1)*W*H*3], np.uint8).reshape(H, W, 3); cx, cy, s = box[i]; s *= 0.9
    pad = cv2.copyMakeBorder(fr, int(2*s), int(2*s), int(2*s), int(2*s), cv2.BORDER_CONSTANT, value=(110,110,110))
    x0, y0 = int(cx - s + 2*s), int(cy - s + 2*s); c = pad[y0:y0+int(2*s), x0:x0+int(2*s)]
    wr.stdin.write(cv2.resize(c, (224, 224)).tobytes())
wr.stdin.close(); wr.wait()
S = SyncNetInstance(device="cpu"); S.loadParameters(str(HERE/"syncnet_python/data/syncnet_v2.model"))
opt = types.SimpleNamespace(tmp_dir=str(T/"sn"), reference="x", batch_size=20, vshift=15)
def score(path):
    off, conf, _ = S.evaluate(opt, str(path)); return int(off), round(float(conf), 2)
res = {"name": name, "face_missing_pct": round(100*(1-ok.mean()),1), "whole": score(crop), "chunks": []}
dur = n/25.0; t = 0.0
while t + 3 < dur:
    seg = T/f"seg_{int(t):03d}.avi"
    subprocess.run(["ffmpeg","-y","-v","error","-ss",str(t),"-t",str(min(CH, dur-t)),"-i",str(crop),"-c:v","mpeg4","-q:v","2","-ac","1","-ar","16000",str(seg)], check=True)
    res["chunks"].append([round(t,1)] + list(score(seg))); t += CH
print(json.dumps(res))
json.dump(res, open(T/"result.json","w"), indent=1)
