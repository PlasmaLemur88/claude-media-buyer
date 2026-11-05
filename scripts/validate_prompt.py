#!/usr/bin/env python3
"""Check a written prompt against the guide BEFORE any credit is spent.

    python3 scripts/validate_prompt.py --kind seedance prompt.txt
    python3 scripts/validate_prompt.py --kind kling  box1.txt box2.txt box3.txt
    python3 scripts/validate_prompt.py --kind seedance --words 41 prompt.txt

Exit code is the number of failures, so it drops into a shell loop.

WHY THIS EXISTS
The director instruction has roughly thirty rules. A human or a model reading
prose forgets some of them every time. About a dozen are mechanically decidable,
and those should never rely on memory. This checks those dozen. The rest still
need a person, and the script says so rather than implying a pass means correct.

WHAT IT CANNOT CHECK
Whether the shot plan is any good, whether the acting will be believable,
whether a B-roll visual matches the words being spoken, whether the dialogue is
worth saying. Those are judgment. A clean run here means "no mechanical rule is
broken", never "this prompt is good".
"""
import argparse
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMERA = json.load(open(ROOT / "lib" / "camera.json"))
HEADER = json.load(open(ROOT / "lib" / "header.json"))

# Every camera string the library allows, expanded into the forms a CORRECT
# prompt actually contains. Three expansions, each of which was a real bug:
#
#   1. Slash pairs. The library stores "Camera Pans Down / Up" but director.md
#      says to use only the direction the shot needs. "Camera Pans Down" alone
#      is correct and must match.
#   2. Blocking placeholders. The library stores "[Subject X]" literally, but a
#      correct prompt fills the names in. The filled form must match and the
#      raw placeholder must NOT count as a real camera string.
#   3. Case. Library strings are used verbatim, but a leading capital at the
#      start of a sentence is not a paraphrase.
# Each library entry becomes (name, matcher). A matcher is a literal string or,
# for templated blocking strings, a compiled regex with the [placeholders]
# turned into name slots. Comparisons key on the NAME, so two filled
# "Over the Shoulder" lines with different character names compare equal.
#
# The previous version stripped the placeholders instead of filling them, which
# produced "Over the shoulder shot of character , back is visible, in front of
# them is" - a string no compliant prompt can ever contain. A correctly filled
# over-the-shoulder box then failed with "no camera string from lib/camera.json".
LIB = set()          # literal strings, for the continuity mask
LIB_RE = []          # (name, compiled regex) for templated strings
ENTRIES = []         # (name, group, matcher) for everything


def _expand_slash(s):
    """'Camera Pans Down / Up' -> both single-direction forms, plus the pair."""
    if " / " not in s:
        return [s]
    head, tail = s.rsplit(" / ", 1)
    words = head.split()
    if not words:
        return [s]
    alt = " ".join(words[:-1] + [tail])
    return [s, head, alt]


def _compile(raw):
    """A templated string becomes a regex; a plain one stays a string."""
    pat = re.escape(raw)
    pat = re.sub(r"\\\[[^\]]*?\\\]", r"[^,.\n]{1,60}", pat)
    return re.compile(pat, re.I)


for group in ("shot_size", "angle", "character_view", "blocking",
              "composition", "movement"):
    for e in CAMERA[group]:
        raw = e["string"].strip()
        if "[" in raw and "]" in raw:
            rx = _compile(raw)
            LIB_RE.append((e["name"], rx))
            ENTRIES.append((e["name"], group, rx))
        else:
            for v in _expand_slash(raw):
                LIB.add(v)
                ENTRIES.append((e["name"], group, v))

# Framing categories. These are what "every shot needs a camera string" means,
# and what the no-repeat rule compares. Composition and movement are modifiers.
FRAMING = {"shot_size", "angle", "character_view", "blocking"}


def framing_names(line):
    """Names of the framing entries this line uses, longest match first."""
    hits = []
    for name, group, m in ENTRIES:
        if group not in FRAMING:
            continue
        if isinstance(m, str):
            if m.lower() in line.lower():
                hits.append((len(m), name))
        elif m.search(line):
            hits.append((80, name))
    hits.sort(reverse=True)
    seen, out = set(), []
    for _, n in hits:
        if n not in seen:
            seen.add(n); out.append(n)
    return out


# Words that imply a previous clip. Seedance has zero memory, so any of these
# makes the prompt depend on something the model cannot know.
CONTINUITY = ["earlier", "before", "previous", "previously", "again", "return",
              "returning", "as before", "last time", "unlike before",
              "continuing from", "as seen", "as established", "back to"]

# Symbols and shorthand that must be spelled out inside spoken dialogue.
SYMBOLS = {
    "$": "dollars", "%": "percent", "&": "and", "#": "number",
    "+": "plus", "@": "at",
}
SHORTHAND = [
    (r"\b\d+\s*K\b", "'K' must be written as 'thousand'"),
    (r"\b\d+\s*M\b", "'M' must be written as 'million'"),
    (r"\bvs\b", "'vs' must be written as 'versus'"),
    (r"\bapprox\b", "'approx' must be written as 'approximately'"),
]

TIMECODE_OK = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)s\b")
TIMECODE_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")

KLING_BOX_LIMIT = 2000   # conservative; the interface caps each box
ENDING_LINE = "The subject stops talking, silence in the room."


SMART = {"“": '"', "”": '"', "‘": "'", "’": "'",
         "″": '"', "«": '"', "»": '"'}


def normalise(text):
    """Smart quotes and unicode dashes defeated the naive extractors."""
    for a, b in SMART.items():
        text = text.replace(a, b)
    return text.replace("–", "-").replace("—", "-").replace("−", "-")


def dialogue_spans(text):
    """Spoken dialogue. Quotes are normalised first so curly quotes cannot hide it."""
    return re.findall(r'"([^"]*)"', normalise(text))


# A line that looks like a shot but whose timecode does not parse. Previously
# these were silently dropped, which made a malformed timecode invisible to
# every downstream check instead of failing.
SHOTLIKE = re.compile(r"^\s*\d[\d:.–—-]*\s*(s\b|-)", re.I)


def shot_lines(text, fails=None):
    """Timecoded shot lines, as (raw, start, end). Flags shot-like lines that
    do not parse rather than discarding them.

    Only below the SHOTS marker: the header legitimately contains lines that
    start with a year ('1980s newsroom, night'), and calling those malformed
    timecodes sent the operator to corrupt their own header."""
    out = []
    body = normalise(text)
    if re.search(r"^\s*SHOTS\s*$", body, re.M | re.I):
        body = re.split(r"^\s*SHOTS\s*$", body, maxsplit=1, flags=re.M | re.I)[1]
    for line in body.splitlines():
        m = TIMECODE_OK.match(line)
        if m:
            out.append((line, float(m.group(1)), float(m.group(2))))
        elif fails is not None and SHOTLIKE.match(line) and line.strip():
            fails.append(f"shot line has an unparseable timecode - use plain seconds like 1.5-3s: {line.strip()[:70]!r}")
    return out


# Only these four categories satisfy "every shot needs a camera string".
# Composition and movement are modifiers - "side by side" appearing inside an
# action description is prose, not a camera direction.
DIRECTING = set()
for _g in ("shot_size", "angle", "character_view", "blocking"):
    for _e in CAMERA[_g]:
        for _v in _expand_slash(_e["string"].strip()):
            if "[" not in _v:
                DIRECTING.add(_v)


def used_camera_strings(line, directing_only=False):
    return framing_names(line) if directing_only else (
        framing_names(line) + [n for n, rx in LIB_RE if rx.search(line)])




def check_common(text, fails):
    # Dialogue must not carry symbols or shorthand.
    for d in dialogue_spans(text):
        for sym, word in SYMBOLS.items():
            if sym in d:
                fails.append(f"dialogue contains {sym!r} - must be spelled out as {word!r}: {d[:60]!r}")
        for pat, msg in SHORTHAND:
            if re.search(pat, d, re.I):
                fails.append(f"dialogue shorthand - {msg}: {d[:60]!r}")

    # Clock-format timecodes confuse the model.
    if TIMECODE_CLOCK.search(text):
        fails.append("clock-format timecode found (e.g. 00:04:30) - use seconds only, like 1.5-3s")


def check_angle_variation(shots, fails):
    """No cut may land on the same shot size or angle as the one before it."""
    prev = None
    for raw, _s, _e in shots:
        here = framing_names(raw)
        if not here:
            prev = None          # unknown angle breaks the run rather than freezing it
            continue
        cur = here[0]
        if prev is not None and cur == prev:
            fails.append(f"same angle twice in a row ({cur!r}) - every cut must change the angle: {raw.strip()[:70]!r}")
        prev = cur


def check_seedance(text, words, fails, pacing=None):
    # Mandatory header lines, matched as whole lines against the exact wording
    # in lib/camera.json (which is byte-identical to director.md). A substring
    # test let "no music-free gaps" satisfy the music rule.
    lines = [l.strip() for l in normalise(text).splitlines()]
    for required in CAMERA["seedance_always_include"]:
        if required not in lines:
            fails.append(f"missing the mandatory line, exactly: {required!r}")
    if "visual tone:" not in text.lower():
        fails.append("missing the 'Visual tone:' line - required in every Seedance prompt")
    if "camera feel:" not in text.lower():
        fails.append("missing the 'Camera feel:' line")

    # --- header structure -------------------------------------------------
    # The spec mandates an exact order. Nothing checked this before, and the
    # header is where every reference in the prompt gets defined.
    low_lines = [l.lower() for l in lines]

    def find(pred):
        for i, l in enumerate(low_lines):
            if pred(l):
                return i
        return None

    i_subj = find(lambda l: l == "main subjects:")
    i_tone = find(lambda l: l.startswith("visual tone:"))
    i_feel = find(lambda l: l.startswith("camera feel:"))
    i_music = find(lambda l: l == HEADER["templates"]["no_music"].lower())
    i_subs = find(lambda l: l == HEADER["templates"]["no_subtitles"].lower())
    i_shots = find(lambda l: l == "shots")

    if i_subj is None:
        fails.append("header is missing the 'Main Subjects:' line")
    if i_shots is None:
        fails.append("missing the 'SHOTS' line that separates the header from the shot list")

    seq = [("Main Subjects:", i_subj), ("Visual tone:", i_tone), ("Camera feel:", i_feel),
           ("NO MUSIC", i_music), ("No texts or subtitles", i_subs), ("SHOTS", i_shots)]
    present = [(n, i) for n, i in seq if i is not None]
    for (n1, i1), (n2, i2) in zip(present, present[1:]):
        if i1 > i2:
            fails.append(f"header out of order: {n2!r} appears before {n1!r}. "
                         f"The mandated order is Main Subjects, references, Visual tone, "
                         f"Camera feel, NO MUSIC, no subtitles, SHOTS.")

    # Every character reference must use the mandated wording.
    for i, l in enumerate(lines):
        if l.startswith("•") and "@" in l and "100% matched based exactly on @" not in l:
            fails.append(f"character reference does not use the mandated wording "
                         f"'... face and outfit 100% matched based exactly on @': {l[:70]!r}")

    # Physical description in the header defeats the @ reference.
    if i_subj is not None and i_tone is not None:
        block = " ".join(lines[i_subj:i_tone]).lower()
        for w in (r"\bhair\b", r"\bskin tone\b", r"\bblonde\b", r"\bbrunette\b",
                  r"\bbeard\b", r"\beyes are\b", r"\bcomplexion\b"):
            if re.search(w, block):
                fails.append(f"header physically describes a character ({w.strip(chr(92)+'b')!r}) - "
                             f"the @ reference does that work, and text on top of it conflicts")
                break

    # A green screen placeholder without its five crosses is a defect.
    if "green screen" in text.lower():
        need = HEADER["screen_shot_lines"]["green_screen_placeholder"]
        if need.lower() not in normalise(text).lower():
            fails.append("green screen placeholder is missing its mandated wording - "
                         "it needs a white cross in each of the four corners and one in the centre")

    # Zero memory.
    # Mask library strings before the continuity scan, or "Back to Back side
    # profiles" trips the "back to" rule and no compliant option exists.
    low = text.lower()
    for _lib in sorted(LIB, key=len, reverse=True):
        low = low.replace(_lib.lower(), " ")
    for w in CONTINUITY:
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            fails.append(f"continuity word {w!r} - Seedance has zero memory, every prompt must stand alone")

    # @ must be blank. Two distinct violations:
    #   1. @Label with no space - always wrong, the @ is carrying a name.
    #   2. a header definition line whose @ is not the end of the line.
    # An @ followed by a space inside a SHOT line is correct and expected:
    # "Sarah @ picks up the Product bottle @ and holds it toward camera."
    for line in text.splitlines():
        for m in re.finditer(r"@(\S)", line):
            if m.group(1) not in ".,:;\"')]}":
                fails.append(f"@ carries a label ({('@' + m.group(1))!r}) in {line.strip()[:60]!r} - the @ must be blank, the label goes before it")
        if re.search(r"(based exactly on|based on|=)\s*@", line) and not line.rstrip().endswith("@"):
            tail = line.rstrip().split("@")[-1].strip()
            if tail:
                fails.append(f"header definition has text after the @ ({tail[:40]!r}) - nothing follows the @, ever")

    # Scene setting: reference OR text, never both.
    has_scene_ref = "scene setting is based on @" in low
    env_words = ["ceiling", "floor material", "wall color", "wallpaper", "furniture", "lighting fixture"]
    env_hits = [w for w in env_words if w in low]
    if has_scene_ref and env_hits:
        fails.append(f"scene @ reference AND environment description together ({', '.join(env_hits)}) - pick one, the two conflict")

    shots = shot_lines(text, fails)
    if not shots:
        fails.append("no timecoded shot lines found (expected lines like '0-2s - ...')")
        return

    # Shots must be contiguous and the block within 4-15s.
    total = shots[-1][2]
    if total < 4:
        fails.append(f"generation is {total}s - Seedance minimum is 4s for the whole block")
    if total > 15:
        fails.append(f"generation is {total}s - Seedance maximum is 15s")
    for i in range(1, len(shots)):
        if abs(shots[i][1] - shots[i - 1][2]) > 0.001:
            fails.append(f"timecode gap or overlap: {shots[i-1][0].strip()[:40]!r} then {shots[i][0].strip()[:40]!r}")

    # Every shot needs a library camera string.
    for raw, _s, _e in shots:
        if not used_camera_strings(raw, directing_only=True):
            fails.append(f"shot has no camera string from lib/camera.json - never invent camera wording: {raw.strip()[:70]!r}")

    check_angle_variation(shots, fails)

    # Duration must be honest against the dialogue word count - but director.md
    # REQUIRES breathing room on medium and slow pacing, so a flat words/35*15
    # ceiling failed correct medium and slow prompts as "padded".
    # 4s is also the hard floor for a block, so short dialogue can never be
    # penalised below it.
    BREATH = {"fast": 0.0, "medium": 2.0, "slow": 4.0}
    key = (pacing or "fast").strip().lower().split()[0].split("-")[0]
    if key not in BREATH:
        fails.append(f"pacing {pacing!r} is not one of fast/medium/slow - "
                     f"the breathing-room rule cannot be applied, so this prompt "
                     f"was not fully checked")
        key = "fast"
    spoken = " ".join(dialogue_spans(text))
    n = words if words is not None else len(spoken.split())
    if n:
        base = n / 35 * 15
        dialogue_shots = sum(1 for raw, _s, _e in shots if dialogue_spans(raw))
        allowance = BREATH[key] * max(dialogue_shots, 1)
        honest = round(max(base + allowance, 4.0), 1)
        if total > honest + 0.05:
            note = f" (+{allowance}s breathing room for {key} pacing)" if allowance else ""
            fails.append(
                f"padded: {n} words of dialogue supports about {honest}s"
                f"{note} but the block is {total}s. Trim it.")
        if base > 15.0:
            fails.append(
                f"{n} words cannot fit any legal duration: the honest maximum is "
                f"{base:.1f}s (words/35*15) and a Seedance block caps at 15s. "
                f"Split this into two generations at a natural line break.")
        elif key in ("medium", "slow") and dialogue_shots:
            floor = min(base * 0.6, 15.0)
            if total < floor - 0.05:
                fails.append(
                    f"too tight for {key} pacing: {n} words across {dialogue_shots} "
                    f"dialogue shot(s) in only {total}s leaves no breathing room")


def check_kling(paths, fails, mode="omni"):
    boxes = [(p, open(p, encoding="utf-8").read()) for p in paths]
    total_declared = 0.0

    for idx, (p, text) in enumerate(boxes, 1):
        name = os.path.basename(p)

        if len(text) > KLING_BOX_LIMIT:
            fails.append(f"{name}: box is {len(text)} chars, over the interface limit - trim descriptive filler, never the character assignments")

        # The rule is positional: the box ENDS with this exact line. A bare
        # substring test passed a box that mentioned it in the middle.
        body = normalise(text).rstrip()
        if not body.endswith(ENDING_LINE):
            if ENDING_LINE.lower() in body.lower():
                fails.append(f"{name}: the ending line is present but not at the END of the box, or the wording/case differs from {ENDING_LINE!r}")
            else:
                fails.append(f"{name}: missing the ending line {ENDING_LINE!r} - it goes on EVERY shot box, dialogue or not")

        # Kling gets its look from the images. Tone language is a defect.
        if "visual tone:" in text.lower():
            fails.append(f"{name}: contains a 'Visual tone:' line - the tone string is for Seedance and Stage 2 only, never Kling")
        if re.search(r"\b(shot on|film stock|color grade|desaturated|anamorphic|film grain)\b", text, re.I):
            fails.append(f"{name}: contains visual/look description - Kling prompts say what HAPPENS; the uploaded images carry how it looks")

        # Upload-order references do not bind.
        if re.search(r"\b(first|second|third|1st|2nd|3rd)\s+image\b", text, re.I):
            fails.append(f"{name}: refers to image by upload order - Kling does not know order. Name what the image shows.")

        if idx == 1 and "no music" not in text.lower():
            fails.append(f"{name}: Shot Box 1 missing the camera and audio line ('... No music, only SFX and natural ambience.')")

        found = re.findall(r"\((?:about\s*)?(\d+(?:\.\d+)?)\s*s(?:ec|econds?)?\)", text)
        found += re.findall(r"\b(?:duration|about|approx\.?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*"
                            r"s(?:ec|econds?)?\b", text, re.I)
        if found:
            total_declared += float(found[0])
        else:
            fails.append(f"{name}: no shot duration declared, so the 15s cap on this "
                         f"generation cannot be checked. State it, e.g. 'Close Up (about 3s).'")

        check_common(text, fails)

    if total_declared > 15:
        fails.append(f"declared shot durations total {total_declared}s across {len(boxes)} boxes - one Kling generation is capped at 15s. Split it.")

    # Angle handling differs by mode, and getting this wrong punished compliance.
    #
    # OMNI: consecutive boxes are different shots, so the angle must change.
    # GENERAL: a speaker batch is ALL of one speaker's lines off ONE close-up
    #   start frame. Identical angles across boxes is the correct output. The
    #   previous version failed exactly that, and rewarded splitting one clip
    #   per line - the thing director.md flags CRITICAL at 12 credits/second.
    seen = []
    for p, text in boxes:
        here = framing_names(text)
        if not here:
            fails.append(f"{os.path.basename(p)}: no camera string from lib/camera.json")
            seen.append(None)
            continue
        seen.append(here[0])

    if mode == "general":
        real = [s for s in seen if s]
        if len(set(real)) > 1:
            fails.append(
                f"--mode general is a single-speaker batch off ONE start frame, so every box "
                f"should share that angle, but {len(set(real))} different angles appear: "
                f"{sorted(set(real))!r}. Either these are not one batch, or the wrong start frame is implied.")
    else:
        for i in range(1, len(seen)):
            if seen[i] and seen[i] == seen[i - 1]:
                fails.append(f"{os.path.basename(boxes[i][0])}: same angle as the box before it ({seen[i]!r}) - every cut changes the angle")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--kind", choices=["seedance", "kling"], required=True)
    ap.add_argument("--mode", choices=["omni", "general"], default="omni",
                    help="kling only. 'general' is a single-speaker batch off one start frame, "
                         "where identical angles across boxes are correct")
    ap.add_argument("--pacing", choices=["fast", "medium", "slow"], default=None,
                    help="seedance only. medium and slow REQUIRE breathing room per dialogue shot")
    ap.add_argument("--words", type=int, default=None,
                    help="override the dialogue word count used for the duration check")
    a = ap.parse_args(argv[1:])

    # Pacing lives in the session state, so use it unless overridden.
    pacing = a.pacing
    pacing_source = "--pacing" if pacing else None
    if pacing is None:
        cur = ROOT / ".current_project"
        if cur.exists():
            st = ROOT / "projects" / cur.read_text().strip() / "STATE.json"
            if st.exists():
                try:
                    pacing = json.load(open(st)).get("answers", {}).get("pacing")
                    pacing_source = "STATE.json"
                except Exception as exc:
                    print(f"  NOTE  could not read pacing from {st}: {exc}")

    if a.kind == "seedance" and not pacing:
        print("  NOTE  no pacing found (no --pacing and no answered pacing in STATE.json). "
              "Checking as FAST, which is the least forgiving. If this film is medium or "
              "slow paced, pass --pacing or the breathing-room rule is not applied.")
    elif a.kind == "seedance":
        print(f"  pacing: {pacing} (from {pacing_source})")

    fails = []
    if a.kind == "kling":
        check_kling(a.paths, fails, mode=a.mode)
    else:
        for p in a.paths:
            text = open(p, encoding="utf-8").read()
            check_common(text, fails)
            check_seedance(text, a.words, fails, pacing=pacing)

    for f in fails:
        print(f"  FAIL  {f}")
    if not fails:
        print("  PASS  no mechanical rule broken.")
    print(f"\n{len(fails)} mechanical failure(s).")
    print("Still needs a human: is the plan good, is the acting believable, "
          "does the B-roll match the words, is the dialogue worth saying.")
    return len(fails)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
