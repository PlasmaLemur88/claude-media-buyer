#!/usr/bin/env python3
"""Build a demonstration ad from placeholder parts only, spending nothing, and run every free tool on the way.

  python3 toolbox/sample/make_sample.py [--out toolbox/sample/out] [--skip-demucs]

Everything is made here: a macOS `say` voice, Whisper word timings, PIL stills, an ffmpeg gradient clip, a
silhouette standing in for the presenter cutout (no real person), local HTML pages for the page capture, the
recorded interaction and the redacted document sweep. It is a demo of the tools, not a template for an ad."""
import argparse, json, math, pathlib, shutil, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent; TB = HERE.parent; PY = sys.executable
SCRIPT = ("This is a sample ad, built from placeholder parts. "
          "The first card is a page, captured from a local file. "
          "Here is a number screen, and it counts up. "
          "It is a sample number, not a fact. "
          "Next, a recorded typing demo, one keystroke at a time. "
          "Then a document sweep, with two lines redacted. "
          "And last, a closing card, with typing over a clip.")


def sh(*c, **k):
    print("$", " ".join(str(x) for x in c)[:220]); return subprocess.run([str(x) for x in c], check=True, **k)


def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode())


def still(path, top, bottom, shapes, seed):
    W, H = 1080, 1920; im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y/H; d.line([(0, y), (W, y)], fill=tuple(int(top[i]*(1 - k) + bottom[i]*k) for i in range(3)))
    rng = np.random.default_rng(seed)
    for _ in range(shapes):
        x, y, r = rng.integers(0, W), rng.integers(int(H*0.45), H), rng.integers(80, 260)
        d.rectangle([x - r, y - r//2, x + r, y + r//2], fill=tuple(int(v) for v in rng.integers(60, 200, 3)))
    im.filter(ImageFilter.GaussianBlur(2)).save(path)


def presenter(out, voice_wav, vdur, fps=30, S=720, phone_at=None):
    """a flat silhouette whose 'mouth' opens with the voice level: a stand-in for a real cutout, never a person"""
    with wave.open(str(voice_wav)) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)/32768; sr = w.getframerate()
    n = int(vdur*fps); hop = sr//fps; rms = [float(np.sqrt(np.mean(a[i*hop:(i+1)*hop]**2))) if i*hop < len(a) else 0 for i in range(n)]
    mx = max(rms) or 1
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{S}x{S}", "-r", str(fps), "-i", "-",
                          "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32", "-deadline", "realtime", "-cpu-used", "8", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); sway = 10*math.sin(i/fps*1.3)
        d.ellipse([S*0.12 + sway, S*0.62, S*0.88 + sway, S*1.25], fill=(70, 82, 104, 255))          # shoulders
        d.ellipse([S*0.33 + sway, S*0.18, S*0.67 + sway, S*0.62], fill=(214, 190, 170, 255))        # head
        m = rms[i]/mx; d.ellipse([S*0.45 + sway, S*0.47 - 14*m, S*0.55 + sway, S*0.50 + 14*m], fill=(90, 40, 40, 255))
        if phone_at and phone_at[0] <= i/fps < phone_at[1]:                                        # a "phone" the matte grabbed
            d.rectangle([S*0.55, S*0.05, S*0.98, S*0.95], fill=(20, 20, 24, 255))
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()


def bed(out, seconds):
    sr = 48000; t = np.arange(int(sr*seconds))/sr; x = np.zeros_like(t)
    for f, g in ((110, .5), (164.8, .35), (220, .3), (277.2, .2)): x += g*np.sin(2*np.pi*f*t)*(0.6 + 0.4*np.sin(2*np.pi*0.1*t))
    x = (x/np.abs(x).max()*0.5*32767).astype(np.int16)
    with wave.open(str(out), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE/"out")); ap.add_argument("--skip-demucs", action="store_true")
    a = ap.parse_args(); O = pathlib.Path(a.out); O.mkdir(parents=True, exist_ok=True); (O/"stills").mkdir(exist_ok=True); (O/"clips").mkdir(exist_ok=True)
    # 1. voice + words
    if not (O/"voice.wav").exists():
        sh("say", "-v", "Samantha", "-r", "175", "-o", O/"voice.aiff", SCRIPT)
        sh("ffmpeg", "-y", "-v", "error", "-i", O/"voice.aiff", "-ac", "1", "-ar", "48000", O/"voice.wav")
    if not (O/"voice.json").exists():
        sh("whisper", O/"voice.wav", "--model", "base.en", "--language", "en", "--word_timestamps", "True", "--output_format", "json",
           "--output_dir", O, "--fp16", "False", "--verbose", "False", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    vdur = dur(O/"voice.wav"); sh(PY, TB/"compose_shots.py", "segments", O/"voice.json")
    # 2. pictures
    still(O/"stills"/"sky.png", (150, 180, 210), (90, 110, 80), 6, 1)
    still(O/"stills"/"dusk.png", (60, 70, 110), (40, 45, 50), 8, 2)
    still(O/"stills"/"plain.png", (200, 200, 190), (120, 120, 110), 5, 3)
    if not (O/"clips"/"grad.mp4").exists():
        sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "gradients=s=1080x1920:d=8:speed=0.02:c0=0x4a6a8a:c1=0x9ab0a0:c2=0x6a5a4a:nb_colors=3",
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", O/"clips"/"grad.mp4")
    bed(O/"bed.wav", 20)
    presenter(O/"presenter.webm", O/"voice.wav", vdur)
    presenter(O/"presenter_phone_test.webm", O/"voice.wav", min(vdur, 6), phone_at=(2.0, 3.0))
    # 3. captures (local files only)
    steps = [{"shot": "home", "hold": 0.6}, {"click": "#q", "hold": 0.25}, {"type": "Example", "into": "#q", "hold": 0.07},
             {"pick": "Example Park", "hold": 0.3}, {"shot": "card", "hold": 1.4}]
    json.dump(steps, open(O/"steps.json", "w"))
    sh(PY, TB/"record_interaction.py", "shoot", HERE/"form.html", "--steps", O/"steps.json", "--dir", O/"demo", "--mobile", "iPhone 14 Pro",
       "--private", "#q", "--private", "[role=option]", "--wait", "300")
    sh(PY, TB/"record_interaction.py", "build", "--dir", O/"demo", "--blur", "--name", "demo")
    sh(PY, TB/"capture_page.py", HERE/"form.html", "--out", O/"cards"/"search_box.png", "--selector", "#q", "--transparent", "--wait", "300")
    # 4. document: local HTML -> PDF with a real text layer -> redact -> sweep
    if not (O/"document.pdf").exists():
        import asyncio
        from playwright.async_api import async_playwright
        async def pdf():
            async with async_playwright() as p:
                b = await p.chromium.launch(); pg = await b.new_page(); await pg.goto((HERE/"document.html").as_uri()); await pg.pdf(path=str(O/"document.pdf")); await b.close()
        asyncio.run(pdf())
    sh(PY, TB/"redact.py", O/"document.pdf", "--out-dir", O/"red", "--string", "Jordan Placeholder", "--regex", r"555-\d{3}-\d{4}",
       "--replace", "12 Example Road, Sampletown=Your site", "--string", "EX-0000-SAMPLE")
    sh(PY, TB/"doc_sweep.py", "--pages", O/"red", "--words", O/"red"/"words.json", "--highlight", "42% sample score", "--highlight", "1,234 sq ft",
       "--order", "1,2", "--title", "Sample Report.pdf", "--out", O/"sweep")
    # 5. closing clip: typing into the captured element over the gradient clip; shown for 5.5 s after the full-length demo
    sh(PY, TB/"type_overlay.py", "--bg", O/"clips"/"grad.mp4", "--element", O/"cards"/"search_box.png", "--text-box", "0.05,0.15,0.95,0.85",
       "--phrases", "Type a sample place|See a sample result", "--lines", "Placeholder line one|Placeholder line two",
       "--fine", "Sample small print. Nothing here is real.", "--shown", "5.5", "--out", O/"closing")
    # 6. the shot list (the capture and quote-card tools print the JSON to register each card)
    (O/"cards").mkdir(exist_ok=True)
    info = json.loads(subprocess.check_output([PY, TB/"quote_card.py", "--out", O/"cards"/"quote.png", "--outlet", "Sample Outlet", "--date", "1 Jan 2000",
                      "--headline", "A placeholder headline set as a quote card", "--quote", "Words on a quote card are copied exactly from the source."]).decode().strip().splitlines()[-1])
    art = json.loads(subprocess.check_output([PY, TB/"capture_page.py", HERE/"article.html", "--out", O/"cards"/"article_full.png", "--full",
                     "--headline", "#headline", "--source", "Sample News · 1 Jan 2000", "--redact", "Jordan Placeholder", "--redact-regex", r"555-\d{3}-\d{4}",
                     "--wait", "500"]).decode().strip().splitlines()[-1])
    segs = json.load(open(O/"voice.json"))["segments"]; n = len(segs)
    shots = {0: ["s:sky", "s:dusk@parts"], 1: ["c:article", "c:quote@local"], 2: ["n:12,400|SAMPLE NUMBER|placeholder, not a real statistic"], 3: ["s:dusk"],
             4: ["i:demo"], 5: ["i:sweep"], 6: ["END"]}
    shots = {k: v for k, v in shots.items() if k < n}
    if n != 7: print(f"note: Whisper split the script into {n} phrases, not 7; the sample shot list is trimmed to fit")
    sl = {"name": "sample", "voice": "voice.wav", "words": "voice.json", "presenter": "presenter.webm", "bed": "bed.wav", "speed": 1.0,
          "hook": "Sample ad: placeholder parts only", "labels": {"0": "", "4": "Recorded demo", "5": "Redacted document"},
          "name_card": {"cue": "fact", "name": "Sample Presenter", "title": "Placeholder title"},
          "stills": "stills", "clips": "clips", "number_backgrounds": ["plain"],
          "cards": {"article": dict(art, file="cards/article_full.png"), "quote": dict(info, file="cards/quote.png")},
          "inserts": {"demo": {"file": "demo/demo_{fmt}.mp4", "fit": "cut"}, "sweep": {"file": "sweep_{fmt}.mp4", "fit": "rate"}},
          "close": {"file": "closing_{fmt}.mp4", "len": 7.5, "len_after_full": 5.5},
          "shots": {str(k): v for k, v in shots.items()}}
    json.dump(sl, open(O/"sample.shots.json", "w"), indent=1)
    rc = subprocess.run([PY, TB/"compose_shots.py", "render", O/"sample.shots.json", "--qa", "--out-dir", O/"render"]).returncode
    # 7. checks
    for f in sorted((O/"render").glob("sample_*.mp4")): subprocess.run([PY, TB/"safezone.py", f, "--every", "1.0"])
    subprocess.run([PY, TB/"matte_coverage.py", O/"presenter_phone_test.webm", "--no-face"])
    if not a.skip_demucs:
        sh("ffmpeg", "-y", "-v", "error", "-i", O/"voice.wav", "-i", O/"bed.wav", "-filter_complex", "[1:a]volume=0.5[b];[0:a][b]amix=inputs=2:duration=first[a]",
           "-map", "[a]", O/"voice_with_music.wav")
        sh(PY, TB/"vocals.py", "separate", O/"voice_with_music.wav", "--out-dir", O/"sep")
    print("render exit code", rc)
    for f in sorted((O/"render").glob("*.mp4")): print(f, f"{dur(f):.2f}s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
