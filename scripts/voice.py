#!/usr/bin/env python3
"""One voiceover read of a WHOLE script in ONE call, normalised to a 48 kHz mono wav.

Never generate a script line by line: the delivery drifts between calls. Read it once,
then cut it with readcheck.py / timings.py word timestamps if you need per-line clips.

    python3 scripts/voice.py gemini     --text-file script.txt --voice Fenrir --style "brisk, natural, no pauses" --out read.wav
    python3 scripts/voice.py minimax    --text-file script.txt --voice English_Jovialman --speed 1.1 --out read.wav
    python3 scripts/voice.py elevenlabs --text-file script.txt --voice Charlie --speed 1.1 --out read.wav
    python3 scripts/voice.py seed       --text-file script.txt --voice <speaker_id> --out read.wav
    python3 scripts/voice.py seed-clone --ref clean_10-30s.wav                       # prints a speaker_id, ~$2.50 once
    python3 scripts/voice.py seedance   --text-file script.txt --voice "An American man in his thirties, calm" --out read.wav
    python3 scripts/voice.py seedance   --text-file script.txt --ref-audio 25s_of_the_person.wav --ref-image plain.jpg --out read.wav

Engines (all but gemini run on fal and read FAL_KEY; gemini reads GEMINI_API_KEY; env first, then .env at the engine root):
  gemini      gemini-2.5-flash-preview-tts, a prebuilt voice (Fenrir, Charon, Puck, Zephyr...) plus a style prompt.
              Returns 24 kHz PCM. Has no speed control, so --speed is applied locally with atempo.
  minimax     fal-ai/minimax/speech-2.8-hd. --voice is a MiniMax voice_id. --speed is native.
  elevenlabs  fal-ai/elevenlabs/tts/eleven-v3 through fal (a direct ElevenLabs key is not needed). --speed is native.
  seed        bytedance/seed-audio-1.0 with a cloned speaker_id from seed-clone. Reads vary in pace run to run at the
              same speed: draw 3-6 and keep the cleanest (readcheck.py). --speed is native.
  seedance    bytedance/seedance-2.5 text-to-video (or reference-to-video with --ref-audio), used ONLY for its voice:
              the 480p picture is thrown away. Natural-sounding but ~30 s max and priced as video. With --ref-image,
              use a TEXT-FREE image: a take once read the text on a reference page aloud.

Pronunciation: --say-as brands/x/say_as.json is a flat {"Spelling": "SaidAs"} map applied, whole-word, ONLY to the
text sent to the TTS. Captions keep the real spelling. Numbers: spell them out in the script ("twelve thousand")
unless you have checked the engine reads digits right.

Post: optional --speed (see above), --trim (leading/trailing silence), then loudnorm to --loudness LUFS (default -16),
48 kHz mono. --raw keeps the provider's file beside the output. --dry-run prints the text and payload and spends nothing.
"""
import argparse
import base64
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from keys import key  # noqa: E402

GEMINI_MODEL = "gemini-2.5-flash-preview-tts"
EP = {
    "minimax": "fal-ai/minimax/speech-2.8-hd",
    "elevenlabs": "fal-ai/elevenlabs/tts/eleven-v3",
    "seed": "bytedance/seed-audio-1.0",
    "seed-clone": "bytedance/seed-audio-1.0/voice-clone",
    "seedance": "bytedance/seedance-2.5/text-to-video",
    "seedance-ref": "bytedance/seedance-2.5/reference-to-video",
}
NATIVE_SPEED = {"minimax", "elevenlabs", "seed"}


def sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def apply_say_as(text, path):
    if not path:
        return text, []
    table = json.loads(pathlib.Path(path).read_text())
    hits = []
    for spelled, said in table.items():
        new, n = re.subn(rf"\b{re.escape(spelled)}\b", said, text)
        if n:
            hits.append(f"{spelled} -> {said} x{n}")
        text = new
    return text, hits


# ---------------- engines ----------------
def gemini(text, a, raw):
    style = a.style or "Read this at a brisk, natural pace, like a person talking to a friend. Short pauses only at sentence ends."
    body = {"contents": [{"parts": [{"text": f"{style}\n\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": a.voice}}}}}
    if a.dry_run:
        return print(json.dumps({"endpoint": f"generativelanguage.googleapis.com {GEMINI_MODEL}", "payload": body}, indent=1))
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key("GEMINI_API_KEY")})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"gemini HTTP {e.code}: {e.read().decode()[:300]}")
    parts = res.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    aud = [p for p in parts if "inlineData" in p]
    if not aud:
        sys.exit(f"gemini returned no audio: {json.dumps(res)[:300]}")
    mime = aud[0]["inlineData"]["mimeType"]
    rate = next((int(kv.split("=")[1]) for kv in mime.split(";") if kv.strip().startswith("rate=")), 24000)
    pcm = raw.with_suffix(".pcm")
    pcm.write_bytes(base64.b64decode(aud[0]["inlineData"]["data"]))
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", rate, "-ac", "1", "-i", pcm, raw)
    pcm.unlink()


def _fal(endpoint, payload, a):
    if a.dry_run:
        return print(json.dumps({"endpoint": endpoint, "payload": payload}, indent=1))
    import fal
    return fal.run(endpoint, payload, fal.token(), timeout=2400)


def _first_url(out, *keys_):
    for k in keys_:
        v = out.get(k)
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, str) and v.startswith("http"):
            return v
    import fal
    got = fal.urls(out)
    if not got:
        sys.exit(f"no media url in response: {json.dumps(out)[:300]}")
    return got[0]


def minimax(text, a, raw):
    vs = {"voice_id": a.voice, "speed": a.speed}
    if a.emotion:
        vs["emotion"] = a.emotion
    out = _fal(EP["minimax"], {"text": text, "voice_setting": vs, "output_format": "url"}, a)
    if out:
        _save(_first_url(out, "audio", "audio_url", "audio_file"), raw)


def elevenlabs(text, a, raw):
    p = {"text": text, "voice": a.voice, "stability": a.stability, "similarity_boost": 0.8, "speed": a.speed}
    if a.style_strength is not None:
        p["style"] = a.style_strength
    out = _fal(EP["elevenlabs"], p, a)
    if out:
        _save(_first_url(out, "audio", "audio_url"), raw)


def seed(text, a, raw):
    out = _fal(EP["seed"], {"prompt": text, "voice": a.voice, "speed": a.speed, "pitch": 0,
                            "output_format": "wav", "sample_rate": 48000}, a)
    if out:
        _save(_first_url(out, "audio"), raw)


def seedance(text, a, raw):
    words = len(text.split())
    if words > 80:
        print(f"warning: {words} words is a lot for a 30 s Seedance take (~70 is comfortable)", file=sys.stderr)
    tail = ("\" Then the speaker stops talking. NO MUSIC. No background noise, no other voices, "
            "only the voice in a quiet room. No text or subtitles on screen.")
    if a.ref_audio:
        style = a.style or "calm, friendly and natural, at a relaxed conversational pace"
        prompt = ("@Image1 is shown full screen, static, one continuous take with no cuts. An off-screen narrator speaks over it. "
                  "The voice is the exact voice of the person in @Audio1: same timbre, same accent, same delivery. "
                  f"The delivery is {style}. The narrator says: \"" + text + tail)
        import fal
        payload = {"prompt": prompt, "audio_urls": ["<upload>" if a.dry_run else fal.upload(a.ref_audio)],
                   "duration": str(a.duration), "resolution": "480p", "aspect_ratio": "9:16", "generate_audio": True}
        if a.ref_image:
            payload["image_urls"] = ["<upload>" if a.dry_run else fal.upload(a.ref_image)]
        endpoint = EP["seedance-ref"]
    else:
        if not a.voice:
            sys.exit("seedance needs --voice (a description of the speaker) or --ref-audio")
        style = a.style or "Calm, friendly and natural, like a podcast host explaining something useful to a friend, not a salesperson"
        prompt = ("Static camera, locked off, close-up at eye level, vertical frame, one continuous take with no cuts. "
                  f"{a.voice} sits in a quiet, softly lit room and talks to the camera. {style}. "
                  "Every word is articulated clearly, with a short natural pause between sentences. They say: \"" + text + tail)
        payload = {"prompt": prompt, "duration": str(a.duration), "resolution": "480p", "aspect_ratio": "9:16",
                   "generate_audio": True}
        endpoint = EP["seedance"]
    if a.seed is not None:
        payload["seed"] = a.seed
    out = _fal(endpoint, payload, a)
    if out:
        mp4 = a.out.with_suffix(".seedance.mp4")
        _save(_first_url(out, "video"), mp4)
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "48000", raw)
        print(f"seedance video kept at {mp4} (picture is 480p, voice only)")


def seed_clone(a):
    ref = pathlib.Path(a.ref)
    if dur(ref) > 30:
        sys.exit("reference must be 30 s or less: one speaker, no music, same mic as the footage if you will lip-sync")
    if a.dry_run:
        return print(json.dumps({"endpoint": EP["seed-clone"], "payload": {"audio_url": "<upload>", "language": "en"}}))
    import fal
    out = fal.run(EP["seed-clone"], {"audio_url": fal.upload(ref), "language": "en"}, fal.token())
    sid = out.get("speaker_id") or out.get("voice")
    print(json.dumps({"speaker_id": sid}))
    print("clone costs ~$2.50 and stays valid ~12 months: store the speaker_id with the brand, reuse it.", file=sys.stderr)


def _save(url, path):
    import fal
    fal.download(url, path)


ENGINES = {"gemini": gemini, "minimax": minimax, "elevenlabs": elevenlabs, "seed": seed, "seedance": seedance}


def post(raw, out, a):
    chain = []
    if a.speed != 1.0 and a.engine not in NATIVE_SPEED:
        s = a.speed
        while s > 2.0:
            chain.append("atempo=2.0"); s /= 2.0
        chain.append(f"atempo={s:.4f}")
    if a.trim:
        trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
        chain = [trim, "areverse", trim.replace("0.05", "0.08"), "areverse"] + chain
    if a.loudness is not None:
        chain.append(f"loudnorm=I={a.loudness}:TP=-1.5:LRA=11")
    chain.append("aresample=48000")
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", ",".join(chain), "-ac", "1", "-ar", "48000", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("engine", choices=list(ENGINES) + ["seed-clone"])
    ap.add_argument("--text-file", type=pathlib.Path, help="the whole script, one file")
    ap.add_argument("--text", help="inline script instead of --text-file")
    ap.add_argument("--voice", help="gemini voice name, minimax voice_id, elevenlabs voice, seed speaker_id, or seedance speaker description")
    ap.add_argument("--style", help="delivery prompt (gemini, seedance)")
    ap.add_argument("--say-as", help='JSON {"Spelling": "SaidAs"} applied only to the text sent to the TTS')
    ap.add_argument("--speed", type=float, default=1.0, help="native for minimax/elevenlabs/seed, atempo otherwise")
    ap.add_argument("--trim", action="store_true", help="trim leading and trailing silence")
    ap.add_argument("--loudness", type=float, default=-16.0, help="loudnorm target LUFS; pass --no-norm to skip")
    ap.add_argument("--no-norm", dest="loudness", action="store_const", const=None)
    ap.add_argument("--emotion", help="minimax emotion, e.g. happy, neutral")
    ap.add_argument("--stability", type=float, default=0.45, help="elevenlabs stability")
    ap.add_argument("--style-strength", type=float, help="elevenlabs style 0-1")
    ap.add_argument("--ref", help="seed-clone: 10-30 s of clean speech")
    ap.add_argument("--ref-audio", help="seedance: reference clip of the voice to copy (switches to reference-to-video)")
    ap.add_argument("--ref-image", help="seedance: text-free reference image")
    ap.add_argument("--duration", type=int, default=30, help="seedance clip seconds")
    ap.add_argument("--seed", type=int, help="seedance seed")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--raw", action="store_true", help="keep the provider's unprocessed file next to --out")
    ap.add_argument("--dry-run", action="store_true", help="print the text and payload, call nothing, spend nothing")
    a = ap.parse_args()

    if a.engine == "seed-clone":
        if not a.ref:
            ap.error("seed-clone needs --ref")
        return seed_clone(a)
    if a.engine in ("gemini", "minimax", "elevenlabs", "seed") and not a.voice:
        ap.error(f"{a.engine} needs --voice")
    if not (a.text_file or a.text):
        ap.error("give --text-file or --text")
    text = (a.text_file.read_text() if a.text_file else a.text).strip()
    text = re.sub(r"[ \t]+", " ", text)
    text, hits = apply_say_as(text, a.say_as)
    for h in hits:
        print("say-as:", h, file=sys.stderr)
    print(f"{a.engine}: {len(text.split())} words in one call", file=sys.stderr)
    if a.dry_run:
        print("TEXT SENT TO TTS:\n" + text + "\n")
        ENGINES[a.engine](text, a, pathlib.Path("dry.wav"))
        return
    if not a.out:
        ap.error("--out is required")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    keep = a.out.with_name(a.out.stem + "_raw.wav")
    with tempfile.TemporaryDirectory() as td:
        raw = keep if a.raw else pathlib.Path(td) / "raw.wav"
        ENGINES[a.engine](text, a, raw)
        post(raw, a.out, a)
    print(f"{a.out}  {dur(a.out):.2f}s  ({len(text.split()) / dur(a.out) * 60:.0f} wpm incl. silence)")
    print("next: python3 scripts/readcheck.py", a.out, "--script <script.txt>   (catch slips before anyone listens)")


if __name__ == "__main__":
    main()
