#!/usr/bin/env python3
"""Bring a realistic still to life with subtle, real-camera motion. Rules in guide/MOTION.md.
  People (faces, hands):      python3 scripts/motion.py kling <still.png> "<one small action>" <out.mp4>   (Kling v3 pro, fal, 5 s)
  Camera / scenery / builds:  python3 scripts/motion.py veo   <still.png> "<one small motion>" <out.mp4>   (Veo 3.1, Gemini key, 8 s 1080p)
Kling needs FAL_KEY; Veo needs GEMINI_API_KEY (in .env). Use your own keys."""
import sys, os, json, time, base64, pathlib, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
BASE = ("Real footage shot on an iPhone, natural light, photorealistic, documentary. Keep every object, building, face and word exactly as in the image. "
        "Motion is subtle and physically real. Nothing new enters the frame. ")
NEG = ("morphing, melting, warping, shape change, buildings changing, new objects, new people, faces changing, extra fingers, distorted hands, "
       "text changing, gibberish text, cartoon, CGI, animation, glossy, oversaturated, zoom, fast camera move, cut, dissolve, crossfade, slow motion, watermark")
def kling(img, motion, out):
    from talking_head import upload, fal, url_of
    o = fal("fal-ai/kling-video/v3/pro/image-to-video", {"start_image_url": upload(img), "prompt": BASE + motion, "negative_prompt": NEG,
            "duration": "5", "generate_audio": False, "cfg_scale": 0.5}, poll=10)
    urllib.request.urlretrieve(url_of(o, "video"), out)
def veo(img, motion, out, model="veo-3.1-generate-preview"):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from keys import key as _getkey
    key = _getkey("GEMINI_API_KEY")
    H = {"x-goog-api-key": key, "Content-Type": "application/json"}; G = "https://generativelanguage.googleapis.com/v1beta"
    body = {"instances": [{"prompt": BASE + motion, "image": {"bytesBase64Encoded": base64.b64encode(pathlib.Path(img).read_bytes()).decode(), "mimeType": "image/png"}}],
            "parameters": {"aspectRatio": "9:16", "durationSeconds": 8, "resolution": "1080p", "negativePrompt": NEG}}   # 1080p requires 8 s
    op = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/models/{model}:predictLongRunning", data=json.dumps(body).encode(), headers=H), timeout=300))["name"]
    while True:
        time.sleep(15); s = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/{op}", headers=H), timeout=60))
        if s.get("done"): break
    if "error" in s: sys.exit(f"veo error: {json.dumps(s)[:400]}")
    r = s["response"]; uri = (r.get("generateVideoResponse", {}).get("generatedSamples") or r.get("generatedSamples"))[0]["video"]["uri"]
    with urllib.request.urlopen(urllib.request.Request(uri, headers={"x-goog-api-key": key})) as r, open(out, "wb") as f: f.write(r.read())
if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in ("kling", "veo"): sys.exit(__doc__)
    {"kling": kling, "veo": veo}[sys.argv[1]](sys.argv[2], sys.argv[3], sys.argv[4]); print("wrote", sys.argv[4])
