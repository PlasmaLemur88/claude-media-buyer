#!/usr/bin/env python3
"""Talking head: a real person saying a new script, from ONE continuous raw take of them talking to camera.
Voice clone (Seed Audio 1.0) -> 3 reads, best by transcript -> steadiest face window of the take -> tracked face crop at 25 fps
-> lip-sync (sync.so lipsync v2 pro) -> mouth-only paste-back -> green-screen cutout (Bria, 30 s chunks). All on fal.
Read guide/LIPSYNC.md first. Every step writes into --work and skips itself if its output exists (safe to re-run).

  python3 scripts/talking_head.py all --work <dir> --source <raw_take.mov> --script <script.txt> [--ref <10-30s clean audio>]
  python3 scripts/talking_head.py <step> --work <dir> ...        steps: clone read pick window crop sync paste cutout

Needs FAL_KEY in the environment, ffmpeg, whisper (openai-whisper), opencv-python-headless>=4.8 (FaceDetectorYN), numpy, pillow.
Cost per ~55 s script: clone $2.50 once, reads ~$0.30, sync.so ~$4.60 ($5/min), Bria cutout 2 calls."""
import os, sys, re, json, time, math, base64, shutil, difflib, argparse, pathlib, mimetypes, subprocess, urllib.request, urllib.error
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

FPS = 25                                     # sync.so and LatentSync both consume frames one-for-one at 25; feeding 30 drifts the mouth 20%
CROP = 720                                   # face crop side in 1080-wide source px (~2.4x face width)
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# ---------------- fal ----------------
def _key():
    k = os.environ.get("FAL_KEY")
    if not k: sys.exit("FAL_KEY not set. Put the client's own fal key in the environment; never borrow another client's.")
    return {"Authorization": "Key " + k, "Content-Type": "application/json"}
def _open(req, timeout):
    try: return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:600]
        if "Exhausted balance" in body: sys.exit("fal account is out of credit (403 'User is locked'). Top up at fal.ai/dashboard/billing, then re-run: finished steps are skipped.")
        sys.exit(f"HTTP {e.code} from {req.full_url[:80]}\n{body}")
def upload(p):
    p = pathlib.Path(p); mt = mimetypes.guess_type(p.name)[0] or "application/octet-stream"; H = _key()
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request("https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
            data=json.dumps({"content_type": mt, "file_name": p.name}).encode(), headers=H), timeout=60))
        urllib.request.urlopen(urllib.request.Request(r["upload_url"], data=p.read_bytes(), method="PUT", headers={"Content-Type": mt}), timeout=600)
        return r["file_url"]
    except Exception:
        return f"data:{mt};base64," + base64.b64encode(p.read_bytes()).decode()
def fal(endpoint, payload, poll=8):
    H = _key(); r = json.load(_open(urllib.request.Request(f"https://queue.fal.run/{endpoint}", data=json.dumps(payload).encode(), headers=H), 120))
    t0 = time.time()
    while True:
        s = json.load(_open(urllib.request.Request(r["status_url"], headers=H), 60))
        if s.get("status") == "COMPLETED": break
        if s.get("status") in ("FAILED", "ERROR"): sys.exit(f"fal {endpoint} failed: {s}")
        time.sleep(poll)
    out = json.load(_open(urllib.request.Request(r["response_url"], headers=H), 120)); print(f"  {endpoint}: {round(time.time()-t0)}s"); return out
def url_of(out, key):
    v = out.get(key) or out; return v["url"] if isinstance(v, dict) else v
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode())
def sh(*cmd, **kw): return subprocess.run([str(c) for c in cmd], check=True, **kw)

# ---------------- steps ----------------
def clone(a):
    st = a.work/"clone.json"
    if st.exists(): print("clone: have", json.load(open(st))["speaker_id"]); return
    ref = a.ref or (a.work/"ref.wav")
    if not a.ref:                                   # first 27 s of the source's own audio (same room, same mic as the face)
        sh("ffmpeg","-y","-v","error","-i",a.source,"-t","27","-vn","-ac","1","-ar","44100","-af","highpass=f=70",ref)
    if dur(ref) > 30: sys.exit("voice reference must be <= 30 s")
    out = fal("bytedance/seed-audio-1.0/voice-clone", {"audio_url": upload(ref), "language": "en"})
    sid = out.get("speaker_id") or out.get("voice"); json.dump({"speaker_id": sid, "ref": str(ref), "at": time.strftime("%Y-%m-%d")}, open(st, "w"), indent=2)
    print("clone:", sid, "(~$2.50, valid ~12 months; reuse it for every script with this person)")
def read(a):
    tk = a.work/"takes"; tk.mkdir(exist_ok=True); sid = json.load(open(a.work/"clone.json"))["speaker_id"]; text = pathlib.Path(a.script).read_text().strip()
    for i in (1, 2, 3):
        if (tk/f"t{i}.wav").exists(): continue
        out = fal("bytedance/seed-audio-1.0", {"prompt": text, "voice": sid, "speed": 1.0, "pitch": 0, "output_format": "wav", "sample_rate": 48000})
        raw = tk/f"t{i}_raw.wav"; urllib.request.urlretrieve(url_of(out, "audio"), raw)
        sh("ffmpeg","-y","-v","error","-i",raw,"-af","silenceremove=stop_periods=-1:stop_duration=0.30:stop_threshold=-40dB:stop_silence=0.25,atempo=1.15,loudnorm=I=-16:TP=-1.5:LRA=9","-ar","48000","-ac","1",tk/f"t{i}.wav")
        sh("whisper",tk/f"t{i}.wav","--model","small.en","--language","en","--output_format","txt","--output_dir",tk,"--fp16","False","--verbose","False", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"read: take {i} {dur(tk/f't{i}.wav'):.1f}s")
def pick(a):
    if (a.work/"voice.wav").exists(): return
    norm = lambda t: re.sub(r"[^a-z ]", "", re.sub(r"[\d$,]+", "", t.lower().replace("-", " "))).split()
    ref = norm(pathlib.Path(a.script).read_text()); best = None
    for i in (1, 2, 3):
        r = difflib.SequenceMatcher(None, ref, norm((a.work/"takes"/f"t{i}.txt").read_text())).ratio(); d = dur(a.work/"takes"/f"t{i}.wav")
        print(f"pick: take {i} match {r:.3f} {d:.1f}s")
        if best is None or r > best[0] + 0.005 or (abs(r - best[0]) <= 0.005 and d < best[2]): best = (r, i, d)
    shutil.copy(a.work/"takes"/f"t{best[1]}.wav", a.work/"voice.wav"); print(f"pick: take {best[1]}  (LISTEN to it before paying for lip-sync)")
    sh("whisper",a.work/"voice.wav","--model","small.en","--language","en","--word_timestamps","True","--output_format","json","--output_dir",a.work,"--fp16","False","--verbose","False", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def _detector(w, h):
    import cv2
    m = pathlib.Path(__file__).parent/"yunet.onnx"
    if not m.exists(): urllib.request.urlretrieve(YUNET_URL, m)
    return cv2.FaceDetectorYN.create(str(m), "", (w, h), 0.7)
def _frames(src, t0=None, L=None, fps=FPS, w=1080, h=1920):
    pre = ["-ss", str(t0), "-t", str(L)] if t0 is not None else []
    p = subprocess.Popen(["ffmpeg","-v","error",*pre,"-i",str(src),"-vf",f"fps={fps},scale={w}:{h}","-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w*h*3)
        if len(b) < w*h*3: break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
def _enc(path, w, h, audio=None, outfps=None):
    a_ = ["-i", str(audio), "-c:a", "aac", "-b:a", "160k", "-shortest"] if audio else []; vf = ["-vf", f"fps={outfps}"] if outfps else []
    return subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{w}x{h}","-r",str(FPS),"-i","-",*a_,*vf,"-c:v","libx264","-crf","16","-pix_fmt","yuv420p",str(path)], stdin=subprocess.PIPE)
def window(a):
    """steadiest stretch of the take (least change in face size) that is voice + 1.5 s long"""
    wf = a.work/"window.json"
    if wf.exists(): return json.load(open(wf))["t0"]
    import cv2
    det = _detector(540, 960); rows = []
    for i, f in enumerate(_frames(a.source, fps=10)):
        _, d = det.detect(cv2.resize(cv2.cvtColor(f, cv2.COLOR_RGB2BGR), (540, 960)))
        rows.append((i/10, float(max(d, key=lambda r: r[2])[2]*2) if d is not None and len(d) else np.nan))
    t = np.array([r[0] for r in rows]); w = np.array([r[1] for r in rows]); L = dur(a.work/"voice.wav") + 1.5
    if t[-1] < L: sys.exit(f"source is {t[-1]:.1f}s but the voice needs {L:.1f}s of continuous face. Shorten the script or get a longer take. Never loop footage.")
    best = min((np.nanstd(w[(t >= s) & (t < s+L)])/np.nanmean(w[(t >= s) & (t < s+L)]), s) for s in np.arange(0, t[-1]-L+0.01, 0.5))
    json.dump({"t0": float(best[1]), "len": L, "cv": float(best[0])}, open(wf, "w")); print(f"window: {best[1]:.1f}-{best[1]+L:.1f}s (size variation {best[0]:.3f})"); return best[1]
def crop(a):
    if (a.work/"face_crop25.mp4").exists(): return
    import cv2
    T0 = window(a); L = dur(a.work/"voice.wav") + 1.5; det = _detector(540, 960); fr = list(_frames(a.source, T0, L)); n = len(fr)
    cx, cy, mx, my, mw = (np.full(n, np.nan) for _ in range(5))
    for i, f in enumerate(fr):
        _, d = det.detect(cv2.resize(cv2.cvtColor(f, cv2.COLOR_RGB2BGR), (540, 960)))
        if d is not None and len(d):
            b = max(d, key=lambda r: r[2])*2; cx[i] = b[0]+b[2]/2; cy[i] = b[1]+b[3]*0.62; mx[i] = (b[10]+b[12])/2; my[i] = (b[11]+b[13])/2; mw[i] = abs(b[12]-b[10])
    for v in (cx, cy, mx, my, mw):
        m = np.isnan(v); v[m] = np.interp(np.flatnonzero(m), np.flatnonzero(~m), v[~m])
    sm = lambda v, k: np.convolve(np.pad(v, k//2, mode="edge"), np.ones(k)/k, mode="valid")
    x0 = np.clip(sm(cx, 11) - CROP/2, 0, 1080 - CROP).astype(int); y0 = np.clip(sm(cy, 11) - CROP/2, 0, 1080 - CROP).astype(int)
    json.dump({"x0": x0.tolist(), "y0": y0.tolist(), "mx": sm(mx, 5).tolist(), "my": sm(my, 5).tolist(), "mw": sm(mw, 9).tolist(), "T0": T0}, open(a.work/"track.json", "w"))
    ef = _enc(a.work/"face_crop25.mp4", 1024, 1024); eb = _enc(a.work/"body25.mp4", 1080, 1080)
    for f, x, y in zip(fr, x0, y0):
        ef.stdin.write(np.asarray(Image.fromarray(f[y:y+CROP, x:x+CROP]).resize((1024, 1024), Image.LANCZOS)).tobytes()); eb.stdin.write(f[0:1080].tobytes())
    for e in (ef, eb): e.stdin.close(); e.wait()
    print(f"crop: {n} frames at {FPS} fps from {T0:.1f}s")
def sync(a):
    if (a.work/"sync_raw.mp4").exists(): return
    out = fal("fal-ai/sync-lipsync/v2/pro", {"video_url": upload(a.work/"face_crop25.mp4"), "audio_url": upload(a.work/"voice.wav"), "sync_mode": "cut_off"}, poll=10)
    urllib.request.urlretrieve(url_of(out, "video"), a.work/"sync_raw.mp4"); print(f"sync: {dur(a.work/'sync_raw.mp4'):.1f}s  (~$5/min)")
def paste(a):
    """replace only a feathered ellipse around the mouth; everything else stays the real footage"""
    if (a.work/"talking_head.mp4").exists(): return
    tr = json.load(open(a.work/"track.json")); nf = int(round(dur(a.work/"voice.wav")*FPS)); S = CROP
    face = subprocess.Popen(["ffmpeg","-v","error","-i",str(a.work/"sync_raw.mp4"),"-vf",f"fps={FPS},scale={S}:{S}:flags=lanczos","-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
    faces = []
    while True:
        b = face.stdout.read(S*S*3)
        if len(b) < S*S*3: break
        faces.append(np.frombuffer(b, np.uint8).reshape(S, S, 3))
    body = subprocess.Popen(["ffmpeg","-v","error","-i",str(a.work/"body25.mp4"),"-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
    e = _enc(a.work/"talking_head.mp4", 1080, 1080, audio=a.work/"voice.wav", outfps=30)
    for i in range(nf):
        rb = body.stdout.read(1080*1080*3)
        if len(rb) < 1080*1080*3: break
        fr = np.frombuffer(rb, np.uint8).reshape(1080, 1080, 3).astype(np.float32).copy(); fc = faces[min(i, len(faces)-1)].astype(np.float32)
        x, y = tr["x0"][i], tr["y0"][i]; w = tr["mw"][i]*1.3; cxp, cyp = tr["mx"][i]-x, tr["my"][i]-y + w*0.25
        m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).ellipse([cxp-w*1.05, cyp-w*0.95, cxp+w*1.05, cyp+w*0.95], fill=255)
        M = np.asarray(m.filter(ImageFilter.GaussianBlur(max(8, w*0.18))), np.float32)[..., None]/255
        fr[y:y+S, x:x+S] = fr[y:y+S, x:x+S]*(1-M) + fc*M; e.stdin.write(fr.astype(np.uint8).tobytes())
    e.stdin.close(); e.wait(); print("paste: talking_head.mp4 (1080 square, 30 fps, with voice)")
def cutout(a):
    """Bria takes <= 30 s per call: split into equal chunks, matte each, concat the alphas, merge with the full-quality RGB"""
    if (a.work/"cutout.webm").exists(): return
    src = a.work/"talking_head.mp4"; L = dur(src); K = math.ceil(L/29.5); P = L/K; ins = []; fil = ""
    for k in range(K):
        part = a.work/f"part_{k}.mp4"; bria = a.work/f"bria_{k}.webm"
        if not bria.exists():
            sh("ffmpeg","-y","-v","error","-ss",f"{P*k:.3f}","-t",f"{P:.3f}","-i",src,"-an","-c:v","libx264","-crf","14","-pix_fmt","yuv420p",part)
            out = fal("bria/video/background-removal", {"video_url": upload(part), "background_color": "Transparent", "output_container_and_codec": "webm_vp9", "preserve_audio": False}, poll=10)
            urllib.request.urlretrieve(url_of(out, "video"), bria)          # each chunk gets its own file: never share one output name between parallel jobs
        ins += ["-c:v", "libvpx-vp9", "-i", str(bria)]; fil += f"[{k+1}:v]fps=30,alphaextract,format=gray[a{k}];"
    cat = "".join(f"[a{k}]" for k in range(K))
    sh("ffmpeg","-y","-v","error","-i",src,*ins,"-filter_complex",f"{fil}{cat}concat=n={K}:v=1:a=0[a];[0:v]fps=30,format=rgb24[c];[c][a]alphamerge,format=yuva420p[v]",
       "-map","[v]","-c:v","libvpx-vp9","-pix_fmt","yuva420p","-b:v","0","-crf","24","-row-mt","1","-an",a.work/"cutout.webm")
    print(f"cutout: cutout.webm ({K} Bria chunks)")

STEPS = {"clone": clone, "read": read, "pick": pick, "window": window, "crop": crop, "sync": sync, "paste": paste, "cutout": cutout}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("step", choices=list(STEPS) + ["all"]); ap.add_argument("--work", required=True, type=pathlib.Path)
    ap.add_argument("--source"); ap.add_argument("--script"); ap.add_argument("--ref"); a = ap.parse_args(); a.work.mkdir(parents=True, exist_ok=True)
    for s in (STEPS if a.step == "all" else [a.step]): STEPS[s](a)
