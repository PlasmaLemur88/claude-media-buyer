# Acted scenes: the cinematic pipeline

`CLAUDE.md` sends you here when the operator wants an acted scene: people who
talk and move, generated on Kling and Seedance. For motion graphics (kinetic
type, captions over footage, aerials, offer cards) you are in the wrong file;
go back to `CLAUDE.md`.

Setup is handled by `CLAUDE.md` and `scripts/doctor.py`. Start here once the
machine is ready.

---

## YOUR FIRST MESSAGE ON AN ACTED SCENE

Run `python3 scripts/session.py start` and say what it gives you, in your own
words. Do not dump this file at the operator. Do not list the file tree. Do not
explain the stages. Open with the offer and the question, then **stop**.

The operator should never have to know a command, a filename, or which stage
anything is in. You run the tooling. They answer questions and make calls.

After they describe the idea: `session.py init <short-name>`, then
`session.py status` every turn to know the single next thing.

---

## FIRST ACTION AFTER THAT, BEFORE ANY WORK

**Read `lib/director.md` in full.** It is 679 lines. Read all of it.

It is the guide's own instruction, reproduced word for word. It is the spec.
This file does not replace it, summarise it, or stand in for it. It adds this
project's failure log on top and tells you how to check your work.

**Where this file and `lib/director.md` disagree about a generation rule,
`lib/director.md` wins.**

Do not work from memory of the director instruction. Do not work from a summary
of it, including any summary you wrote earlier in the session. Every failure in
this project's history traces to somebody working off a compressed version.

---

## WHO THE FILMS ARE FOR

The active brand lives in `brands/<slug>/`: `brand.json` holds the brand and
the offer in its exact wording, and `BRAND-GUIDE.md` holds what may never be
said or shown (people who must never be generated or cloned, claims the brand
will not make, every number with its source). `RULES.md` holds the craft rules
for both halves.

**Check every script against them before a single frame renders.** Rendering is
cheap. Re-rendering a whole wave because one word was wrong is not.

To serve a different brand, follow "Making ads for a different brand" in
`CLAUDE.md`. Nothing else in the engine is tied to it.

---

## THE RULE THIS PROJECT ADDS

**You cannot see motion.** You read still frames. Stills cannot show physics:
weight, acceleration, whether a body moves like mass or like a puppet.

**Never tell the operator a clip works.** Report only what is mechanically
verifiable: duration, frame count, resolution, transcript, loudness, whether
object state changes between frames. Then hand it over. The verdict is theirs.

When they reject something, ask for specifics. "He floats instead of planting
his feet" is actionable. "It's off" is not.

---

## SECOND ACTION: OPEN THE SESSION GATE

```bash
python3 scripts/session.py status      # existing project
python3 scripts/session.py init <name> # new one
```

**`status` reads out EVERY step for the stage you are in**, with its state,
split into two lanes: what YOU must do, and what you must TELL the operator to do
because it happens in an interface, in Premiere, or is a judgment call you cannot
make for them. `session.py checklist <stage>` prints the full list.

All 692 steps from the guide are in `lib/checklist.json`, indexed by stage. Before
this file, 453 of them existed only as text nobody was shown at the moment they
mattered - which is missing in every way that counts.

**`status` also tells you the single next gated action.** Run it at
the top of every turn where you are unsure what comes next. It is the source of
truth for where the session is, not your memory of the conversation.

It also names the contact sheet for the current decision. **When it says SHOW
THEM THIS FIRST, send the image.** The operator picks a tone or an angle by
looking at eight pictures, not by reading eight names. That is the whole reason
`guide/sheets/` exists.

**Three ways a step closes, and the difference matters.**

- **A checker enforces it** → it auto-closes when that checker passes. The
  passing run is the evidence. Do not attest to it on top.
- **It is your own work** → close a contiguous run with one evidence line:
  `session.py steps CR-13 CR-24 done "built Part A through C, all three checked
  against lib/prep.json reject list"`. A run stops dead at anything the operator
  owns or a script checks.
- **The operator owns it** → one at a time, quoting their words, never batched,
  never closed by you.

That is roughly 161 commands across a whole film rather than 868, and 111 of
them are the operator actually checking something. Closing every step
individually was ceremony heavier than the film-making, and ceremony that heavy
gets faked, which is worse than none.

**One step at a time, in order.** `status` names exactly one step: the next one.
You cannot close any other. A prerequisite that is merely outstanding is a
prerequisite nobody did, and finding that out at the next stage transition is
too late, because the work that depended on it is already written.

**Work the list, do not skim it.** Every step is either done or deliberately
skipped with a reason. You cannot leave a stage until all of them are one or the
other, and you cannot record a step that belongs to a different stage - reaching
into a later stage's work is the drift these gates exist to stop.

```bash
# your own work: evidence, not a tick
python3 scripts/session.py step WCA-27 done "sent guide/sheets/angle.jpg, operator picked low angle + close up"

# the operator's: you cannot close these yourself, quote what they said
python3 scripts/session.py step B05 confirmed "operator: GPT Image 2 is set to High"

# does not apply: say why
python3 scripts/session.py step WCA-33 skip "no product in this film"

# the proof, any time
python3 scripts/session.py report        # writes projects/<name>/AUDIT.md
```

**A tick with nothing behind it is refused.** An operator step cannot be closed
by you at all - it needs their actual words. `report` writes the audit trail:
every step, who closed it, on what evidence, and what is still outstanding.
That is what you show someone who asks whether the playbook was followed.

Record every step as it happens:

```bash
python3 scripts/session.py answer tone G
python3 scripts/session.py approve-plan "<what the operator actually said>"
python3 scripts/session.py add-image base_image projects/<name>/gen/base.png
python3 scripts/session.py validated projects/<name>/prompts/seedance-01.txt
python3 scripts/session.py gate stage3   # exits non-zero if you may not proceed
```

`gate` refuses. It will block on unanswered questions, an unapproved plan, or
missing Stage 2 images, and it names which. **Run `gate` before entering a
stage. If it exits non-zero, do not proceed; fix what it names.**

Never record an answer the operator did not give. The gate cannot tell a real
answer from an invented one; it only makes skipping visible and effortful
instead of silent and free. Inventing an answer defeats the entire mechanism.

---

## VALIDATE BEFORE YOU SPEND

Every prompt you write goes through the checker before it reaches the operator
or a credit is spent.

```bash
python3 scripts/validate_prompt.py --kind seedance prompt.txt
python3 scripts/validate_prompt.py --kind kling --mode omni box1.txt box2.txt
python3 scripts/validate_prompt.py --kind kling --mode general spkA1.txt spkA2.txt
```

**`--mode general` matters.** A Kling General speaker batch is all of one
speaker's lines off ONE close-up start frame, so every box shares that angle.
Under `--mode omni` that same input correctly fails the angle-variation rule.
Pass the right mode or the checker will tell you the opposite of the truth.

Pacing is read from `STATE.json`, because medium and slow *require* breathing
room per dialogue shot and a flat word-count ceiling fails a correct prompt.
Override with `--pacing` only if there is no session state.

It mechanically enforces: exact camera strings from `lib/camera.json`, no
back-to-back angles, seconds-only timecodes, no symbols or shorthand in
dialogue, Seedance zero-memory words, the mandatory NO MUSIC and no-subtitles
lines, blank `@` references, scene reference vs scene text but never both, the
4-15s block bounds, the 15s Kling cap, per-box character limits, no visual or
tone language in Kling prompts, no references by upload order, the ending line
on every Kling box, duration honesty against the dialogue word count, the mandated
Seedance header order and reference wording, and the green-screen placeholder's
five white crosses.

**A clean run means no mechanical rule is broken. It never means the prompt is
good.** Everything the checker cannot see (whether the plan is right, whether
the acting will land, whether the B-roll matches the words) is still yours to
get right and the operator's to judge.

---

## THE STAGE GATES

`lib/director.md` defines four stages. Do not move past a gate without the thing
named here.

| Stage | Gate |
|---|---|
| Setup questions | All four answered, **one per turn**, never simulated |
| 0a: Script | The operator has approved the script. `lib/director.md` assumes you have one. Run `/content-strategist` before drafting and `/content-editor` after, per the operator's own standing rule, but where they disagree with the guide's Writing chapter on structure, the guide wins. |
| 0b: Character sheets | At least one sheet exists. Stage 2 uploads them. |
| 1: Shot plan | The operator has approved the plan in writing |
| 2: Base images | Base image, wide shot, location sheet all exist |
| 3: Kling prompts | Every box passes the validator |
| 4: Seedance prompts | Every prompt passes the validator |

**Stage 2 always runs.** Never ask whether a location already exists. Never
offer to describe it in writing instead. The pipeline builds it visually.

**Never chain setup questions.** Ask one, stop your response completely, wait
for a real answer. Never guess what the operator will pick.

---

## SPEND

**Never spend a credit without asking.** State the cost in credits or dollars
and get an explicit yes. Decide the stop-loss before the first paid call.

- **Kling: 12 credits per second, flat.** Duration is the only lever.
- `enable_audio` defaults to **false**; set `"true"` on every dialogue
  generation. A silent 15s take is 180 credits of nothing.
- `resolution` defaults to **4k**; set `"1080p"`.
- Every argument value is a string, including numbers and booleans.
- **Seedance:** duration 4-15. Driving video must be ≥3s. Use 720p when a
  driving video is attached. Do not attach a character photo when a weapon is in
  the scene; it content-blocks. Describe the person in the prompt instead.
- **Wan:** the input video must carry an audio track. Never slow a clip and
  speed it back up; it drops frames.

---

## THINGS THAT WASTED DAYS HERE

- **Change one variable per round.** Two moving teaches you nothing, and the
  whole stage restarts.
- **Take one shot end to end before batching**: assembly, grade, and a human's
  ears. Report spend at that checkpoint.
- **The status API lies.** Measured: QUEUING for eight minutes on a job that
  finished in 106 seconds; RUNNING for fourteen minutes on a 58-second job.
  Poll on long intervals. **Never switch models or resubmit because a job looks
  stuck.**
- **Download results immediately.** URLs expire 24 hours after finish.
- **Label contact sheets** OPTIONS or CLIP N START, never mixed. A grid of
  alternatives gets read as a sequence and approved as a film you did not
  propose.
- **Step the reference frame by frame before building anything.** Minutes of
  ffmpeg settles what prompt wording never will.
- **Generate five to twenty and select.** One or two rolls is not a verdict on
  whether a tool can do something.
- **No face sheet on a from-behind shot.** The model satisfies both constraints
  by painting the face onto a second person.

---

## AFTER GENERATION: TWO GATES BEFORE THE OPERATOR SEES ANYTHING

```bash
python3 scripts/check_takes.py --expect takes.json take.mp4
python3 scripts/watch_take.py --kind <action|dialogue> take.mp4
```

`check_takes.py` covers the audio: word-for-word delivery, scripted pauses,
register drops, baked-in music, a clean tail.

`watch_take.py` covers what a still frame cannot show: a stall, an unwanted cut
inside one generation, a held pose, soft frames, a morphing tail, and whether an
action shot actually moves. **Pass `--kind action` for anything the plan calls
action.** That check is calibrated on real rejections: both door-burst takes the
operator turned down on physics measured under 0.02 mean frame-to-frame change,
while real reference footage measures 0.027.

Getting a low movement number on an action shot means re-roll before the
operator ever watches it.

Then reject a take if any of these fail; these need eyes, not scripts:

1. Wrong face
2. A prop vanishes or floats
3. Eyes go to the camera
4. Room does not match the stills

After a batch passes, build a room-consistency contact sheet across the passing
takes and confirm the same window, furniture and doorway appear in all of them.

**Post:** contrast down, highlights down, saturation down, temperature toward
neutral, HSL secondary on skin, grain 3-8%. `scripts/grade.py` does this in one
ffmpeg pass and currently sits at ~2.4% of full scale (6/255) grain, just under the floor. Grade in
code, never in prompts.

---

## TWO GATES THAT ARE NEVER YOURS

**Is the performance believable?**
**Does the read sound like a person?**

No metric answers either. Both belong to the operator. Every failure in this
project's history happened when a green check stood in for one of them.

---

## ACTION BEATS: TRANSFER THE PHYSICS, DO NOT PROMPT IT

Physics is what has cost this project more than everything else combined.
`lib/physics.json` has the detail. The short version:

**Eight image-to-video takes were rejected on physics. The one clip the operator
approved on physics was a motion transfer.** So for any beat the shot plan calls
action, in this order:

1. **Motion transfer first, not as a fallback.** Pick a driving clip from
   `motion/`, or cut a new one. The weight, acceleration and ground contact come
   from real footage by construction. Seedance stage 1 regenerates the action in
   your location, Wan `animate-replace` puts your character on that plate.
2. **First-frame-to-last-frame** if no driving clip fits. Lock both endpoints so
   the model interpolates between two real poses instead of inventing a path.
3. **Text-to-video last.** It is what failed eight times.

**When you do write motion language, describe forces and contact, not adjectives.**
A model can render a described contact. It cannot render "violent"; it renders
that as speed with no weight, which is exactly what "he floats" means.

> Weak: *he explodes through the door, violent and aggressive*
> Strong: *his palm strikes the door flat and high; the door swings hard and
> rebounds off the wall; his weight lands on the front foot before his shoulder
> follows through the gap*

One contact per shot. A shove AND a charge AND a swing inside three seconds is
why bodies come out floating.

Then measure it: `watch_take.py --kind action`. Real footage measures above 0.02
mean frame-to-frame change. Both rejected door-burst takes measured below it.

---

## THE TOOLS, AND WHEN EACH ONE RUNS

Six of these were sitting in the repo with nothing telling you when to reach for
them, which is how they stay unused.

| Stage | Command | What it does |
|---|---|---|
| any | `session.py start` | The opening message. Run it first. |
| any | `session.py status` | The next action, plus every guide step for this stage. |
| any | `session.py gate <stage>` | Refuses if you may not proceed. |
| script | `/content-strategist` then `/content-editor` | The operator's standing rule for any ad copy. |
| prep | `rep.py <owner/model> '<json>'` | Any Replicate call: Nano Banana 2, GPT Image 2, Seedream 4, Seedance, Wan. |
| prep | Kling MCP | Character work and dialogue video. Needs a paid Kling plan. |
| stage 3-4 | `validate_prompt.py` | Fails a prompt before a credit is spent. |
| after a take | `check_takes.py` | The audio gate: words, pauses, register, music, tail. |
| after a take | `watch_take.py --kind action` | The motion gate: stalls, held poses, cuts, soft frames, morphing tails. |
| voiceover | `voice.py` → `readcheck.py` → `timings.py` → `prosody.py` | Generate a read in one call, check every word against the script, get word-level timings, catch uptalk before anyone hears it. |
| music | `bed.py` | An originally composed bed. **Never substitute a track someone found**. Three tracks in an earlier wave have no clearance and are an open liability. |
| post | `assemble.py build --config <cut>.json` | Cuts the picked takes to the beat map, J-cuts and L-cuts the audio, lays a room-tone bed, burns captions, adds the card, grades, and writes both ratios. |
| post | `assemble.py grade in.mp4 out.mp4 [--strong]` | The grade alone. `--strong` pulls skin shine on tight faces. |

`assemble.py build` is the whole post chapter in one command. It was written and
never referenced anywhere, so it never got used.

---

## LAYOUT

```
CINEMATIC.md                this file - the wrapper and the failure log
lib/director.md             THE SPEC. 679 lines, verbatim. Read it every session.
lib/tones.json              8 visual tones + which model compiles each sheet
lib/camera.json             every camera string + its sample image
lib/duration.json           word-count-to-duration table + the 3 pacing profiles
lib/header.json             the mandated Seedance header structure and its exact wording
lib/script.json             the script layer - hooks, pain keywords, retention, CTA
lib/prep.json               character sheets Part A/B/C and the product sheet
lib/checklist.json          all 692 guide steps, indexed by stage and by who does them
lib/physics.json            why physics fails, and the transfer-first routing that fixes it
brands/<slug>/brand.json    the active brand, its offer, and its non-negotiable rules
reference/                  films worth stealing structure from. Step them frame by frame first.
motion/                     driving clips for transfer. Build once, reuse on every film.
guide/                      source blueprint, extract, 137 reference images
guide/sheets/               labelled option sheets - SEND THESE when asking
scripts/session.py          the stage gate. status / answer / gate / add-image
tests/regression.sh         10 cases, all previously-real bugs. run after any change
tests/consistency.py        proves every string the engine pastes appears verbatim in the spec
.claude/on-start.sh         fires at session start, prints the mandatory first steps
scripts/validate_prompt.py  run before spending anything
scripts/check_takes.py      audio gate - run before a human looks at a take
scripts/watch_take.py       motion gate - stalls, held poses, cuts, morphing tails
scripts/                    assemble, grade, rep, fal, voice, readcheck, lipsync, matte, widows, bed, timings, prosody
projects/<name>/STATE.json  where this session actually is
```

---

## HONEST LIMITS OF THIS REPO

An audit extracted **588 atomic rules** from `lib/director.md` and tested each
against the code. The result:

- **All 692 steps are read out** by `session.py status` at the stage they apply to.
  None of them depend on you remembering to look something up.
- **127 are also blocked by a script** if you skip or break them.
- **0 are un-breakable.** Every mechanical check has a bypass if you go looking.
- **107 steps are the operator's** and always will be: interface settings, uploads,
  Premiere, and every judgment call. The engine's job there is to say them out
  loud at the right moment, not to do them.

The gate and the validator narrow the failure modes. They do not close them.
Treat a green check as "no obvious rule is broken", never as "this is right".

`guide/` holds the reference prompts, images and camera sheets the acted-scene
pipeline uses.
