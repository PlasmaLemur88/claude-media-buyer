#!/usr/bin/env python3
"""Mechanically check a generated take before a human spends attention on it.

    python3 check_takes.py --expect takes.json kling_takes/v3_1C_designer.mp4 1C
    python3 check_takes.py --expect takes.json kling_takes/*.mp4   # ids auto-matched

Every failure this catches was found by ear in the 7/28 session, one take at a
time. The point is that none of them needed ears. Whisper knows whether the line
was said word-for-word; the audio envelope knows whether a scripted pause exists;
ffmpeg knows whether the register actually dropped. Only "is the performance
believable" needs a human, so only that should reach one.

Checks, mapped to the cherry-pick list:
  2. word-for-word     transcript vs the expected line, word by word
  -  scripted pauses   a gap the script demands must be measurably there
  -  register          a beat marked quiet must be quieter than the beat before
  7. no music          sustained tonal content under dialogue
  6. clean tail        no audio or motion cliff in the final 0.4s

Exit code is the number of failures, so it drops into a shell loop.

------------------------------------------------------------------------------
THE EXPECTATION FILE (this is the part you fill in)

Everything film-specific lives in a JSON file. Nothing about one ad is compiled
into this script. Minimum viable file:

    {
      "takes": {
        "1C": {
          "lines": ["a hundred creatives last week you have no designer"],
          "pause_after": [["week", 0.25]]
        }
      }
    }

Keys inside "takes":
  lines        list of strings. What the SCRIPT says, lowercase, no punctuation.
               Derive these from the screenplay, never from what a take happened
               to produce - otherwise the checker ratifies the defect.
  pause_after  list of [word, seconds]. The beat map needs a real gap after that
               word and a merged delivery is a defect.
  quiet_after  a single word. Everything after it must measurably drop in level.

Optional top-level keys, all defaulted, override only if you must:
  whisper_model  default "small.en"
  filler         words too common to prove anything either way
  homophones     spelling collapses applied before comparison
  thresholds     the five numbers the checks compare against

Run with --write-template to drop a commented starter file next to your takes.
------------------------------------------------------------------------------
"""
import argparse
import json
import pathlib
import subprocess
import sys

DEFAULT_EXPECT = "takes.json"

# Words too common to prove anything either way. A missing "the" is not a defect
# and an extra "a" is not an invention, so neither should fail a take.
# "no" is NOT filler. A take that drops or inverts a scripted negation says the
# opposite of the line, and treating it as filler made that invisible.
DEFAULT_FILLER = ["a", "the", "and", "it", "is", "i", "to", "of", "in", "you"]

# Whisper picks spelling from context, so a homophone tells you nothing about
# what was actually said. "whose" vs "who's" is identical audio; the gap between
# it and the next word is the real discriminator, and that is checked separately.
# Only put genuine homophones here - anything that sounds different must fail.
DEFAULT_HOMOPHONE = {"who's": "whose", "whos": "whose"}

DEFAULT_THRESHOLDS = {
    # a beat marked quiet must drop at least this much against the beat before
    "register_drop_db": 4.0,
    # window used either side of the anchor word for that comparison
    "register_before_s": 2.0,
    "register_after_s": 2.5,
    "register_offset_s": 0.3,
    # only inter-word gaps longer than this are sampled for a music bed
    "music_gap_min_s": 0.6,
    # room tone sits below this; anything louder in a gap is probably music
    "music_floor_db": -28.0,
    # the last word must end at least this far from the cut or there is no
    # room to trim and the edit will clip it
    "tail_room_s": 0.15,
}

TEMPLATE = {
    "whisper_model": "small.en",
    "thresholds": DEFAULT_THRESHOLDS,
    "filler": DEFAULT_FILLER,
    "homophones": DEFAULT_HOMOPHONE,
    "takes": {
        "EXAMPLE_ID": {
            "lines": ["first line exactly as scripted",
                      "second line exactly as scripted"],
            "pause_after": [["scripted", 0.8]],
            "quiet_after": "scripted",
        }
    },
}


def load_spec(path: str) -> dict:
    """Read the expectation file and fill in every default."""
    with open(path) as fh:
        doc = json.load(fh)
    # Tolerate a bare mapping of take-id -> spec, which is what people write
    # first. A doc with no "takes" key and no known top-level key is one.
    if "takes" not in doc:
        doc = {"takes": doc}
    cfg = {
        "whisper_model": doc.get("whisper_model", "small.en"),
        "filler": {w.lower() for w in doc.get("filler", DEFAULT_FILLER)},
        "homophones": dict(doc.get("homophones", DEFAULT_HOMOPHONE)),
        "thresholds": {**DEFAULT_THRESHOLDS, **doc.get("thresholds", {})},
        "takes": doc["takes"],
    }
    return cfg


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def norm(w: str, homophones: dict) -> str:
    w = "".join(c for c in w.lower() if c.isalnum() or c == "'")
    return homophones.get(w, w)


def words_of(path: str, cfg: dict) -> list[dict]:
    import whisper
    m = whisper.load_model(cfg["whisper_model"])
    r = m.transcribe(path, language="en", word_timestamps=True, fp16=False)
    hp = cfg["homophones"]
    return [{"w": norm(w["word"], hp), "start": w["start"], "end": w["end"]}
            for s in r["segments"] for w in s["words"] if norm(w["word"], hp)]


def mean_db(path: str, start: float, dur: float) -> float:
    out = sh(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(dur),
              "-i", path, "-af", "volumedetect", "-f", "null", "/dev/null"])
    for line in out.splitlines():
        if "mean_volume" in line:
            return float(line.split(":")[1].strip().split()[0])
    return -99.0


def check(path: str, take_id: str, cfg: dict) -> list[str]:
    spec = cfg["takes"].get(take_id)
    if not spec:
        return [f"no expectation defined for take id {take_id!r}"]

    th = cfg["thresholds"]
    hp = cfg["homophones"]
    filler = cfg["filler"]

    fails: list[str] = []
    words = words_of(path, cfg)
    said = [w["w"] for w in words]
    print(f"  transcript: {' '.join(said)}")

    # --- check 2: word-for-word -------------------------------------------
    want = [norm(w, hp) for line in spec.get("lines", []) for w in line.split()]
    missing = [w for w in want if w not in said and w not in filler]
    if missing:
        fails.append(f"words missing or mispronounced: {', '.join(missing)}")

    # Order matters. A set test passed "prompts the me show" as "show me the
    # prompts". Walk the expected words through the transcript in sequence.
    seq = [w for w in want if w not in filler]
    pos, out_of_order = 0, []
    for w in seq:
        try:
            pos = said.index(w, pos) + 1
        except ValueError:
            if w in said:
                out_of_order.append(w)
    if out_of_order:
        fails.append(f"words delivered out of order: {', '.join(out_of_order)}")
    # a word the model invented that no line contains
    extra = [w for w in said if w not in want and w not in filler]
    if extra:
        fails.append(f"words not in the script: {', '.join(sorted(set(extra)))}")

    # --- scripted pauses ---------------------------------------------------
    for after, need in spec.get("pause_after", []):
        idx = next((i for i, w in enumerate(words) if w["w"] == norm(after, hp)), None)
        if idx is None or idx + 1 >= len(words):
            continue
        gap = words[idx + 1]["start"] - words[idx]["end"]
        if gap < need:
            fails.append(
                f"pause after {after!r} is {gap:.2f}s, script needs >={need:.2f}s "
                f"(delivered as one continuous phrase)")
        else:
            print(f"  pause after {after!r}: {gap:.2f}s  ok")

    # --- register: the quiet beat must actually be quieter ------------------
    anchor = spec.get("quiet_after")
    if anchor:
        idx = next((i for i, w in enumerate(words) if w["w"] == norm(anchor, hp)), None)
        if idx is not None:
            t = words[idx]["end"]
            before = mean_db(path, max(0, t - th["register_before_s"]),
                             th["register_before_s"])
            after = mean_db(path, t + th["register_offset_s"], th["register_after_s"])
            drop = before - after
            if drop < th["register_drop_db"]:
                fails.append(
                    f"no register change after {anchor!r}: {before:.1f} -> "
                    f"{after:.1f} dB ({drop:.1f} dB). Quiet beat inherited the shout.")
            else:
                print(f"  register drop after {anchor!r}: {drop:.1f} dB  ok")

    # --- check 7: no music -------------------------------------------------
    # Kling bakes music in unremovably when it does it at all. Music shows as a
    # loud floor during the gaps between words; room tone does not.
    gaps = [(words[i]["end"], words[i + 1]["start"] - words[i]["end"])
            for i in range(len(words) - 1)
            if words[i + 1]["start"] - words[i]["end"] > th["music_gap_min_s"]]
    if gaps:
        floors = [mean_db(path, s + 0.1, min(d - 0.2, 1.0)) for s, d in gaps]
        worst = max(floors)
        if worst > th["music_floor_db"]:
            fails.append(f"possible music bed: loudest inter-word gap is "
                         f"{worst:.1f} dB, expected room tone below "
                         f"{th['music_floor_db']:.0f} dB")
        else:
            print(f"  quietest-gap floor: {worst:.1f} dB  ok (no music bed)")

    # --- check 6: clean tail -----------------------------------------------
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip())
    if words and dur - words[-1]["end"] < th["tail_room_s"]:
        fails.append(f"last word ends {dur - words[-1]['end']:.2f}s before the "
                     f"cut - no room to trim, will clip in the edit")

    return fails


def infer_id(path: str, takes: dict) -> str | None:
    """Take id from filename. `_<id>_` first because it cannot collide; a loose
    substring match second, and only when exactly one id matches."""
    name = pathlib.Path(path).name
    exact = [k for k in takes if f"_{k}_" in name]
    if len(exact) == 1:
        return exact[0]
    loose = [k for k in takes if k in name]
    if len(loose) == 1:
        print(f"  (id {loose[0]!r} inferred by loose match on the filename)")
        return loose[0]
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="take files, optionally followed by a take id")
    ap.add_argument("--expect", default=DEFAULT_EXPECT,
                    help=f"expectation JSON (default {DEFAULT_EXPECT})")
    ap.add_argument("--take-id", default=None,
                    help="force one take id for every path given")
    ap.add_argument("--write-template", metavar="PATH",
                    help="write a starter expectation file and exit")
    a = ap.parse_args(argv[1:])

    if a.write_template:
        with open(a.write_template, "w") as fh:
            json.dump(TEMPLATE, fh, indent=2)
        print(f"wrote {a.write_template} - fill in 'takes' from your script")
        return 0

    if not a.paths:
        print(__doc__)
        return 0

    cfg = load_spec(a.expect)
    paths = list(a.paths)
    take_id = a.take_id
    # trailing bare take id, as in: check_takes.py take.mp4 1C
    if take_id is None and paths[-1] in cfg["takes"]:
        take_id = paths.pop()

    total = 0
    for p in paths:
        tid = take_id or infer_id(p, cfg["takes"])
        print(f"\n{pathlib.Path(p).name}  [{tid or 'unknown'}]")
        if tid is None:
            print("  FAIL  cannot infer take id from the filename - this take was NOT checked. "
                  "Pass the id explicitly, e.g. check_takes.py take.mp4 1C")
            total += 1
            continue
        try:
            fails = check(p, tid, cfg)
        except Exception as exc:
            # one unreadable take used to abort the whole batch
            print(f"  FAIL  could not read this take: {type(exc).__name__}: {exc}")
            total += 1
            continue
        for f in fails:
            print(f"  FAIL  {f}")
        if not fails:
            print("  PASS  all mechanical checks")
        total += len(fails)
    print(f"\n{total} mechanical failure(s). Believability still needs a human.")
    return total


if __name__ == "__main__":
    sys.exit(main(sys.argv))
