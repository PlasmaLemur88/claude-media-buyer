#!/usr/bin/env python3
"""Image-to-video: bring one realistic still to life with one small, physically real motion.

  People (faces, hands, anyone doing something):   python3 toolbox/motion_runner.py kling <still.png> "<one small action>" --out a.mp4
  Camera and scenery (drone glide, water, trees):  python3 toolbox/motion_runner.py veo   <still.png> "<one small motion>" --out b.mp4
  A change between two stills (a build, a reveal): python3 toolbox/motion_runner.py veo   <first.png> "<what happens>" --last <last.png> --out c.mp4
Add --dry-run to any of them: it prints the request and the estimated cost and spends nothing.

Kling: Kling v3 pro image-to-video through fal (FAL_KEY, via scripts/fal.py), 5 s, no audio. The Kling MCP
connector can run the same model by hand; this script uses fal so it can run unattended.
Veo: Veo 3.1 through the Gemini API (GEMINI_API_KEY via scripts/keys.py; GOOGLE_AI_API_KEY is accepted too).
Veo image-to-video rejects the personGeneration parameter, so it is never sent. 1080p only comes in 8 s clips.

Overlap: scripts/motion.py does the same two calls without --dry-run, --last or the key lookup. Rules for picking
the model and judging the result: guide/MOTION.md and RULES.md section 9."""
import argparse, base64, json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))

BASE = ("Real footage shot on a phone, natural light, photorealistic, documentary. Keep every object, building, face and word exactly as in the image. "
        "Motion is subtle and physically real. Nothing new enters the frame. Same people throughout; nobody walks in or out. ")
BASE_CHANGE = ("Static camera throughout, locked off, no camera movement at all. Only the area that changes between the first and last frame changes; "
               "everything else (neighbouring buildings, trees, sky, road) stays exactly the same. People are true to scale. ")
NEG = ("morphing, melting, warping, shape change, buildings changing, new objects, new people, faces changing, extra fingers, distorted hands, "
       "text changing, gibberish text, cartoon, CGI, animation, glossy, oversaturated, zoom, fast camera move, cut, dissolve, crossfade, slow motion, watermark")
VEO_USD_PER_S = 0.40            # 1080p Veo 3.1, as billed on the project this came from; check the current Gemini price sheet
G = "https://generativelanguage.googleapis.com/v1beta"


def gemini_key():
    from keys import key
    return key("GEMINI_API_KEY", required=False) or key("GOOGLE_AI_API_KEY")


def veo(a):
    img = pathlib.Path(a.still); last = pathlib.Path(a.last) if a.last else None
    if a.resolution == "1080p" and a.duration != 8: sys.exit("Veo 3.1 at 1080p only makes 8 s clips; use --duration 8 or --resolution 720p")
    enc = lambda p: {"bytesBase64Encoded": base64.b64encode(p.read_bytes()).decode(), "mimeType": "image/png" if p.suffix.lower() == ".png" else "image/jpeg"}
    inst = {"prompt": (BASE_CHANGE if last else BASE) + a.motion, "image": enc(img)}
    if last: inst["lastFrame"] = enc(last)
    body = {"instances": [inst], "parameters": {"aspectRatio": a.aspect, "durationSeconds": a.duration, "resolution": a.resolution, "negativePrompt": NEG}}
    cost = VEO_USD_PER_S*a.duration
    if a.dry_run:
        show = json.loads(json.dumps(body))
        for k in ("image", "lastFrame"):
            if k in show["instances"][0]: show["instances"][0][k]["bytesBase64Encoded"] = f"<{len(inst[k]['bytesBase64Encoded'])} base64 chars>"
        print(f"DRY RUN veo {a.model}: ~${cost:.2f}\n" + json.dumps(show, indent=1)); return
    k = gemini_key(); H = {"x-goog-api-key": k, "Content-Type": "application/json"}
    op = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/models/{a.model}:predictLongRunning", data=json.dumps(body).encode(), headers=H), timeout=300))["name"]
    print("submitted", op, f"(~${cost:.2f}); polling every 15 s")
    while True:
        time.sleep(15); s = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/{op}", headers=H), timeout=60))
        if s.get("done"): break
    if "error" in s: sys.exit(f"veo error: {json.dumps(s)[:500]}")
    r = s["response"]; uri = ((r.get("generateVideoResponse", {}) or {}).get("generatedSamples") or r.get("generatedSamples") or [{}])[0].get("video", {}).get("uri")
    if not uri: sys.exit(f"veo returned no video (often a safety filter): {json.dumps(s)[:500]}")
    with urllib.request.urlopen(urllib.request.Request(uri, headers={"x-goog-api-key": k}), timeout=900) as resp: pathlib.Path(a.out).write_bytes(resp.read())
    print("wrote", a.out, "- check a frame strip before using it; trim the first 0.3 s if it opens on a smear")


def kling(a):
    payload = {"start_image_url": f"<upload of {a.still}>", "prompt": BASE + a.motion, "negative_prompt": NEG,
               "duration": str(a.duration), "generate_audio": False, "cfg_scale": 0.5}
    ep = "fal-ai/kling-video/v3/pro/image-to-video"
    if a.dry_run:
        print(f"DRY RUN fal {ep} (price: see fal.ai/models for {ep}; not recorded here)\n" + json.dumps(payload, indent=1)); return
    import fal
    tok = fal.token(); payload["start_image_url"] = fal.upload(a.still, tok)
    out = fal.run(ep, payload, tok); v = out.get("video") or out
    fal.download(v["url"] if isinstance(v, dict) else v, a.out); print("wrote", a.out, "- use 2.5-3 s of it; check a frame strip for new people or changing faces")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("veo", "kling"):
        s = sp.add_parser(name); s.add_argument("still"); s.add_argument("motion", help="one small action or camera move, plain words")
        s.add_argument("--out", required=True); s.add_argument("--dry-run", action="store_true", help="print the request and cost, spend nothing")
    s = sp.choices["veo"]; s.add_argument("--last", help="last-frame still: the clip moves from the first still to this one")
    s.add_argument("--duration", type=int, default=8); s.add_argument("--resolution", default="1080p", choices=["720p", "1080p"])
    s.add_argument("--aspect", default="9:16", choices=["9:16", "16:9"]); s.add_argument("--model", default="veo-3.1-generate-preview")
    sp.choices["kling"].add_argument("--duration", type=int, default=5, choices=[5, 10])
    a = ap.parse_args()
    if not pathlib.Path(a.still).exists(): sys.exit(f"no such still: {a.still}")
    {"veo": veo, "kling": kling}[a.cmd](a)


if __name__ == "__main__":
    main()
