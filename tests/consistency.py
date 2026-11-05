#!/usr/bin/env python3
"""Verify this repo's own data against lib/director.md.

    python3 tests/consistency.py

Every string the engine will paste into a model - tone strings, camera strings,
mandatory lines, question wording - must appear VERBATIM in the spec. Drift
between the spec and the data is the defect class that made following the rules
produce a red check, so it gets its own gate rather than a one-time fix.

Exit code is the number of divergences.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = (ROOT / "lib" / "director.md").read_text(encoding="utf-8")


def norm(s):
    """The spec uses typographic dashes and quotes; JSON often carries ASCII."""
    for a, b in {"—": "-", "–": "-", "’": "'", "“": '"',
                 "”": '"', " ": " "}.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


SPEC_N = norm(SPEC)
fails = []


def must_appear(label, s, where="director.md"):
    if norm(s) and norm(s) not in SPEC_N:
        fails.append(f"{label}: not found verbatim in {where}\n        {s[:110]!r}")


print("checking lib/tones.json ...")
tones = json.load(open(ROOT / "lib" / "tones.json"))
for k, v in tones["tones"].items():
    must_appear(f"tone {k} string", v["string"])
    if "default_for" in v:
        fails.append(f"tone {k}: has a default_for key, but the spec bans defaulting to any style")
    img = ROOT / "guide" / "images" / (v.get("example") or "")
    if v.get("example") and not img.exists():
        fails.append(f"tone {k}: example image missing: {v['example']}")

print("checking lib/camera.json ...")
cam = json.load(open(ROOT / "lib" / "camera.json"))
for group in ("shot_size", "angle", "character_view", "blocking",
              "composition", "movement"):
    for e in cam[group]:
        # Templated blocking strings carry [Subject X] verbatim in the spec too.
        must_appear(f"{group}/{e['name']}", e["string"])
        if e.get("image") and not (ROOT / "guide" / "images" / e["image"]).exists():
            fails.append(f"{group}/{e['name']}: image missing: {e['image']}")

for line in cam["seedance_always_include"]:
    must_appear("seedance_always_include", line)
gs = cam["kling_boilerplate"]["global_setup"]
if not isinstance(gs, dict):
    fails.append("kling_boilerplate.global_setup must be keyed by camera feel, not a single string")
else:
    for feel, line in gs.items():
        must_appear(f"kling global_setup/{feel}", line)
must_appear("kling ending line", cam["kling_boilerplate"]["ending"])
for feel in ("handheld", "static"):
    must_appear(f"camera_feel/{feel}", cam["camera_feel"][feel])

print("checking scripts/session.py question wording ...")
sess = (ROOT / "scripts" / "session.py").read_text(encoding="utf-8")
for q in re.findall(r'"((?:How|What)[^"]{15,120}\?[^"]*)"', sess):
    must_appear("session question", q)

print("checking lib/duration.json against the spec table ...")
dur = json.load(open(ROOT / "lib" / "duration.json"))
for sec, row in dur["seconds_to_words"].items():
    pat = rf"{sec} seconds = approximately {row['min_words']} to {row['max_words']} words"
    if pat.lower() not in SPEC_N.lower():
        fails.append(f"duration table row {sec}s = {row['min_words']}-{row['max_words']} words does not match the spec")


print("checking lib/header.json against the mandated structure ...")
hdr = json.load(open(ROOT / "lib" / "header.json"))
for k, tpl in hdr["templates"].items():
    core = tpl.split("[")[0].strip() if tpl.startswith("[") is False else tpl
    must_appear(f"header template/{k}", tpl if "[" not in tpl else core)
must_appear("green screen placeholder", hdr["screen_shot_lines"]["green_screen_placeholder"])
must_appear("screen visible line", "as defined in the header, visible and legible on screen")
must_appear("character line wording", "face and outfit 100% matched based exactly on @")
must_appear("object line wording", "100% matched based exactly on @")
must_appear("screen line wording", "display content 100% matched based exactly on @")
must_appear("scene line wording", "Scene setting is based on @")

print("checking every pasteable example against the banned-word list ...")
BANNED = ["earlier", "before", "previous", "again", "return", "continue",
          "as before", "last time", "unlike before"]
phys = json.load(open(ROOT / "lib" / "physics.json"))
for i, sw in enumerate(phys["prompt_language"]["swap"]):
    for b in BANNED:
        if re.search(rf"\\b{b}\\b", sw["strong"], re.I):
            fails.append(f"physics.json swap[{i}].strong uses the banned word {b!r} - "
                         f"an operator pasting this example would fail the validator")
for i, c in enumerate(phys["prompt_language"]["checklist"]):
    for b in BANNED:
        if re.search(rf"\\b{b}\\b", c, re.I):
            fails.append(f"physics.json checklist[{i}] uses the banned word {b!r}")

print("checking the validator's library expansion ...")
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
spec_ = importlib.util.spec_from_file_location("v", ROOT / "scripts" / "validate_prompt.py")
v = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(v)
for group in ("shot_size", "angle", "character_view", "composition", "movement"):
    for e in cam[group]:
        raw = e["string"].strip()
        if "\n" in raw:
            fails.append(f"{group}/{e['name']}: multi-line string can never match a single prompt line - split it")
            continue
        if raw not in v.LIB:
            fails.append(f"{group}/{e['name']}: library string is not matchable by the validator")
for e in [b for b in cam["blocking"] if "[" in b["string"]]:
    if not any(rx.search(e["string"].replace("[Subject X]", "Sarah")
                         .replace("[Subject 1]", "Sarah").replace("[Subject 2]", "Mike")
                         .replace("[Subject 3]", "Jo")
                         .replace("[Subject 3's Character view]", "Front view")
                         .replace("[Subject 2's Character view]", "Front view"))
               for _n, rx in v.LIB_RE):
        fails.append(f"blocking/{e['name']}: a correctly filled version does not match the compiled pattern")

print()
for f in fails:
    print(f"  DIVERGENCE  {f}")
print(f"\n{len(fails)} divergence(s) between the repo's data and lib/director.md.")
sys.exit(len(fails))
