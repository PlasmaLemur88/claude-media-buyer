#!/usr/bin/env python3
"""Check this machine can actually run the engine. Run it first, on any new box.

    python3 scripts/doctor.py

Exit code is the number of problems. Nothing here spends money or touches a key.
"""
import importlib
import os
import pathlib
import platform
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
problems = []


def ok(msg):
    print(f"  ok    {msg}")


def bad(msg, fix):
    print(f"  MISS  {msg}\n        fix: {fix}")
    problems.append(msg)


print(f"engine doctor - {platform.system()} {platform.machine()}, "
      f"python {sys.version.split()[0]}\n")

print("command line tools")
for tool, fix in (("ffmpeg", "brew install ffmpeg   (or your platform's package manager)"),
                  ("ffprobe", "ships with ffmpeg")):
    if shutil.which(tool):
        ok(tool)
    else:
        bad(tool, fix)

print("\npython packages")
for mod, pkg in (("numpy", "numpy"), ("scipy", "scipy"), ("PIL", "Pillow"),
                 ("whisper", "openai-whisper"), ("librosa", "librosa"),
                 ("cv2", "opencv-python-headless"), ("playwright", "playwright")):
    try:
        importlib.import_module(mod)
        ok(mod)
    except ImportError:
        bad(mod, f"pip install {pkg}   (or: pip install -r requirements.txt)")

print("\nfonts")
fonts = {
    "caption": ["/System/Library/Fonts/SFNS.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf"],
}
for role, paths in fonts.items():
    found = next((p for p in paths if os.path.exists(p)), None)
    if found:
        ok(f"{role} font: {found}")
    else:
        bad(f"no {role} font found",
            "set paths.caption_font in your cut config to any .ttf on this machine")

print("\nkeys  (in .env, never in chat; each one unlocks part of the engine)")
KEYS = (
    ("REPLICATE_API_TOKEN", False,  "stills and video on Replicate (GPT Image 2, Nano Banana, Seedance, Wan)",
     "https://replicate.com/account/api-tokens"),
    ("FAL_KEY",             False,  "voices (MiniMax, ElevenLabs v3), sync.so lip-sync, Seedance on fal",
     "https://fal.ai/dashboard/keys"),
    ("GEMINI_API_KEY",      False, "Gemini voices, the gemini-video skill (watch a video), Nano Banana images",
     "https://aistudio.google.com/apikey"),
)
env = ROOT / ".env"
if not env.exists():
    bad(".env missing", "cp .env.example .env  then paste your own keys. Never commit it.")
else:
    txt = env.read_text()
    for key, required, unlocks, where in KEYS:
        line = [l for l in txt.splitlines() if l.startswith(key + "=")]
        if line and line[0].split("=", 1)[1].strip():
            ok(f"{key} set")
        elif required:
            bad(f"{key} empty in .env (needed for {unlocks})", f"make one at {where}, paste it after the = sign")
        else:
            print(f"  skip  {key} empty: {unlocks} will not work until it is set ({where})")
print("  note  Running ads needs none of these. Making new videos needs a video provider: fal,")
print("        Replicate or Higgsfield (prices differ; your choice). This engine's own voice and")
print("        lip-sync scripts call fal; its stills and generated footage call Replicate.")
print("  note  Kling runs through an MCP entry in your Claude config, not a key here.")
print("        Tools only appear in a session started AFTER the entry exists. Restart.")

print("\nmotion graphics (Remotion)")
node = shutil.which("node")
if not node:
    bad("node", "install Node.js 18 or newer from https://nodejs.org (the LTS installer)")
else:
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major = int(v.lstrip("v").split(".")[0] or 0)
    if major >= 18:
        ok(f"node {v}")
    else:
        bad(f"node {v} is too old", "install Node.js 18 or newer from https://nodejs.org")
    if (ROOT / "motion-graphics" / "node_modules" / "remotion").exists():
        ok("motion-graphics packages installed")
    else:
        bad("motion-graphics packages not installed", "cd motion-graphics && npm install   (setup.sh does this)")
    if (ROOT / "motion-graphics" / "public" / "audio" / "bed_phrygian.wav").exists():
        ok("music bed composed")
    else:
        bad("music bed missing", "python3 scripts/bed.py   (setup.sh does this)")

print("\nrepo")
for p, what in (("lib/director.md", "the spec"), ("lib/camera.json", "camera library"),
                ("guide/images", "reference images"), ("guide/sheets", "option sheets")):
    if (ROOT / p).exists():
        ok(f"{what}: {p}")
    else:
        bad(f"{what} missing at {p}", "re-clone; this ships with the repo")

print("\nself-test")
r = subprocess.run(["bash", str(ROOT / "tests" / "regression.sh")],
                   capture_output=True, text=True, cwd=ROOT)
tail = [l for l in r.stdout.splitlines() if "passed" in l]
if r.returncode == 0 and tail:
    ok(tail[-1].strip())
else:
    bad("regression suite did not pass", "run bash tests/regression.sh and read the failures")

print()
if problems:
    print(f"{len(problems)} problem(s). Fix those before making a film.")
else:
    print("Ready. Open this folder in Claude and say what you want to make.")
sys.exit(len(problems))
