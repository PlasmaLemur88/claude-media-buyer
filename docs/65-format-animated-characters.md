# 65 · Animated characters: cartoon two-handers with voices that stay put

A recurring cartoon cast (two flat 2D stick-figure men, Chuy and Beto) talking
to each other in a 9:16 reel, built in September 2026 and shipped as an
organic reel. Everything in this file came out of that build: what worked,
what was tried and rejected, and why. The worked example, with its character
sheets, approved voices, prompts and scripts, is in
`examples/animated-characters/`.

Use this route when the operator wants **invented cartoon characters who talk**:
a skit, a series with the same cast every episode, a mascot. For realistic
invented people, use `CINEMATIC.md`. For a real person, use a real recording
or sync.so (`RULES.md` section 3).

**The photoreal defaults do not apply here.** `scripts/motion.py` and
`toolbox/motion_runner.py` put "cartoon, CGI, animation" in their negative
prompts, because those tools make realistic footage. Do not run animated shots
through them. This route has its own scripts and its own LOOK block.

---

## The recipe that shipped

| Layer | Service | Model | Key |
|---|---|---|---|
| Character sheets, start frames, backgrounds | Replicate | `google/nano-banana-pro` | `REPLICATE_API_TOKEN` |
| Each speaker's lines, picture AND voice | Replicate | `bytedance/seedance-2.5`, image mode, `generate_audio` on | same |
| Silent wides and inserts | Replicate | `bytedance/seedance-2.5`, image mode, audio off | same |
| Line timings and slicing | local | Whisper `small.en` + ffmpeg (`slice_lines.py`) | none |
| Captions and assembly | local | the engine's caption tools + ffmpeg | none |

Every take: 720p, 9:16, seed 4242, watermark off.

### 1. Character sheets first, and the operator approves them

Generate one **two-shot** (both characters side by side, full body, in the
main location) and then **one single per character** off it with Nano Banana
Pro, editing the approved image rather than recreating it. Then a single per
character for each new location (the example has a truck cab for each man).
See `examples/animated-characters/sheets/`.

Make the characters different in silhouette and colour so a viewer and the
model can tell them apart at a glance: in the example one man is shorter in a
green shirt and a dark cap, the other is taller in an orange hi-vis vest. The
prompt then names only that ("the taller man in the orange hi-vis vest"); the
start frame carries the rest of the look. Nothing renders until the operator
approves the sheets.

### 2. One generation per speaker, with the sheet as the start frame

Each character says ALL of his lines in ONE Seedance take, alone in his single
frame, with a short listening beat between lines. 30 s is the cap, so a long
part splits into two takes off the same frame and the same prompt blocks
(the example's Beto needed two). One take per speaker means his voice cannot
change from line to line, and image mode means his size, position and
clothing cannot change either.

The prompt is built from fixed blocks, in this order (`prompts.py`):

1. **Who and where**: "A single flat 2D cartoon stick figure man alone in the
   frame, the taller man in the orange hi-vis vest, sitting in the passenger
   seat of a pickup truck cab on his lunch break."
2. **Voice difference**, when two characters share an accent: "He has a
   DEEPER, rougher voice than a younger man."
3. **ACCENT**, written as a dialect with its sound features (see below).
4. **ENERGY** at full strength: happy, loud, fast (about 190 words a minute),
   starts on the first frame, listens a beat between lines, ends on a closed
   mouth and holds still.
5. **LOCK**: "CRITICAL: he says ONLY these lines, in this order, word for
   word, nothing else, and stops after the last one."
6. **The numbered lines**, each with an emotion and one gesture, never a voice
   type: `3. Fast and matter-of-fact, counting on his fingers: "..."`
7. **LOOK**: the art style restated ("Flat 2D vector animation exactly as in
   the start image: hard black outlines, solid grey circular head, small dot
   eyes, thin stick limbs, no shading, no gradients, no 3D"), the background
   held still, a slow push-in, and "Dialogue only, no music, no laugh track,
   no other voices."

`python3 examples/animated-characters/generate.py speaker ...` prints the
prompt and the settings and spends nothing until `--go`.

### 3. Silent cutaways under the dialogue

Wides of both men, a phone insert, an evening wide: Seedance image mode off
the two-shot, audio off, 5-6 s each, with "Keep both men exactly as they
appear in the input frame: same heights, same positions in frame, same
clothing" in the prompt. Lay them under lines in the edit so the reel is not
only singles. Four cutaways (about 23 s) cost about $5 in September 2026.

### 4. Cut it together

- Slice each speaker's take into one clip per line (`slice_lines.py`): Whisper
  word times, a pause longer than 0.8 s ends a line, and you check the
  printed lines against the script because the model ad-libs a word now and
  then ("ándale", "boom") despite the LOCK block. Keep an ad-lib if it plays.
  A fast take runs some lines together with no pause (the example's first
  three Chuy lines came out as one 12 s run): print the word times with
  `slice_lines.py take.mp4 --words` and cut at the first word of each line
  with `--cuts`.
- Stagger the lines in script order, cutting between the two singles, and lay
  the cutaways under lines.
- Fade every audio cut 20 ms in and 60 ms out. That removed the clicks.
- Word captions timed by Whisper, a fixed hook bar at the top that never
  changes, and an end card, all in the brand's own caption style.
- The approved master ran 58 s at -14 LUFS, 1080x1920.

---

## The one constraint behind every consistency failure

**Seedance 2.5 refuses a start image and reference audio in the same call**
(Replicate and fal both; Replicate returns ModelError E006). So each call is
one of two modes:

- **image mode**: the start frame locks composition, character size and
  left/right, but nothing locks the voice;
- **reference mode**: a voice reference biases the voice, but the model
  re-stages the scene on every generation.

The first full cut used reference mode, and the men swapped sides in one
chunk, shrank in two others, and one man's vest changed. Picture consistency
wins, so the picture always comes from image mode. The voice then stays the
same because each speaker's lines come from ONE take with fixed prompt
blocks, and because the ACCENT, ENERGY and LOOK blocks are copied word for
word into every later episode.

---

## Writing an accent that sounds right

What finally passed was the accent written as **where he grew up and how the
dialect sounds**, plus the energy block, both at full strength:

> HE IS CHICANO, born and raised in East Los Angeles, Boyle Heights. He is a
> native English speaker who speaks CHICANO ENGLISH, the East LA dialect: a
> sing-song rise-and-fall melody on every sentence, stress that lands late,
> long drawn-out vowels, 'ch' where an Anglo says 'sh', dropped final
> consonants, tags like 'ey', 'right?' and 'you know?', and Spanish words
> dropped into the middle of English sentences... He does NOT sound like a
> newscaster, and he does NOT sound like a Mexican national learning English.

The same method works for any accent: name the place, say they are a native
speaker of that dialect, list four to six sound features, and say what they
must NOT sound like.

- An earlier version wrote the accent as a biography of a second-language
  speaker (born in Michoacán, Spanish first language, rolled R's). The
  operator rated it close; the dialect version replaced it and shipped.
- **Short words from the other language pull the accent** (güey, carnal,
  órale, no manches, simón, nel, mira, troca). **Full sentences in the other
  language break every model.** Keep it to single words and short phrases.
- **"Flat", "dry", "slow" or "unhurried" in a delivery note gives a
  depressing read.** Write the energy you want instead.
- Give each line an emotion and a gesture, never a voice type.

The approved voices are in `examples/animated-characters/voices/`. Use them as
the target when judging a new take.

---

## A series: keeping the voices from one episode to the next

Episode two reuses the ACCENT, ENERGY, LOCK and LOOK blocks without a single
word changed, the same seed, and new single frames for the new location. Only
the setting sentence and the lines change.

Before building episode two, generate one short test take per character with
the new lines and the new frame, then run `voice_ab.py` to put the approved
voice and the new take back to back. **The operator listens and decides**:
Claude cannot hear whether a voice still matches. Build the rest only after
both characters pass.

---

## Tried and rejected (do not retry)

| Tried | What happened |
|---|---|
| Kling 3.0 dialogue (five batches, 708 credits) | Rejected for voice: the accent was wrong. The pictures went unused. |
| Seedance reference mode for picture | Characters swapped sides, changed size, changed clothes between chunks. |
| Silent picture plus cloned TTS (Chatterbox zero-shot on fal) | Works as a fallback with a fixed voice per character. It ranked second to Seedance's own voice from one take, which shipped. |
| ElevenLabs v3 library voices (through fal) | Worked technically; the operator did not like them. The direct ElevenLabs API refused library voices on the free plan. |
| Veo 3.1 for the voice | It returns a finished mix with its own invented background bed, never a clean dialogue track, and asking it not to made the bed worse. |
| MiniMax TTS presets, Qwen voice design, VibeVoice | Rejected on sound. |
| Full sentences in the other language | Mangled by every model. |

## Other surfaces, compared in September 2026

- **Kling web app (Elements)**: binds a character's look and voice so you call
  them by name (@Chuy) in later prompts, 9:16 1080p with native audio, up to
  about 3 lines per 15 s clip; wants 2-4 images per character, which you make
  from the sheet with Nano Banana Pro. It looked like the best way to keep a
  cast across episodes, but its voices failed this cast's accent. Run one
  short proof clip before committing credits.
- **Higgsfield**: worth it only if you need Seedance 2.5 inside a web UI
  (about $59/month for Plus at the time). The engine runs Seedance on
  Replicate instead, which is pay per take and scriptable.
- **MiniMax (Hailuo) web app**: fine for silent picture from start frames; pair
  it with a voice from somewhere else.
- **Dreamina**: no saved characters, so every run re-uploads the references.
- **fal playground**: costs more than Replicate for the same Seedance takes,
  and fal refuses photoreal start frames in Seedance (cartoon frames are
  fine).
- **Replicate**: the only surface with a seed, which is why the engine uses it.

Prices and features change: check the provider's page before quoting either.

---

## Gates (same rules as the rest of the engine)

1. The operator approves the script, then the character sheets.
2. **One speaker take end to end first**: generate it, slice it, cut a
   rough with one cutaway, and have the operator watch and listen before the
   other takes are generated.
3. The operator says yes before each spend, with the number of takes and
   their length.
4. The operator judges the voice and the motion. A green check never means
   the take is good.
