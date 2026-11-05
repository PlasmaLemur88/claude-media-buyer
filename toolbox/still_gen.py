#!/usr/bin/env python3
"""Generate a still that reads as an ordinary phone photo, not an AI render (Nano Banana through the Gemini API).

  python3 toolbox/still_gen.py "<what is in the picture>" --out still.png [--aspect 9:16] [--n 1] [--dry-run] [--strict]

The realism rules are appended to every prompt: candid phone photo, plain uneven light, real clutter, printed text
out of focus, no logos. The prompt is also linted for the things that make a still read as generated or staged
(posed smiling groups, faces to camera, golden hour, "cinematic", "4k"); --strict turns warnings into a stop.
Needs GEMINI_API_KEY (scripts/keys.py; GOOGLE_AI_API_KEY also accepted). About $0.08 per 2K image at the time this
was written; check the current Gemini price sheet. Finish shots that go into a render with a grade (compose_shots.py
grades stills itself; scripts/grade.py for clips)."""
import argparse, base64, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
REAL = (" Candid smartphone photo taken by an ordinary person, phone camera, natural uneven light, overcast or plain midday or indoor light, "
        "slight grain, everyday unstaged moment, real clutter, slightly imperfect framing, not glossy, no HDR, no dramatic lighting, not a stock photo. "
        "People, if any, are small in frame, seen from behind, side-on or over the shoulder, never looking at the camera. "
        "Any printed text is out of focus and unreadable. No logos, no watermarks, no brand names.")
LINT = [(r"\bsmil\w*", "smiling people read as stock; show them doing something"),
        (r"\b(pos(e|ed|ing)|portrait|headshot)\b", "posed or portrait framing reads as staged"),
        (r"(look\w* (at|into) (the )?camera|facing (the )?camera|face to camera)", "faces to camera: shoot from behind, side-on or hands only"),
        (r"(close-?up of (a|her|his|their) face|big face)", "a large face has to stay the same person in motion; keep faces small"),
        (r"(golden hour|sunset|sunrise|dusk|magic hour)", "golden light is the postcard tell; use plain midday or overcast"),
        (r"\b(cinematic|epic|dramatic|stunning|perfect|pristine|glossy|luxur\w*|4k|8k|hdr|ultra[- ]?realistic)\b", "polish words push the model to the AI look"),
        (r"\bfamily\b.*\b(together|happy)\b", "a happy family together is the stock-photo cliché"),
        (r"\b(logo|brand)\b", "no real logos or brand marks")]
MODEL = "gemini-3.1-flash-image-preview"


def lint(prompt):
    return [why for pat, why in LINT if re.search(pat, prompt, re.I)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt"); ap.add_argument("--out", required=True); ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--size", default="2K"); ap.add_argument("--n", type=int, default=1, help="variants (out_1.png, out_2.png, ...)")
    ap.add_argument("--model", default=MODEL); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    warns = lint(a.prompt)
    for w in warns: print("lint:", w)
    if warns and a.strict: sys.exit("stopped by --strict")
    text = a.prompt.rstrip(".") + "." + REAL + f" Aspect {a.aspect}."
    body = {"contents": [{"parts": [{"text": text}]}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": a.aspect, "imageSize": a.size}}}
    if a.dry_run: print(f"DRY RUN {a.model} x{a.n} (~${0.08*a.n:.2f})\n" + json.dumps(body, indent=1)); return
    from keys import key
    k = key("GEMINI_API_KEY", required=False) or key("GOOGLE_AI_API_KEY"); out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    for i in range(a.n):
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{a.model}:generateContent", data=json.dumps(body).encode(),
                                     headers={"x-goog-api-key": k, "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=300)); dst = out if a.n == 1 else out.with_name(f"{out.stem}_{i+1}{out.suffix}")
        data = next((p["inlineData"]["data"] for c in r.get("candidates", []) for p in c.get("content", {}).get("parts", []) if "inlineData" in p), None)
        if not data: print("no image returned:", json.dumps(r)[:300]); continue
        dst.write_bytes(base64.b64decode(data)); print("wrote", dst)


if __name__ == "__main__":
    main()
