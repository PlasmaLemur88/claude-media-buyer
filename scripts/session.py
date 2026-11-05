#!/usr/bin/env python3
"""The stage gate. Refuses to let a session skip a step.

    python3 scripts/session.py init my-first-film
    python3 scripts/session.py status
    python3 scripts/session.py answer tone G
    python3 scripts/session.py gate stage1        # exits non-zero if not allowed
    python3 scripts/session.py approve-plan "operator said yes in chat"
    python3 scripts/session.py add-image base_image projects/my-first-film/gen/base.png
    python3 scripts/session.py validated projects/my-first-film/prompts/seedance-01.txt

WHY THIS EXISTS
CINEMATIC.md and lib/director.md tell a session what order to work in. Prose
cannot enforce order. This can: `gate` exits non-zero with the reason, so a
step that has not happened yet blocks the next one instead of being quietly
skipped.

It also answers "what do I show the operator right now" — `status` names the
contact sheet for the current decision, so the operator sees the options
instead of reading a list of names.

WHAT IT DOES NOT DO
It cannot tell whether an answer was real or invented, or whether an approval
actually came from the operator. It records what it is told. Its value is that
skipping becomes visible and effortful rather than silent and free.
"""
import argparse
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHEETS = "guide/sheets"

# All 634 steps from the guide, indexed by the stage where they apply.
# A step written down in a file nobody opens at the right moment is missing in
# every way that matters, so status reads the relevant ones OUT.
try:
    CHECKLIST = json.load(open(ROOT / "lib" / "checklist.json"))["stages"]
except Exception:
    CHECKLIST = {}


QUESTIONS = [
    ("tone",
     "What cinematic style do you want for this video? Reply with the letter:",
     "A - 60s/70s Italian Drama\n    B - 80s American Drama\n    C - 80s Summer Comedy\n"
     "    D - 80s/90s Hong Kong Cinema\n    E - 90s Wong Kar-Wai Neon HK\n"
     "    F - 90s American Drama\n    G - Modern A24 Indie\n    H - Modern Digital IMAX",
     f"{SHEETS}/visual-tones.jpg",
     "plain text, lettered multiple choice - NEVER buttons, and never leave a tone out"),

    ("camera_feel",
     "How should the camera physically behave throughout the video?",
     '"Handheld - natural, human" / "Static - composed, locked-off" / "Mix - you decide per shot"',
     None, "buttons"),

    ("angle_switching",
     "How much camera angle switching do you want between shots?",
     '"Lots of angle switches - dynamic" / "Minimal - hold angles longer"',
     f"{SHEETS}/angle.jpg", "buttons"),

    ("pacing",
     "How should the video be paced?",
     '"Fast paced - tight, no dead air" / "Medium paced - natural breathing room" / "Slow paced - let it breathe"',
     None, "buttons"),
]

# director.md assumes you arrive holding a finished script and character sheets.
# The guide has two chapters before it. Nothing gated either, so a session could
# reach Stage 2 with no sheets - and Stage 2 uploads character sheets.
PREREQ_IMAGES = ["character_sheet"]

# Stage 2 images that must exist before any Kling or Seedance prompt is written.
REQUIRED_IMAGES = ["base_image", "wide_shot", "location_sheet"]

STAGES = ["setup", "script", "prep", "stage1", "stage2", "stage3", "stage4"]


def print_checklist(stage, full=False):
    """Print every step for this stage with its state. Never a slice.

    The earlier version printed eight per lane. On the script stage that is 8 of
    74, and a session reading it had no way to know the other 66 existed - so it
    worked from the eight it could see and drifted. A worklist you cannot see
    the end of is not a worklist."""
    lanes = CHECKLIST.get(stage)
    if not lanes:
        return
    st = {}
    try:
        st = json.load(open(state_path())).get("steps", {})
    except Exception:
        pass
    for lane, heading in (("model", "YOU MUST DO / VERIFY THESE"),
                          ("operator", "TELL THE OPERATOR TO DO THESE (you cannot do them)")):
        items = lanes.get(lane, [])
        if not items:
            continue
        done = [i for i in items if i["id"] in st]
        print()
        print(f"  {heading}  [{stage}]  {len(done)}/{len(items)} addressed")
        for it in items:
            rec = st.get(it["id"])
            box = "x" if rec and rec.get("state") == "done" else (
                  "-" if rec else " ")
            gate = {"ENFORCED": "*", "ABSENT": "!"}.get(it["cov"], " ")
            note = ""
            if rec and rec.get("state") == "skip":
                note = f"   SKIPPED: {rec.get('why', '')[:60]}"
            print(f"    [{box}]{gate} {it['id']:>7}  {it['step'][:96]}{note}")
    print()
    print("  [x] done   [-] deliberately skipped   [ ] outstanding")
    print("  * a script also blocks this   ! was absent from the repo until the audit")
    print(f"  mark one:  session.py step <id> done")
    print(f"  skip one:  session.py step <id> skip \"why it does not apply\"")


def state_path():
    cur = ROOT / ".current_project"
    if not cur.exists():
        sys.exit("no active project. run: session.py init <name>")
    name = cur.read_text().strip()
    return ROOT / "projects" / name / "STATE.json"


def load():
    p = state_path()
    if not p.exists():
        sys.exit(f"no STATE.json at {p}. run: session.py init <name>")
    return json.load(open(p)), p


def save(st, p):
    """Atomic. The previous version truncated the file before writing, so an
    interrupted save left an empty STATE.json and lost the whole project."""
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w") as fh:
        json.dump(st, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)


def cmd_init(a):
    name = a.name
    if "/" in name or ".." in name or name.startswith("~"):
        sys.exit(f"BLOCKED: {name!r} is not a plain project name")
    d = ROOT / "projects" / name
    if (d / "STATE.json").exists():
        sys.exit(f"BLOCKED: projects/{name}/STATE.json already exists. Overwriting it would "
                 f"destroy the recorded approvals. Use a different name, or delete it "
                 f"deliberately first.")
    for sub in ("gen", "prompts", "takes", "final"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    st = {
        "project": name,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "answers": {},
        "script_approved": None,
        "plan_approved": None,
        "images": {},
        "validated": [],
        "spend_approved": None,
    }
    save(st, d / "STATE.json")
    (ROOT / ".current_project").write_text(name + "\n")
    print(f"created projects/{name}/ and set it active")
    cmd_status(a)


def next_question(st):
    for key, q, opts, sheet, how in QUESTIONS:
        if key not in st["answers"]:
            return key, q, opts, sheet, how
    return None


def current_stage(st):
    if next_question(st):
        return "setup"
    if not st.get("script_approved"):
        return "script"
    if not any(k.startswith("character_sheet") for k in st["images"]):
        return "prep"
    if not st.get("plan_approved"):
        return "stage1"
    if not all(k in st["images"] for k in REQUIRED_IMAGES):
        return "stage2"
    if st.get("picks"):
        return "post"
    v = st.get("validated", [])
    if any("seedance" in x.lower() for x in v):
        return "post" if st.get("picks") else "stage4"
    if any("kling" in x.lower() for x in v):
        return "stage4"
    return "stage3"


def cmd_status(a):
    st, _ = load()
    stage = current_stage(st)
    print(f"project: {st['project']}")
    print(f"stage:   {stage}")
    print()

    print("SETUP QUESTIONS (one per turn, never chained, never simulated)")
    for key, q, opts, sheet, how in QUESTIONS:
        got = st["answers"].get(key)
        print(f"  [{'x' if got else ' '}] {key:16} {got if got else '-- not answered --'}")
    print()

    print("GATES")
    print(f"  [{'x' if st.get('script_approved') else ' '}] script approved by operator"
          f"{'  (' + st['script_approved'] + ')' if st.get('script_approved') else ''}")
    print(f"  [{'x' if any(k.startswith('character_sheet') for k in st['images']) else ' '}] character sheet(s) exist"
          f"  {[v for k,v in st['images'].items() if k.startswith('character_sheet')] or ''}")
    print(f"  [{'x' if st.get('plan_approved') else ' '}] shot plan approved by operator"
          f"{'  (' + st['plan_approved'] + ')' if st.get('plan_approved') else ''}")
    for k in REQUIRED_IMAGES:
        path = st["images"].get(k)
        here = bool(path) and os.path.exists(path)
        mark = "x" if here else ("!" if path else " ")
        note = f"  {path}" if path else ""
        if path and not here:
            note += "   <-- MISSING ON DISK"
        print(f"  [{mark}] stage 2 image: {k}{note}")
    print(f"  validated prompts: {len(st.get('validated', []))}")
    print()

    brief = ROOT / "projects" / st["project"] / "BRIEF.md"
    if brief.exists():
        print(f"  BRIEF: {brief.relative_to(ROOT)}  <-- read this first, it is the film")
        print()

    nxt, nlane = next_step(st, stage)
    if nxt:
        items = stage_steps(stage)
        done = len(items) - sum(1 for it, _l in items if it["id"] not in st.get("steps", {}))
        print("=" * 72)
        print(f"  THE NEXT STEP  ({done + 1} of {len(items)} in stage {stage!r})")
        print()
        print(f"  {nxt['id']}   {nxt['step']}")
        print()
        if nlane == "operator":
            print("  THIS ONE IS THE OPERATOR'S. You cannot do it or close it.")
            print("  Put it to them, wait for a real answer, then:")
            print(f'    session.py step {nxt["id"]} confirmed "<what they said>"')
        else:
            print("  When it is genuinely done, record what you did:")
            print(f'    session.py step {nxt["id"]} done "<evidence>"')
        print(f'  If it does not apply: session.py step {nxt["id"]} skip "<why>"')
        print("=" * 72)
        print()

    nq = next_question(st)
    print("DO THIS NEXT")
    if nq:
        key, q, opts, sheet, how = nq
        print(f"  Ask the operator, as its own turn, then STOP and wait:")
        print(f"    {q}")
        print(f"    {opts}")
        print(f"  ASK AS: {how}")
        if sheet and (ROOT / sheet).exists():
            print(f"  SHOW THEM THIS FIRST: {sheet}")
            print(f"  (send the image - do not just list the option names)")
    elif not st.get("script_approved"):
        print("  Write the SCRIPT first. lib/director.md assumes you already have one.")
        print("  Use lib/script.json: hook with the pain keyword in the first 1-3 words,")
        print("  pain before product, a setup that needs a payoff, curiosity CTA,")
        print("  characters talking to each other and never to camera.")
        print("  Present it, then STOP. Record with: session.py approve-script \"<what they said>\"")
    elif not any(k.startswith("character_sheet") for k in st["images"]):
        print("  Build the CHARACTER SHEETS. Stage 2 uploads them, so they come first.")
        print("  lib/prep.json has Part A portrait, Part B side profile, Part C triptych,")
        print("  which model compiles which tone, and what to reject.")
        print("  Record with: session.py add-image character_sheet <path>")
        print(f"  Show the operator the look per tone: {SHEETS}/character-per-tone.jpg")
    elif not st.get("plan_approved"):
        print("  Write the Stage 1 shot plan. Present it. Then STOP.")
        print("  Record approval with: session.py approve-plan \"<what they said>\"")
        print("  Do not write a single prompt until that is recorded.")
    elif not all(k in st["images"] for k in REQUIRED_IMAGES):
        missing = [k for k in REQUIRED_IMAGES if k not in st["images"]]
        print(f"  Stage 2. Missing: {', '.join(missing)}")
        print("  Give the operator the GPT Image 2 prompts in order: base image,")
        print("  then wide shot from it, then location sheet from the wide shot.")
        print("  Record each with: session.py add-image <role> <path>")
    elif stage == "post":
        print("  POST. The picks are in. Cut, grade, ship:")
        print("    python3 scripts/assemble.py build --config <cut>.json")
        print("  cuts take in/dur/lead/tail/caps; caps are [text, start, end] triples;")
        print("  outputs.ratios is a list of {file, crop, crf}. Both ratios always.")
        print("  Watch the 4:5 separately - a crop can decapitate what the 9:16 got right.")
    else:
        print("  Stage 3/4. Write prompts, then for each one:")
        print("    python3 scripts/watch_take.py --kind <action|dialogue> <take.mp4>")
        print("    python3 scripts/validate_prompt.py --kind <seedance|kling> <file>")
        print("    python3 scripts/session.py validated <file>")
        print(f"  Camera options to show when choosing shots: {SHEETS}/")

    print_checklist(stage)


def cmd_start(a):
    """What the session says first. The operator should not have to know a
    command, a filename, or what stage anything is in."""
    cur = ROOT / ".current_project"
    active = cur.read_text().strip() if cur.exists() else None
    print("SAY THIS TO THE OPERATOR, in your own words, and no longer:")
    print()
    print("  Let's make a film. Tell me the idea - even half an idea is fine.")
    print()
    print("  I'll take it from there: I write the script, build the characters,")
    print("  generate every reference image, write every prompt, run the")
    print("  generations, check the takes, cut it and grade it.")
    print()
    print("  Four things stay yours, and I'll come to you for each one:")
    print("    - approving the script and the shot plan")
    print("    - saying yes before I spend credits")
    print("    - deciding if the acting is believable")
    print("    - deciding if the voice sounds like a person")
    print()
    print("  I can't watch motion or hear audio. You can. That's the whole split.")
    print()
    print("  What are we making?")
    print()
    print("THEN STOP. Wait for a real answer. Do not ask the four setup")
    print("questions yet - the idea comes first, then the questions, one per turn.")
    print()
    if active:
        print(f"(a project is already active: {active} - run status to see where it is)")
    else:
        print("(once they answer, run: session.py init <short-name>)")


STAGE_ORDER = ["setup", "script", "prep", "stage1", "stage2", "stage3", "stage4", "post"]


def require_clear_through(st, stage):
    """Every stage up to and including this one must be fully addressed.

    Guarding only the stage you happen to be in leaves the earlier ones open:
    a session that skipped setup work and then got busy in stage2 never had to
    go back. Checking the whole prefix means a skipped step surfaces at the next
    transition rather than never."""
    for st_name in STAGE_ORDER[:STAGE_ORDER.index(stage) + 1]:
        require_stage_clear(st, st_name)


def require_stage_clear(st, stage):
    """Refuse to leave a stage with its own work unaddressed.

    This belongs on the transition, not on `gate`. Recording an approval
    advances current_stage immediately, so by the time gate runs it is already
    measuring the stage you moved INTO - which is how a session left the script
    stage with 66 of 74 steps never looked at."""
    lanes = CHECKLIST.get(stage, {})
    allids = [i["id"] for lane in ("model", "operator") for i in lanes.get(lane, [])]
    if not allids:
        return
    seen = st.get("steps", {})
    left = [i for i in allids if i not in seen]
    if left:
        sys.exit(
            f"BLOCKED: stage {stage!r} has {len(left)} of {len(allids)} steps unaddressed.\n"
            f"  next few: {', '.join(left[:6])}\n"
            f"  See them all:  session.py status\n"
            f"  Mark each one: session.py step <id> done\n"
            f"  Or skip with a reason: session.py step <id> skip \"does not apply because...\"\n"
            f"Working from the handful you happened to read is how a stage gets half done.")


def _seq(step_id):
    """Sort key from an id like WCA-27 or CP-041, so both lanes interleave in
    the order the guide states them rather than model-first."""
    m = re.match(r"([A-Za-z]+)-?(\d+)", step_id)
    return (m.group(1).lower(), int(m.group(2))) if m else (step_id.lower(), 0)


def stage_steps(stage):
    """Every step in a stage, in guide order, both lanes interleaved."""
    lanes = CHECKLIST.get(stage, {})
    items = [(i, "model") for i in lanes.get("model", [])] + \
            [(i, "operator") for i in lanes.get("operator", [])]
    items.sort(key=lambda t: _seq(t[0]["id"]))
    return items


def next_step(st, stage):
    """The one step that may be worked right now. None when the stage is done."""
    seen = st.get("steps", {})
    for it, lane in stage_steps(stage):
        if it["id"] not in seen:
            return it, lane
    return None, None


def find_step(step_id):
    """Return (stage, lane, item) for a step id."""
    for stage, lanes in CHECKLIST.items():
        for lane in ("model", "operator"):
            for it in lanes[lane]:
                if it["id"] == step_id:
                    return stage, lane, it
    return None, None, None


def cmd_steps(a):
    """Close a contiguous run of your own steps with one piece of evidence.

    868 individual closes is more bookkeeping than film-making, and ceremony
    that heavy gets abandoned or faked - which is worse than none. So: your own
    work closes in runs, one evidence line for the run. The two things that
    cannot batch are the two that matter - anything the operator must answer,
    and anything a script independently checks."""
    st, p = load()
    here = current_stage(st)
    items = stage_steps(here)
    ids = [it["id"] for it, _l in items]
    try:
        i0, i1 = ids.index(a.first), ids.index(a.last)
    except ValueError as exc:
        sys.exit(f"BLOCKED: {exc}. Both ids must be in stage {here!r}. Run: session.py status")
    if i1 < i0:
        i0, i1 = i1, i0
    nxt, _ = next_step(st, here)
    if nxt and ids[i0] != nxt["id"]:
        sys.exit(f"BLOCKED: a run must start at the next step, which is {nxt['id']}.")
    if not (a.evidence or "").strip():
        sys.exit("BLOCKED: a run still needs evidence. What did you actually do across these?")

    blocked = [(it, lane) for it, lane in items[i0:i1 + 1]
               if lane == "operator" or it["cov"] == "ENFORCED"]
    if blocked:
        it, lane = blocked[0]
        why = ("belongs to the operator" if lane == "operator"
               else "is independently checked by a script")
        sys.exit(
            f"BLOCKED: {it['id']} {why}, so it cannot be closed in a run.\n"
            f"  {it['id']}  {it['step'][:100]}\n"
            f"Stop the run before it. Close that one on its own, then continue.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for it, lane in items[i0:i1 + 1]:
        st.setdefault("steps", {})[it["id"]] = {
            "state": "done", "evidence": a.evidence.strip(),
            "lane": lane, "at": now, "batched": True}
    save(st, p)
    print(f"closed {ids[i0]}..{ids[i1]} ({i1 - i0 + 1} steps) with one evidence line.")
    nxt, nl = next_step(st, here)
    if nxt:
        tag = "  <-- OPERATOR" if nl == "operator" else ""
        print(f"next: {nxt['id']}  {nxt['step'][:80]}{tag}")


def cmd_step(a):
    """Mark a checklist step done or deliberately skipped.

    Refuses a step that belongs to a different stage. That refusal is the whole
    point: a session that starts choosing camera angles during the script stage
    has drifted, and the drift should hit a wall rather than a shrug."""
    st, p = load()
    here = current_stage(st)
    owner = None
    for stage, lanes in CHECKLIST.items():
        for lane in ("model", "operator"):
            if any(i["id"] == a.id for i in lanes[lane]):
                owner = stage
                break
        if owner:
            break
    if owner is None:
        sys.exit(f"BLOCKED: no step {a.id!r} exists. Run: session.py status")
    if owner != here:
        sys.exit(f"BLOCKED: {a.id} belongs to stage {owner!r}. You are in {here!r}.\n"
                 f"Finish this stage before doing that work. Moving a later stage's "
                 f"job into this one is exactly the drift the gates exist to stop.")
    _stage, lane, _it = find_step(a.id)
    # Strictly sequential. A prerequisite that is merely "outstanding" is a
    # prerequisite nobody did - surfacing it at the next stage transition is too
    # late, because the work that depended on it is already written.
    if _stage == here:
        nxt, _nl = next_step(st, here)
        if nxt and nxt["id"] != a.id:
            sys.exit(
                f"BLOCKED: {a.id} is not the next step. {nxt['id']} is.\n\n"
                f"  {nxt['id']}  {nxt['step']}\n\n"
                f"Do that one first. If it does not apply to this film, say so:\n"
                f'  session.py step {nxt["id"]} skip "why it does not apply"')

    # A checkbox a model can tick unaided is not proof of anything. Every close
    # carries evidence, and a step that belongs to the operator can only be
    # closed by quoting what the operator actually said.
    if a.state == "skip" and not (a.why or "").strip():
        sys.exit("BLOCKED: a skip needs a reason. Say why it does not apply to this film.")
    if a.state == "done":
        if lane == "operator":
            sys.exit(
                f"BLOCKED: {a.id} is an OPERATOR step. You cannot mark it done yourself.\n"
                f"  Put it to them, wait for a real answer, then record their words:\n"
                f'    session.py step {a.id} confirmed "<what they actually said>"')
        if not (a.why or "").strip():
            sys.exit(
                f"BLOCKED: {a.id} needs evidence, not a tick. Say what you actually did:\n"
                f'    session.py step {a.id} done "ran validate_prompt.py on seedance-01, 0 failures"\n'
                f"  A checkbox with nothing behind it proves nothing.")
    if a.state == "confirmed":
        if lane != "operator":
            sys.exit(f"BLOCKED: {a.id} is yours to do, not theirs. Use: step {a.id} done \"<evidence>\"")
        if not (a.why or "").strip():
            sys.exit(f"BLOCKED: quote what the operator said. Never record consent they did not give.")

    st.setdefault("steps", {})[a.id] = {
        "state": a.state,
        "evidence": (a.why or "").strip(),
        "lane": lane,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save(st, p)
    lanes = CHECKLIST[here]
    total = len(lanes["model"]) + len(lanes["operator"])
    done = len(st["steps"])
    print(f"{a.id} -> {a.state}. {done}/{total} addressed for stage {here!r}.")
    if done < total:
        out = [i["id"] for lane in ("model", "operator") for i in lanes[lane]
               if i["id"] not in st["steps"]][:6]
        print(f"still outstanding: {', '.join(out)}" + (" ..." if done + 6 < total else ""))


def cmd_checklist(a):
    stage = a.stage
    if stage not in CHECKLIST:
        sys.exit(f"unknown stage {stage!r}. one of: {', '.join(CHECKLIST)}")
    lanes = CHECKLIST[stage]
    print(f"STAGE {stage}: {len(lanes['model'])} for you, {len(lanes['operator'])} for the operator")
    print_checklist(stage, full=True)


def cmd_answer(a):
    st, p = load()
    valid = {q[0] for q in QUESTIONS}
    if a.key not in valid:
        sys.exit(f"unknown question {a.key!r}. one of: {', '.join(sorted(valid))}")
    order = [q[0] for q in QUESTIONS]
    idx = order.index(a.key)
    for earlier in order[:idx]:
        if earlier not in st["answers"]:
            sys.exit(f"BLOCKED: {earlier!r} must be asked before {a.key!r}. "
                     "The questions have a required order and each is its own turn.")
    ALLOWED = {"tone": list("ABCDEFGH"),
               "camera_feel": ["handheld", "static", "mix"],
               "angle_switching": ["lots", "minimal"],
               "pacing": ["fast", "medium", "slow"]}
    tok = a.value.strip().split()[0].split("-")[0].upper() if a.key == "tone" \
        else a.value.strip().lower().split()[0].split("-")[0]
    if tok not in ALLOWED[a.key]:
        sys.exit(f"BLOCKED: {a.value!r} is not one of {ALLOWED[a.key]} for {a.key!r}. "
                 f"Record what the operator actually chose, normalised.")
    if not a.value.strip():
        sys.exit("BLOCKED: empty answer")
    if len(st["answers"]) + 1 == len(QUESTIONS):
        require_clear_through(st, "setup")
    st["answers"][a.key] = tok
    save(st, p)
    print(f"recorded {a.key} = {a.value}")
    cmd_status(a)


def cmd_approve_script(a):
    st, p = load()
    if not (a.note or "").strip():
        sys.exit("BLOCKED: record what the operator actually said. An empty note is "
                 "an approval that did not happen.")
    if next_question(st):
        sys.exit("BLOCKED: setup questions are not all answered. Finish those first.")
    require_clear_through(st, "script")
    st["script_approved"] = a.note
    save(st, p)
    print("script marked approved")


def cmd_approve_plan(a):
    st, p = load()
    if not (a.note or "").strip():
        sys.exit("BLOCKED: record what the operator actually said. An empty note is "
                 "an approval that did not happen.")
    if next_question(st):
        sys.exit("BLOCKED: setup questions are not all answered. Finish those first.")
    if not st.get("script_approved"):
        sys.exit("BLOCKED: there is no approved script. The shot plan is built FROM the script.")
    if not any(k.startswith("character_sheet") for k in st["images"]):
        sys.exit("BLOCKED: no character sheet recorded. Stage 2 uploads character sheets, "
                 "and the realism of the sheet sets the ceiling for every clip.")
    require_clear_through(st, "stage1")
    st["plan_approved"] = a.note
    save(st, p)
    print("shot plan marked approved")


def cmd_add_image(a):
    st, p = load()
    if not os.path.exists(a.path):
        sys.exit(f"BLOCKED: {a.path} does not exist. Do not record an image that was never generated.")
    order = REQUIRED_IMAGES
    if a.role in order:
        idx = order.index(a.role)
        for earlier in order[:idx]:
            if earlier not in st["images"]:
                sys.exit(f"BLOCKED: {earlier!r} must exist before {a.role!r}. "
                         "Each Stage 2 image is generated FROM the previous one.")
    if a.role.startswith("character_sheet"):
        require_clear_through(st, "prep")
    # the LAST required image is what leaves stage 2
    if a.role in REQUIRED_IMAGES:
        after = {k for k in st["images"] if k in REQUIRED_IMAGES} | {a.role}
        if after >= set(REQUIRED_IMAGES):
            require_clear_through(st, "stage2")
    if a.role in REQUIRED_IMAGES and not st.get("plan_approved"):
        sys.exit("BLOCKED: the shot plan is not approved, so nothing says which angles "
                 "to build. Approve the plan first.")
    # store an absolute path: the caller-relative one broke when a later command
    # ran from a different directory
    st["images"][a.role] = os.path.abspath(a.path)
    save(st, p)
    print(f"recorded {a.role} -> {a.path}")


def cmd_pick(a):
    """Record a take the operator picked. This is what advances into post."""
    st, p = load()
    if not os.path.exists(a.path):
        sys.exit(f"BLOCKED: {a.path} does not exist")
    require_clear_through(st, "stage4")
    st.setdefault("picks", [])
    if a.path not in st["picks"]:
        st["picks"].append(a.path)
    save(st, p)
    print(f"recorded pick: {a.path}")
    print("run status - the session is now in post")


def cmd_validated(a):
    """Record a prompt that passed the checker, and auto-close the steps that
    checker independently enforces.

    A step a script verifies does not need a second attestation from the model.
    The passing run IS the evidence, and asking for a typed confirmation on top
    of it is ceremony that adds nothing."""
    st, p = load()
    low = a.path.lower()
    if "kling" in low:
        require_clear_through(st, "stage3")
    if "seedance" in low:
        require_clear_through(st, "stage4")
    st.setdefault("validated", [])
    if a.path not in st["validated"]:
        st["validated"].append(a.path)

    here = current_stage(st)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    auto = 0
    for it, lane in stage_steps(here):
        if lane == "model" and it["cov"] == "ENFORCED" and it["id"] not in st.get("steps", {}):
            st.setdefault("steps", {})[it["id"]] = {
                "state": "done",
                "evidence": f"enforced by validate_prompt.py, which passed on {os.path.basename(a.path)}",
                "lane": lane, "at": now, "auto": True}
            auto += 1
    if auto:
        print(f"auto-closed {auto} script-enforced step(s) - the passing check is the evidence")
    save(st, p)
    print(f"recorded validated prompt: {a.path}")


def cmd_report(a):
    """The audit trail. Every step, who closed it, and on what evidence.

    This is what you show someone who asks whether the playbook was actually
    followed. A stage that is 'clear' with no evidence behind it is a claim;
    this is the record."""
    st, _ = load()
    steps = st.get("steps", {})
    out = [f"# {st['project']} - playbook audit",
           f"", f"Started {st.get('created', '?')}. Written {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
           f"", f"Tone {st['answers'].get('tone', '?')} | camera {st['answers'].get('camera_feel', '?')} "
           f"| switching {st['answers'].get('angle_switching', '?')} | pacing {st['answers'].get('pacing', '?')}",
           f"", f"Script approved: {st.get('script_approved') or 'NO'}",
           f"Plan approved:   {st.get('plan_approved') or 'NO'}", ""]
    grand = [0, 0, 0, 0]
    for stage in STAGE_ORDER:
        lanes = CHECKLIST.get(stage)
        if not lanes:
            continue
        items = lanes["model"] + lanes["operator"]
        if not items:
            continue
        d = sum(1 for i in items if steps.get(i["id"], {}).get("state") == "done")
        c = sum(1 for i in items if steps.get(i["id"], {}).get("state") == "confirmed")
        k = sum(1 for i in items if steps.get(i["id"], {}).get("state") == "skip")
        o = len(items) - d - c - k
        grand = [grand[0] + d, grand[1] + c, grand[2] + k, grand[3] + o]
        out.append(f"## {stage} - {d} done, {c} confirmed by operator, {k} skipped, {o} outstanding")
        out.append("")
        for it in items:
            r = steps.get(it["id"])
            if not r:
                out.append(f"- [ ] **{it['id']}** {it['step'][:110]}")
                continue
            mark = {"done": "x", "confirmed": "OPERATOR", "skip": "-"}[r["state"]]
            out.append(f"- [{mark}] **{it['id']}** {it['step'][:110]}")
            out.append(f"      _{r['state']}: {r.get('evidence', '')}_")
        out.append("")
    out.insert(6, f"**{grand[0]} done, {grand[1]} confirmed by the operator, "
                  f"{grand[2]} skipped, {grand[3]} outstanding.**")
    text = "\n".join(out)
    dest = ROOT / "projects" / st["project"] / "AUDIT.md"
    dest.write_text(text)
    print(f"wrote {dest}")
    print()
    print(f"  {grand[0]} done   {grand[1]} confirmed by the operator   "
          f"{grand[2]} skipped   {grand[3]} outstanding")
    if grand[3]:
        print("  This film has not been through the whole playbook yet.")
    else:
        print("  Every step in the playbook is accounted for.")


def cmd_gate(a):
    st, _ = load()
    want = a.stage
    if want not in STAGES:
        sys.exit(f"unknown stage {want!r}")

    problems = []
    nq = next_question(st)
    if want in ("stage1", "stage2", "stage3", "stage4") and nq:
        unanswered = [k for k, *_ in QUESTIONS if k not in st["answers"]]
        problems.append(f"setup questions not answered: {', '.join(unanswered)}")
    if want in ("script", "prep", "stage1", "stage2", "stage3", "stage4") and not st.get("script_approved"):
        if want != "script":
            problems.append("no approved script - director.md assumes you already have one")
    if want in ("stage1", "stage2", "stage3", "stage4") and not any(
            k.startswith("character_sheet") for k in st["images"]):
        problems.append("no character sheet recorded - Stage 2 uploads them")
    if want in ("stage2", "stage3", "stage4") and not st.get("plan_approved"):
        problems.append("shot plan has not been approved by the operator")
    if want in ("stage3", "stage4"):
        missing = [k for k in REQUIRED_IMAGES if k not in st["images"]]
        if missing:
            problems.append(f"stage 2 images missing: {', '.join(missing)}")
        # re-stat every recorded path. Recording is not the same as still having
        # the file, and a clone has STATE.json without gen/.
        gone = [f"{k} -> {v}" for k, v in st["images"].items() if not os.path.exists(v)]
        if gone:
            problems.append("recorded image(s) no longer on disk: " + "; ".join(gone))
        gone_p = [x for x in st.get("picks", []) if not os.path.exists(x)]
        if gone_p:
            problems.append("recorded pick(s) no longer on disk: " + "; ".join(gone_p))

    # Do not leave a stage with its own work unaddressed. Every step must be
    # either done or deliberately skipped with a reason.
    here = current_stage(st)
    order = ["setup", "script", "prep", "stage1", "stage2", "stage3", "stage4", "post"]
    if want in order and here in order and order.index(want) > order.index(here):
        lanes = CHECKLIST.get(here, {})
        allids = [i["id"] for lane in ("model", "operator") for i in lanes.get(lane, [])]
        seen = st.get("steps", {})
        left = [i for i in allids if i not in seen]
        if left:
            problems.append(
                f"stage {here!r} still has {len(left)} of {len(allids)} steps unaddressed "
                f"(e.g. {', '.join(left[:5])}). Mark each done or skip it with a reason: "
                f"session.py step <id> done")

    if problems:
        print(f"BLOCKED: cannot enter {want}")
        for pr in problems:
            print(f"  - {pr}")
        print("\nRun: python3 scripts/session.py status")
        return 1
    print(f"OK: {want} may proceed")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("name"); s.set_defaults(f=cmd_init)
    s = sub.add_parser("start"); s.set_defaults(f=cmd_start)
    s = sub.add_parser("status"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("answer"); s.add_argument("key"); s.add_argument("value"); s.set_defaults(f=cmd_answer)
    s = sub.add_parser("approve-script"); s.add_argument("note"); s.set_defaults(f=cmd_approve_script)
    s = sub.add_parser("approve-plan"); s.add_argument("note"); s.set_defaults(f=cmd_approve_plan)
    s = sub.add_parser("add-image"); s.add_argument("role"); s.add_argument("path"); s.set_defaults(f=cmd_add_image)
    s = sub.add_parser("validated"); s.add_argument("path"); s.set_defaults(f=cmd_validated)
    s = sub.add_parser("pick"); s.add_argument("path"); s.set_defaults(f=cmd_pick)
    s = sub.add_parser("steps"); s.add_argument("first"); s.add_argument("last")
    s.add_argument("state", choices=["done"]); s.add_argument("evidence")
    s.set_defaults(f=cmd_steps)
    s = sub.add_parser("step"); s.add_argument("id")
    s.add_argument("state", choices=["done", "confirmed", "skip"])
    s.add_argument("why", nargs="?", default=""); s.set_defaults(f=cmd_step)
    s = sub.add_parser("report"); s.set_defaults(f=cmd_report)
    s = sub.add_parser("gate"); s.add_argument("stage"); s.set_defaults(f=cmd_gate)
    s = sub.add_parser("checklist"); s.add_argument("stage"); s.set_defaults(f=cmd_checklist)

    a = ap.parse_args(argv[1:])
    return a.f(a) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
