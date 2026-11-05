#!/usr/bin/env python3
"""Generate footage and stills on Replicate. THIS SPENDS REAL MONEY.

    # see what a model costs and what it wants, without spending anything
    python3 scripts/generate.py --list
    python3 scripts/generate.py --schema seedance

    # generate
    python3 scripts/generate.py seedance "aerial over a coastal city at golden \\
        hour, slow push in, no people" --out public/footage/city.mp4
    python3 scripts/generate.py nano "character sheet, front three-quarter and \\
        profile, white background, PHOTOGRAPH not illustration" --out gen/sheet.png

    # everything is a dry run until you pass --go
    #   without --go it prints the exact payload and the price and stops.

Reads REPLICATE_API_TOKEN from the engine-root .env. Never prints it.

WHY THIS SCRIPT EXISTS RATHER THAN A RAW API CALL
-------------------------------------------------
Three things went wrong repeatedly when people called these models directly,
and all three are handled here:

  1. Silent overspend. Every call below is a DRY RUN unless you pass --go, and
     it tells you the price first. A batch submitted by accident is the most
     expensive mistake available in this pipeline.
  2. Wrong model for the job. The routing table below is not a preference list,
     it is a record of what each model refuses. Read ROUTING before picking.
  3. Wrong output size. nano-banana returns sizes nobody asked for, so anything
     destined for a 1080x1920 frame gets normalised on download.

NOT VERIFIED: no call in this file has been executed. It is assembled from the
project's own working runner and its documented parameters, but the first
person to run it should start with ONE cheap image and check the result before
batching anything. See docs/70-playbook-and-failures.md, "checkpoint one shot
end to end before batching".
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

API = "https://api.replicate.com/v1"
ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# ROUTING. Pick by what a model REFUSES, not by what looks best.
# ---------------------------------------------------------------------------
#
# video
#   seedance   Best landscapes and action, best motion. REFUSES ANY HUMAN FACE
#              AS INPUT — image-to-video, reference images, even a white-
#              background character sheet. Text-to-video with people in the
#              prompt is fine. Native audio is fine.
#   veo        The only one that takes a face input WITH native audio and lip
#              sync. Refuses weapon-over-person two-shots. Rate-limits hard, so
#              submit sequentially and back off ~45s on a 429. Drifts in the
#              last ~0.5s (props vanish, faces bruise) so trim the tail early.
#   kling      Takes faces and props together. No audio on this Replicate tier;
#              the multi-shot native-audio version is Kling's own app, which is
#              a different pipeline (docs/60-format-kling-dialogue.md).
#
# image
#   nano       General stills, sheets, edits. Cheap. RETURNS WRONG SIZES —
#              always normalised here. Note the sibling Gemini image models
#              REJECT identity-matching prompts outright: asking for "the same
#              man, identical bone structure" from a supplied photo trips a
#              likeness filter and fails in seconds with no error text.
#
# The rule that follows from that last point: ANY reference-consistency work
# (make this the same person from another angle) goes to Kling's own image
# models, not here. And the graded hero compile goes to a gpt-image class model,
# which holds an analog grade the cheap models lose. The spread across image
# models is roughly 17x, so route deliberately.
#
# ONE MORE, LEARNED EXPENSIVELY: never attach a character sheet to a shot where
# the face is not visible. The model resolves the contradiction by rendering the
# face somewhere anyway — a duplicate second person, or a shadow figure on the
# wall. For from-behind framings, drop the sheet and let wardrobe carry
# identity.
MODELS = {
    "seedance": {
        "slug": "bytedance/seedance-2.0",
        "kind": "video",
        "defaults": {"duration": 5, "resolution": "1080p", "aspect_ratio": "9:16"},
        "note": "landscapes/action. REFUSES human face inputs of any kind.",
    },
    "veo": {
        "slug": "google/veo-3.1",
        "kind": "video",
        "defaults": {"duration": 8, "resolution": "1080p", "aspect_ratio": "9:16"},
        "note": "face input + native audio + lip sync. Rate-limits. Trim the tail.",
    },
    "kling": {
        "slug": "kwaivgi/kling-v2.5-turbo-pro",
        "kind": "video",
        "defaults": {"duration": 5, "aspect_ratio": "9:16"},
        "note": "faces + props, no audio on this tier.",
    },
    "nano": {
        "slug": "google/nano-banana-pro",
        "kind": "image",
        "defaults": {},
        "note": "stills, sheets, edits. Cheap. Returns wrong sizes — normalised on download.",
    },
}

# Frame the whole pipeline targets. nano in particular ignores requested sizes.
TARGET_W, TARGET_H = 1080, 1920


def token() -> str:
    env = ROOT.parent / ".env"          # the engine root, beside CLAUDE.md
    if not env.exists():
        sys.exit(f"no {env}. See docs/00-keys-and-accounts.md")
    for line in env.read_text().splitlines():
        if line.startswith("REPLICATE_API_TOKEN="):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    sys.exit("REPLICATE_API_TOKEN not set in .env")


def call(url: str, tok: str, data=None):
    req = urllib.request.Request(url, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    body = json.dumps(data).encode() if data else None
    with urllib.request.urlopen(req, body) as r:
        return json.load(r)


def schema(name: str) -> None:
    """Print a model's real input schema. Free — no prediction is created."""
    m = MODELS[name]
    d = call(f"{API}/models/{m['slug']}", token())
    props = (d.get("latest_version", {}).get("openapi_schema", {})
              .get("components", {}).get("schemas", {})
              .get("Input", {}).get("properties", {}))
    print(f"{m['slug']}  ({m['kind']})\n{m['note']}\n")
    for k, v in sorted(props.items(), key=lambda kv: kv[1].get("x-order", 99)):
        bits = [v.get("type", "?")]
        if "default" in v:
            bits.append(f"default={v['default']!r}")
        if "enum" in v:
            bits.append(f"enum={v['enum']}")
        print(f"  {k:<24} {' '.join(bits)}")
        if v.get("description"):
            print(f"  {'':<24} {v['description'][:100]}")


def normalise(path: pathlib.Path) -> None:
    """Force an image to the target frame. nano-banana ignores size requests."""
    out = path.with_suffix(".norm" + path.suffix)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(path),
         "-vf", (f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
                 f"crop={TARGET_W}:{TARGET_H}"),
         str(out)], check=True)
    out.replace(path)
    print(f"normalised to {TARGET_W}x{TARGET_H}")


def run(name: str, prompt: str, out: str | None, extra: dict, go: bool) -> int:
    m = MODELS[name]
    payload = {**m["defaults"], **extra, "prompt": prompt}

    print(f"model    {m['slug']}")
    print(f"note     {m['note']}")
    print("payload  " + json.dumps(payload, indent=2).replace("\n", "\n         "))

    if m["kind"] == "video":
        secs = payload.get("duration", "?")
        print(f"\nCOST     a {secs}s clip. Replicate bills per second of output "
              f"and the exact rate is on the model page.")
    else:
        print("\nCOST     one image. Cheapest of the image tier, but the spread "
              "across image models is ~17x — check you picked the right one.")

    if not go:
        print("\nDRY RUN. Nothing was submitted and nothing was charged.")
        print("Re-run with --go to actually generate.")
        return 0

    tok = token()
    pred = call(f"{API}/models/{m['slug']}/predictions", tok, {"input": payload})
    pid = pred["id"]
    print(f"\nprediction {pid}", file=sys.stderr)

    # Poll gently. Status APIs in this space lag badly; a finished job can keep
    # reporting an in-progress state for minutes. NEVER resubmit because a job
    # "looks stuck" — that is how a model swap gets wasted on a phantom hang.
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(5)
        pred = call(f"{API}/predictions/{pid}", tok)
        print(f"  {pred['status']}", file=sys.stderr)

    if pred["status"] != "succeeded":
        print(f"FAILED: {pred.get('error')}", file=sys.stderr)
        return 1

    res = pred["output"]
    urls = [res] if isinstance(res, str) else res
    for u in urls:
        print(u)

    if out:
        p = ROOT / out
        p.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(urls[0], p)
        print(f"saved {p}", file=sys.stderr)
        if m["kind"] == "image":
            normalise(p)

    ms = pred.get("metrics", {}).get("predict_time")
    if ms:
        print(f"took {ms:.1f}s", file=sys.stderr)
    print("\nDOWNLOAD ANYTHING YOU KEEP NOW — result URLs expire.", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", nargs="?", choices=sorted(MODELS))
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("--out", help="save here, relative to the project root")
    ap.add_argument("--set", action="append", default=[], metavar="K=V",
                    help="override a model input, repeatable. JSON values allowed")
    ap.add_argument("--go", action="store_true",
                    help="actually submit. Without it, nothing is charged")
    ap.add_argument("--list", action="store_true", help="list models and exit")
    ap.add_argument("--schema", metavar="MODEL", help="print a model's real inputs")
    a = ap.parse_args()

    if a.list:
        for k, m in MODELS.items():
            print(f"{k:<10} {m['slug']:<34} {m['kind']:<6} {m['note']}")
        return 0
    if a.schema:
        schema(a.schema)
        return 0
    if not a.model or not a.prompt:
        ap.error("need a model and a prompt (or --list / --schema)")

    extra = {}
    for kv in a.set:
        k, _, v = kv.partition("=")
        try:
            extra[k] = json.loads(v)
        except json.JSONDecodeError:
            extra[k] = v

    return run(a.model, a.prompt, a.out, extra, a.go)


if __name__ == "__main__":
    sys.exit(main())
