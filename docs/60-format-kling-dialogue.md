# 60 · Kling 3.0 dialogue scenes: setup, generation, checking, assembly

> **Read this first.** `RULES.md` section 4 is the current routing rule: **a
> talking generated character is one Seedance text-to-video take per speaker,
> with the era look in the prompt. Kling is for silent B-roll.** Kling's native
> audio ran mouths 250-500 ms off the voice and no lip-sync pass rescued them.
> So do not plan a shipping ad on Kling dialogue.
>
> This file is kept because most of its method is reusable anyway: the MCP
> setup and free upload, the generation parameters and costs, the shot-box
> prompt rules, the cherry-pick checklist, the mechanical take checker
> (`scripts/check_takes.py`) and the J-cut/L-cut assembler (`scripts/assemble.py`).
> Those apply to silent Kling B-roll, to Seedance talking takes, and to any film
> cut from many separate generations. Kling dialogue itself is still fine for an
> animatic or a scratch cut.
>
> Where this file and `lib/director.md` disagree about how to write a
> generation prompt, **`lib/director.md` wins**. `CINEMATIC.md` holds the stage
> gates and the prompt validator. This is the most expensive format with the
> longest failure log: read `docs/70-playbook-and-failures.md` before spending a
> credit, and do not start a new operator on it.

The route: connect the MCP, upload references for free, submit a generation,
check the takes mechanically, cherry-pick by eye and ear, then cut the picks
into one film in two ratios.

---

## (a) MCP setup

### 1. Register the server

The Kling MCP is a remote HTTP server. The entry in your Claude config
(`~/.claude.json`) is exactly this:

```json
{
  "mcpServers": {
    "kling": {
      "type": "http",
      "url": "https://kling.ai/mcp"
    }
  }
}
```

No API key, no token, no env block. Authorization is an in-app OAuth sign-in
against whichever Kling account you log in with. The CLI equivalent is
`claude mcp add --transport http kling https://kling.ai/mcp`; if that form
differs on your version, edit the JSON directly.

### 2. Restart. This step has eaten whole sessions.

**Tools load only in a session started AFTER the entry exists.** A session
already running when you added it will never see the tools, whatever you do
inside it. Warn the operator before the edit, then quit, relaunch and confirm.

### 3. Confirm, in this order

1. `ToolSearch "+kling"` lists the Kling tools. At minimum: `who_am_i`,
   `query_membership_and_credits`, `query_tasks`, `file_upload`,
   `text_to_image`, `image_to_image`, `text_to_video`, `image_to_video`
   (newer server versions add more, such as element and omni-reference tools).
2. **`who_am_i`** first. It returns the signed-in identity and, for every
   generation tool, the available models with their full argument spec:
   required flags, defaults, allowed values. **Defaults vary by membership
   tier**, so this is the authority for section (c), not this document.
3. **`query_membership_and_credits`** as the account guard. Know what balance
   you expect before you look. Two Kling logins can look identical in the UI;
   one team generated on the wrong, unfunded account before noticing the
   balance was a tiny free-tier number. If the number is not the one you
   expect, stop.

The MCP spends the **same subscription credits** as the web app; there is no
separate API meter (measured: a 180-credit job moved the web balance by 180).
The MCP balance can read slightly lower than the web Credit Details page
because it appears to exclude bonus credits. That gap alone does not mean a
wrong account.

### 4. Browser fallback (only if the MCP breaks)

The web app's Custom Multi-Shot UI (Omni, Video Generation, toggle
**Multi-Shot**, then **Custom Multi-shot**) gives per-shot text boxes with
duration steppers, a shared reference tray and a Native Audio toggle. It is the
only route with a real per-shot duration control. Traps when driving it from
Claude's browser tools:

- Create the tab inside the extension's tab group and bring it to the front.
  Tabs outside the group render 0x0 and every screenshot comes back blank,
  which looks like an empty Kling app rather than a tab problem.
- Use `kling.ai/app/...` URLs. `app.klingai.com/global/...` redirects and
  drops the session.
- If more than one Chrome profile is paired to the extension, check which
  Kling account each one is signed into before generating. Switch to the right
  profile rather than signing in again inside the wrong one.

You cannot drag files into the page from Claude. `file_upload` below takes a
local path, so prefer the MCP.

---

## (b) Upload recipe: two steps, free

Uploading costs no credits.

**Step 1: get a ticket.** Call `file_upload`:

| Argument | Type | Notes |
|---|---|---|
| `filename` | string | e.g. `speakerA_closeup.jpg` |
| `contentType` | string | MIME type: `image/jpeg`, `image/png`, `video/mp4` |
| `size` | integer | exact file size in **bytes** |
| `taskTraceId` | string | optional UUID v7 grouping the chained steps of one job |

It returns a single-use `ticket`, an `uploadUrl` and an `expire_at`.

**Step 2: POST the bytes yourself.** The MCP does not move the file. POST to the
`uploadUrl` step 1 returned (it is authoritative; the endpoint below is the one
that has worked):

```bash
TICKET='<ticket from step 1>'
curl -X POST https://kling.ai/api/mcp/files \
  -F "ticket=$TICKET" \
  -F "file=@refs/speakerA_closeup.jpg;type=image/jpeg"
```

The response carries `data.url`. That URL is what you pass in `inputs[].url`.

- **Tickets are single-use and expire in about 10 minutes** (`expire_at`
  rules). Upload right before the generation that uses them, not at the top of a
  session.
- **Reuse a returned URL** for an unchanged file instead of re-uploading. URLs
  from earlier Kling results can be fed straight back in.
- **Input spec:** PNG or JPG, below 4K, at most 30 MB, aspect no wider than 1:2.
- A publicly reachable URL also works in place of an upload.

---

## (c) Generation parameters

### Call shape

`image_to_video` and `text_to_video` share one shape:

| Parameter | Required | Shape |
|---|---|---|
| `model` | **yes, no default** | one of the models `who_am_i` lists for that tool |
| `arguments` | yes | `[{"name": "...", "value": "..."}]`. **Every value is a string**, numbers and booleans included |
| `inputs` | image routes | `[{"name": "image_1", "inputType": "URL", "url": "https://..."}]` |
| `rationale` | yes in practice | plain-English purpose of this job |
| `taskTraceId` | optional | UUID v7 tying chained calls together |

It returns a `generation_id` at once. Poll `query_tasks` with it, and read
failure-log item 9 before you believe anything it says.

### Models (names as the MCP listed them; confirm with `who_am_i`)

| Model | Use for | Why |
|---|---|---|
| `kling-video-v3_0` (General, non-Omni) | single-character shots off one start frame | takes the scene still as `first_image`, rendered in about half the time of Omni (about 6 min vs 13), and never renders a reference sheet into the shot. Max 2 images per generation (`lib/director.md`) |
| `kling-video-v3_0_omni` | multi-reference, multiple angles or characters in one sequence | up to 7 references, 9:16, native audio, multi-shot. Artifact-prone when overloaded with references |
| `kling-image-v3_0_omni` | stills that must hold identity | cheap (a few credits per pair at 2k); the default for reference-consistency work |
| `kling-image-o1` | surgical edits to an existing still | about 2 credits; removed an artifact first try |
| GPT Image 2 (not Kling, via `scripts/rep.py`) | precision instruction following, from-behind framings, editing a reference frame | slower and dearer, best instruction following |

### Arguments

| Argument | Typical value | Default seen | Notes |
|---|---|---|---|
| `prompt` | the shot boxes as one string | none | section (d) |
| `duration` | `"8"` to `"15"` | read from `who_am_i` | integer seconds, 3-15, **15 is the hard ceiling** |
| `aspect_ratio` | `"9:16"` | read from `who_am_i` | |
| `resolution` | `"1080p"` | **`4k`** | 1080p is the finishing resolution |
| `imageCount` | `"1"` | read from `who_am_i` | |
| `prefer_multi_shots` | `"true"` | read from `who_am_i` | Omni only |
| `enable_audio` | `"true"` for anything with speech or sync sound | **`false`** | see below |
| `first_image` | the scene still | n/a | General route |

> **`enable_audio` defaults to false.** A silent 15 s dialogue take is 180
> credits of nothing. Set it explicitly on every generation that needs sound,
> and check it twice. For true silent B-roll, leaving it off is correct.

### Price

**Measured: 12 credits per second of output, flat, across the v3.0 tiers.**
15 s = 180, 9 s = 108, 8 s = 96. Duration was the only lever that moved the
price; resolution did not appear to. There is no discount for one long
generation, so splitting into short chunks costs nothing extra. What a credit
costs in money depends on your plan; check Kling's current pricing page.

Costing example: a 12-shot, 37-second scene split at the 3-shot cap is five
generations, about 444 credits for one take of everything, about 1,330 for the
three takes per chunk the checklist asks for. The real budget question is how
many chunks need a fourth take, not how many passes you can afford.

---

## (d) Prompt construction on the MCP route

`lib/director.md` Stage 3 is the rulebook for Kling prompts and
`scripts/validate_prompt.py --kind kling --mode <omni|general>` enforces it.
Run the validator on every prompt before it is sent. What follows is how those
rules land on the MCP.

### d1. One string, no stepper

The web UI has one text box per shot and a duration stepper each. **The MCP has
neither.** One prompt string carries every box:

1. Write the boxes in order as `Shot 1 (about 3s): ...`, `Shot 2 (about 2s): ...`.
2. Shot Box 1 holds the global setup AND shot 1. There is no separate setup box.
3. Kling allocates shot boundaries itself. Treat durations as intent; the edit
   trims to the beat map. Durations are integers and the total is at most 15 s.

### d2. What goes in the boxes (from `lib/director.md`)

- **Shot Box 1** opens with the library camera and audio line, verbatim from
  `lib/camera.json` `kling_boilerplate.global_setup`:
  `Handheld camera throughout. No music, only SFX and natural ambience.` (or the
  static version).
- **Omni:** then one assignment line per character, naming the image by what it
  shows ("Boss is based on the man in the navy suit image."), plus "The scene is
  based on the scene image." if a scene still is attached. **Never refer to
  references by upload order**; Kling does not know it.
- **General:** no assignments and no names at all. Refer to people by a short
  general description ("the man in the suit"). The start frame shows who they are.
- **No visual description anywhere.** No outfits, faces, rooms, lighting, tone
  string. The images carry the look. A Kling box says only: library camera
  string, who, action, emotion, the exact line, how it is said.
- **Camera wording is copied exactly** from `lib/camera.json`. Consecutive boxes
  never share an angle, except in a General speaker batch off one close-up start
  frame (that is what `--mode general` allows).
- **Voice by emotion, not timbre.** "He says it furiously, voice cracking", not
  "deep voice".
- **One line of dialogue per shot box.** Two lines in one box made Kling swallow
  the sentence.
- **Every box ends with** `The subject stops talking, silence in the room.`
  This line is load-bearing: without it, a quiet beat that follows a shouted one
  inherits the shouting, and clips end abruptly. Other phrasings that helped
  pin a quiet register: "he never raises his voice in this shot", "he does not
  speak for a long moment", "a second long silence".
- **Off-lens eyelines** go in the action ("his eyes stay on her just off-camera
  to frame left"). Characters looking into the lens read as a presenter, not a
  scene.

### d3. How to batch a two-person scene

**One generation = one voice.** This fixed voice drift between lines: all of
speaker A's lines come from one generation off A's close-up start frame, all of
B's from another off B's close-up, and the edit cuts between them. Split a
speaker's batch at a line break when it passes 15 s or about 3 shots, keeping the
same start frame across the halves so face and voice stay matched. An angle that
appears once in the scene (the only wide, the only close-up) is its own
generation with its own start frame. Wides and anything built on movement go to
Seedance per `lib/director.md`'s Kling-vs-Seedance rule; putting the one real
action beat (a door burst) on Kling was the wrong tool.

### d4. Worked example (General route, one speaker's first three lines)

Illustrative, built to the rules above; not a transcript of a sent prompt.

```
model: kling-video-v3_0
arguments:
  prompt: |
    Shot 1 (about 3s): Handheld camera throughout. No music, only SFX and
    natural ambience. Medium Shot. The man in the suit leans toward the woman
    just off-camera to frame left, eyes on her, never the lens. He is furious.
    He bellows, voice cracking: "YOU HAVE NO CFO. HOW ARE YOU DOING FINANCE?!"
    The subject stops talking, silence in the room.

    Shot 2 (about 2s): Close Up. The man in the suit roars at her off-camera,
    punching each word, livid: "SHOW ME THE PROMPTS." The subject stops
    talking, silence in the room.

    Shot 3 (about 3s): Medium Shot. The man in the suit jabs a finger toward her
    off-camera, disbelieving and loud: "A HUNDRED CREATIVES LAST WEEK. YOU HAVE
    NO DE-SIGN-ER!" The subject stops talking, silence in the room.
  duration: "8"
  aspect_ratio: "9:16"
  resolution: "1080p"
  imageCount: "1"
  enable_audio: "true"
  first_image: <URL of his close-up scene still>
rationale: Speaker A batch, chunk 1 of 2, lines 1-3, 3-shot cap.
```

`DE-SIGN-ER` is deliberate: hyphenating a word the model garbles forces the
syllables apart (failure-log item 6). Check the exact camera strings and the
per-box character limit with `validate_prompt.py` before sending; the example
is shaped to the rules, not run through the validator for you.

---

## (e) The cherry-pick checklist

**A human picks every take by eye and ear.** Every version cleared on metrics
alone failed. Metrics diagnose; they do not clear.

Generate **3 takes of every chunk**, pick the best, and roll more only if all
three fail. Reject a take if any of these fails:

1. **The face matches the character sheet**, the same person in every shot.
2. **The line is word-for-word.** No stretching ("shooow me the proooompts"),
   no invented words.
3. **Props behave.** Nothing vanishes or floats mid-shot.
4. **Eyeline goes off-lens** toward the other character.
5. **The room matches the stills**: same window, table, walls.
6. **The last second is clean**: no morphing, no invented props.
7. **No burned-in text and no music** in the audio.

Before a human looks, run the two mechanical gates (`CINEMATIC.md`):
`scripts/check_takes.py` (section f) covers 2, 6 and 7 plus merged pauses and a
quiet beat that inherited the shout; `scripts/watch_take.py --kind dialogue`
covers stalls, unwanted cuts inside a generation, held poses, soft frames and a
morphing tail. Items 1, 3, 4 and 5 still need eyes.

After a chunk passes, build a **room-consistency contact sheet** across all
passing takes and confirm the same window, curtains, table, props and doorway
appear in each. Room drift was a recurring failure until a peopled scene still
became the room anchor.

**Downloads.** Result URLs expire **24 hours** after the job finishes and the
credits are already spent, so download at once. Name picks by batch and shot
(`b1_s1.mp4`, `b2_s1.mp4`) in a picks folder, then either copy them into the
assembler's clip pattern or point `paths.clip` at the picks folder
(`"picks/{name}.mp4"`).

---

## (f) `scripts/check_takes.py`: the mechanical take checker

Checks a take before a human spends attention on it. Whisper knows whether the
line was said word-for-word; the audio envelope knows whether a scripted pause
exists; ffmpeg knows whether the register dropped. Only "is it believable" needs
a person.

```bash
python3 scripts/check_takes.py --write-template takes.json    # starter file
python3 scripts/check_takes.py --expect takes.json take_1C.mp4 1C
python3 scripts/check_takes.py --expect takes.json takes/*.mp4  # ids inferred
```

- **Take id**: a trailing bare id, `--take-id` for every path, or inferred from
  the filename (`_<id>_` first, then a loose substring match only when exactly
  one id fits).
- **Exit code = number of failures**, so it drops into a shell loop.
- Needs `ffmpeg`, `ffprobe` and `openai-whisper`.

Checks: word-for-word against the scripted lines (missing words and words not
in the script), scripted pauses, register drop after a quiet anchor, a music bed
(a loud floor in the gaps between words, where room tone should be), and tail
room after the last word.

### The expectation file

Everything film-specific is data. Minimum:

```json
{
  "takes": {
    "1B": {
      "lines": ["nine minute replies", "no support team",
                "show me the prompts", "whose", "free"],
      "pause_after": [["prompts", 0.8], ["whose", 0.8]],
      "quiet_after": "prompts"
    }
  }
}
```

- `lines`: what the **script** says, lowercase, no punctuation. Derive it from
  the screenplay, never from what a take produced, or the checker ratifies the
  defect.
- `pause_after`: `[word, seconds]` pairs where the beat map needs a real gap. A
  merged delivery fails. (Above: two broken fragments "whose... free" read as a
  different line entirely when delivered as "who's free?".)
- `quiet_after`: one word; everything after it must measurably drop in level.

Optional top-level keys, all defaulted: `whisper_model` (`small.en`), `filler`
(words too common to prove anything; `no` is deliberately NOT filler, because a
dropped negation says the opposite of the line), `homophones` (spelling
collapses such as `who's` to `whose`; genuine homophones only), and
`thresholds`: `register_drop_db` 4.0, `register_before_s` 2.0,
`register_after_s` 2.5, `register_offset_s` 0.3, `music_gap_min_s` 0.6,
`music_floor_db` -28, `tail_room_s` 0.15.

Know its blind spot: a shouted compound noun can come back from Whisper mangled
a different way each time (one run: `news less ter`, `new's lester`,
`newslester`) and the checker cannot tell a real articulation fault from
mishearing. Use a larger Whisper model, listen, and insure key words with a
burned-in caption.

---

## (g) `scripts/assemble.py` and `scripts/grade.py`: cut, treat, caption, card, grade

`assemble.py` turns picked takes into a finished film in two ratios.
`grade.py` is the same grade pass standalone.

```bash
python3 scripts/assemble.py build --config my_cut.json   # the film
python3 scripts/assemble.py build                        # built-in example cut
python3 scripts/assemble.py grade in.mp4 out.mp4 [--strong]
python3 scripts/assemble.py grade in.mp4 --compare [--at 1.0]   # before/after stills
python3 scripts/grade.py in.mp4 out.mp4 [--strong]       # same pass, own script
```

Needs `ffmpeg`/`ffprobe` and Python 3.10+ with `numpy`, `scipy`, `Pillow`.

### Config shape

The built-in `CONFIG` in the script is one real 14-segment cut, kept as a worked
example: its paths, fonts, card text and captions belong to that ad. Pass your
own JSON with `--config`; it is merged over the built-in recursively, and **lists
replace wholesale** (a partial cut list is never what anyone means), so always
supply the full `cuts` list.

| Key | What it holds |
|---|---|
| `video` | `width`, `height`, `fps` (24), `sample_rate` (48000), `crf_segment`, `crf_master`, `preset` |
| `paths` | `work` dir, `clip` and `still` format strings with `{name}`, `caption_font` (first of SF / DejaVu / Liberation / Arial that exists), `card_font`, `card_mark` |
| `captions` | `size`, `min_size` (shrinks to fit), `max_width_frac`, `y_frac`, `stroke`, `weight` |
| `audio` | `fade_s` (0.12), `roomtone_gain`, fixed `roomtone_seed` / `room_seed`, `peak_ceiling` (0.97), `skip_clips` (picture used, audio never placed) |
| `music` | `bed` wav, `stop_index` (cut index where it stops dead), `gain`, `fade_s`. Set `bed` or `stop_index` to null for no music |
| `card` | end card: `duration`, `bg`, `title`, sizes, mark, `tag` line |
| `outputs` | `master` (9:16) and `ratios`, each `{file, crop, crf}` |
| `grade` | `{"strong": false}` |
| `cuts` | the segments, below |

A cut entry: `clip` (a take through `paths.clip`) or `still` (an image insert
through `paths.still`), `in` (seek, s), `dur` (timeline length, s), `lead`
(start this clip's audio early: J-cut), `tail` (let its audio run past the cut:
L-cut), optional `crop` (ffmpeg crop before scaling, for a punch-in), and `caps`
as `[[TEXT, in, out], ...]` relative to the cut.

```json
{
  "paths": {"work": "tmp/myfilm", "clip": "picks/{name}.mp4", "still": "stills/{name}.jpg"},
  "music": {"bed": null, "stop_index": null},
  "card": {"duration": 2.0},
  "outputs": {"master": "out_9x16.mp4",
              "ratios": [{"file": "out_4x5.mp4", "crop": "crop=1080:1350:0:285", "crf": 18}]},
  "cuts": [
    {"clip": "b1_s1", "in": 0.0, "dur": 3.0, "lead": 0.0, "tail": 0.4,
     "caps": [["YOU HAVE NO CFO.", 0.3, 1.6]]},
    {"clip": "b2_s1", "in": 0.0, "dur": 2.6, "lead": 0.35, "tail": 0.3, "caps": []},
    {"still": "insert", "dur": 1.5, "caps": []}
  ]
}
```

Lead and tail values are tuned by ear. A first assembly with all zeros cuts
flat and needs a pass of tuning. Caption text is rendered pixels, so it follows
`RULES.md` too: no em or en dashes (the built-in example still carries some;
do not copy them).

### What the audio timeline does

- Every clip's audio is pulled mono at 48 kHz, run through `room()`, faded
  0.12 s at each end so overlaps blend without clicks, and summed onto **one
  bus** that already holds a continuous `roomtone()` bed. The continuous bed plus
  J-cuts and L-cuts is what makes a row of separate generations read as one
  room instead of a slideshow.
- `room()` is a synthetic small-room impulse: a direct hit, seven early
  reflections between 9 and 70 ms, and a noise tail (85 ms decay, low-passed at
  3.6 kHz), mixed 55% dry / 45% wet, then half of everything above 3.8 kHz
  subtracted. Dry generated audio read as dubbed; measured against real footage
  it had far less reverb and a brighter spectrum, and this recipe (RT60 about
  350 ms) closes most of the gap. Seeds are fixed so a re-render sounds identical.
- Music starts at zero, loops, and **stops dead** on the chosen beat
  (`stop_index`) rather than fading through it.
- Only a peak ceiling is applied. Measure and set loudness afterwards per
  `RULES.md` section 5 (about -14 LUFS, true peak under -1 dBTP, no dynamic
  loudnorm over a bed).
- Segments are re-encoded and concatenated, then the audio bus is muxed and the
  grade applied in one pass. The 4:5 is cropped from the graded master so both
  ratios share one grade (check it on its own; `RULES.md` prefers building each
  ratio natively where framing suffers).

### The grade (`chain()` in both scripts)

AI video is mathematically clean, and clean is the tell. Contrast and
saturation down, grain back on:

```
eq=contrast=0.94:saturation=0.92:gamma_r=1.01,noise=alls=6:allf=t+u
```

`allf=t+u` makes the grain move between frames like real grain. `--strong`
inserts `selectivecolor=reds=0 0 0 -0.12:yellows=0 0 0 -0.10` to pull shine out
of skin highlights; it is whole-frame and blunt, so use it on tight faces only.
Grain 6 is at the low end on purpose: Kling output already carries texture and
stacking reads as noise. `--compare` writes a before/after still pair to judge
by eye.

---

## (h) The failure log. Read before spending a credit.

1. **Cap a generation at about 3 shots.** Five shots in 15 s garbled dialogue
   (soft lip sync, "designer" came out "designder", 11 shouted syllables in 3 s).
   Splitting is also cheaper, because price is flat per second.
2. **Kling ignores the shot plan under load.** One 5-shot take gave shot 4 five
   seconds and starved shot 5 to 0.9 s; another never cut to shot 5 at all.
   Wording does not fix it. Split the batch and keep the same start frame.
3. **A location sheet fed to Omni rendered as a shot**: the last 0.9 s of a take
   became a top-down view of the wrong character in the wrong scene. Never feed
   a location sheet to Omni. For single-character lines use General with the
   scene still as `first_image`. The room anchor that worked was a **peopled**
   scene still; removing the sheet with nothing in its place also failed.
4. **Write silence as an instruction and pin the register** (section d2).
5. **Hyphenate a word the model garbles** (`DE-SIGN-ER` worked). Some words
   resist; stop spending and insure them with a caption.
6. **`query_tasks` is badly stale.** Measured: a finished job reported QUEUING
   for about 8 minutes after completing in 106 s; a 58 s job reported RUNNING for
   about 14 minutes; `finishTime` is meaningless until status is COMPLETED; the
   credits reading also looked cached. Poll every 5+ minutes and **never switch
   models or resubmit because a job looks stuck**.
7. **Download results within 24 hours.** There is no second chance.
8. **No face sheet on a from-behind shot.** The model resolves the contradiction
   by painting the face elsewhere: a duplicate person or a shadow figure on the
   wall. Drop the sheet, let wardrobe carry identity, use GPT Image for
   precision. When the face IS visible, a face sheet is fine, including in an
   edit call.
9. **Gemini image models silently reject "same person" prompts.** Five-second
   failures with no error text. Reference-consistency work goes to Kling's
   image models (failed jobs appeared to be refunded).
10. **Some concepts cannot be prompted away.** "Broken white door debris" came
    back as shattered china five times. Drop the concept or remove it afterwards
    with `kling-image-o1`.
11. **Edit the reference's actual frame; never recreate it.** Six recreations
    drifted the pose and physics. What landed: a GPT Image EDIT of the reference
    frame (pose kept, face, wardrobe and room swapped), then a `kling-image-o1`
    background fix.
12. **Step the reference frame by frame before building a still.** Three physics
    errors survived rounds of prompting and were obvious at 0.1 s steps
    (`ffmpeg -vf fps=10` into a strip sheet).
13. **Build dialogue scenes from singles.** One readable face per frame,
    performance played just off-lens. Two-shots only when faces are small. In an
    over-the-shoulder, cap the foreground shoulder at a quarter of the frame; an
    uncapped one ate the speaker.
14. **Generate the location sheet from a peopled still.** Models render empty
    rooms unrealistically. Character sheets: front, three-quarter, profile on
    white, and say "PHOTOGRAPH, not illustration" (some models return drawings).
15. **Hold tone across a character's sheet views.** Front and profile drifted in
    saturation (one profile measured 49, another 102, against a portrait at 71),
    and every video generation inherits that drift. Judge with PIL `ImageStat`,
    not by eye.
16. **Never let a model render UI text.** Corner-pin the real screenshot in post.
17. **Label contact sheets.** Stamp OPTIONS or CLIP N START and never mix them;
    a grid of alternatives was read as a storyboard.
18. **Never ship audio no human has heard.** Whisper also hallucinates looping
    phrases over music-only spans; probe regions, do not trust a full-pass list.
19. **ffmpeg traps.** `-loop 1` on still overlays or the overlay never shows;
    re-encode hybrids (a stream-copy mux of mismatched streams runs away); cap
    segments with an output-side `-t`.
20. **Checkpoint one shot end to end before batching.** Generate, assemble,
    grade, and get a human's eyes and ears on it; report spend there. Decide the
    stop-loss before the first credit. Do not batch ahead.
