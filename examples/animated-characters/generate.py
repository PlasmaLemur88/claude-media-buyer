#!/usr/bin/env python3
"""Generate one animated take on Replicate Seedance 2.5 (image mode).

  # one speaker, all his lines, voice ON (the take that carries the dialogue)
  python3 generate.py speaker chuy job sheets/chuy.jpg 25 out/CH_CHUY.mp4
  python3 generate.py speaker beto cab_passenger sheets/beto_cab.jpg 25 out/CH_BETO.mp4 --lines my_lines.json

  # a silent shot to lay under dialogue
  python3 generate.py cutaway sheets/twoshot.jpg 6 out/W1.mp4 "Both men stand and talk." job-site

Nothing is spent without --go. Without it the script prints the prompt and the
settings so the operator can approve them first. --lines takes a JSON list of
[direction, text] pairs; without it the example episode's lines are used.

Rules this script holds (docs/65-format-animated-characters.md):
- one generation per speaker, 30 s at most, so a voice never changes mid-scene
- image mode with the character sheet as the start frame, so size, position
  and left/right cannot drift
- seed 4242 on every take, 720p, 9:16
"""
import json, os, pathlib, sys, time, urllib.request, uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import prompts as P

MODEL = "bytedance/seedance-2.5"
SEED = 4242


def token():
    if os.environ.get("REPLICATE_API_TOKEN"):
        return os.environ["REPLICATE_API_TOKEN"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("REPLICATE_API_TOKEN=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    raise SystemExit("REPLICATE_API_TOKEN is not set in .env (see docs/00-keys-and-accounts.md)")


def upload(path, tok):
    b = pathlib.Path(path).read_bytes()
    bd = "----b" + uuid.uuid4().hex
    body = (f'--{bd}\r\nContent-Disposition: form-data; name="content"; filename="{os.path.basename(path)}"\r\n'
            "Content-Type: image/jpeg\r\n\r\n").encode() + b + f"\r\n--{bd}--\r\n".encode()
    req = urllib.request.Request("https://api.replicate.com/v1/files", data=body, headers={
        "Authorization": "Bearer " + tok, "Content-Type": "multipart/form-data; boundary=" + bd})
    return json.load(urllib.request.urlopen(req))["urls"]["get"]


def run(inp, out, tok, poll_max=1800):
    req = urllib.request.Request(f"https://api.replicate.com/v1/models/{MODEL}/predictions",
                                 data=json.dumps({"input": inp}).encode(),
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    p = json.load(urllib.request.urlopen(req))
    print(out, "started", p["id"], flush=True)
    t0 = time.time()
    while p["status"] not in ("succeeded", "failed", "canceled") and time.time() - t0 < poll_max:
        time.sleep(8)
        p = json.load(urllib.request.urlopen(urllib.request.Request(
            p["urls"]["get"], headers={"Authorization": "Bearer " + tok})))
    if p["status"] != "succeeded":
        raise SystemExit(f"{out}: {p['status']} {p.get('error')}")
    u = p["output"] if isinstance(p["output"], str) else p["output"][0]
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(u, out)
    print(out, "saved", flush=True)


def main(a):
    go = "--go" in a
    a = [x for x in a if x != "--go"]
    lines = None
    if "--lines" in a:
        i = a.index("--lines")
        lines = [tuple(x) for x in json.load(open(a[i + 1]))]
        del a[i:i + 2]
    if not a or a[0] not in ("speaker", "cutaway"):
        raise SystemExit(__doc__)
    if a[0] == "speaker":
        _, who, setting, sheet, secs, out = a
        prompt = P.speaker_prompt(who, setting, lines or P.EXAMPLE[who])
        audio = True
    else:
        _, sheet, secs, out, action, bg = a
        prompt = P.cutaway_prompt(action, bg)
        audio = False
    secs = int(secs)
    if secs > 30:
        raise SystemExit("Seedance 2.5 caps a take at 30 s: split the speaker's lines into two takes")
    words = sum(len(t.split()) for _, t in (lines or P.EXAMPLE.get(a[1], []))) if a[0] == "speaker" else 0
    print(f"model {MODEL}  start frame {sheet}  {secs}s  audio {'ON' if audio else 'OFF'}  seed {SEED}")
    if words:
        print(f"{words} words: at ~190 wpm that is about {words / 190 * 60:.0f} s of speech")
    print("\n" + prompt + "\n")
    if not go:
        print("Dry run. Nothing spent. Add --go once the operator has said yes.")
        return
    tok = token()
    run({"image": upload(sheet, tok), "prompt": prompt, "duration": secs, "aspect_ratio": "9:16",
         "resolution": "720p", "generate_audio": audio, "watermark": False, "seed": SEED}, out, tok)


if __name__ == "__main__":
    main(sys.argv[1:])
