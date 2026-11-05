# The generation layer: Replicate, Seedance, Nano Banana Pro, and the still/sheet workflow

This is the part of the engine that makes pixels that did not exist before: video
clips, character sheets, scene stills, surgical edits. It sits before the edit.
Nothing here touches Remotion, assembly, voice or music. When this stage is done
you have a folder of mp4s and jpgs, and everything downstream treats them as
footage.

Two platforms are involved and they are not interchangeable:

- **Replicate**: a plain HTTPS API billed in USD. Used for **Seedance** (video),
  **Veo** (video with faces), **Nano Banana Pro** (images and edits) and
  **Kling 2.5** (video with faces and props). Scriptable; the runners are below.
- **Kling**: driven through its own MCP tools, billed in credits. Used for
  dialogue video and for the character-sheet and still workflow (`gpt-image-2`,
  `kling-image-v3_0_omni`, `kling-image-o1`). It is covered here because the
  image routing decision spans both platforms.

Acted scenes follow `CINEMATIC.md` and `lib/director.md`; where they disagree
with this file about a prompt, `lib/director.md` wins. Kling dialogue specifics
are in `docs/60-format-kling-dialogue.md`, and the cross-cutting failure log is
`docs/70-playbook-and-failures.md`.

---

## 1. Routing: which model for which job, and what each refuses

The most expensive mistake is sending a job to the wrong model and then trying to
fix the result with prompt wording. Route first, by what a model refuses.

### Video

| Model | Where | Use it for | It refuses or breaks |
|---|---|---|---|
| `bytedance/seedance-2.0` | Replicate | Landscapes, aerials, action, wides, any shot with **no supplied human face**. Good native audio. Good first-frame to last-frame interpolation. | **Any human face as an input, in any slot.** See section 4. |
| `google/veo-3.1` | Replicate | Takes a face input **and** produces native audio with lip sync. 9:16, 4/6/8 s, 1080p. | Weapon-over-person two-shots. Rate-limits hard (429): submit sequentially, 45 s backoff. Drifts in the last ~0.5 s (props vanish, faces bruise): trim early, always check tails. Defaults to landscape if you omit `aspect_ratio`. |
| `kwaivgi/kling-v2.5-turbo-pro` | Replicate | Faces plus props. | **No audio at all**, so every line needs dubbing, which is the costliest failure path. |
| `kling-video-v3_0` / `_omni` | Kling MCP | Silent B-roll, multi-shot, up to 7 reference images. | Native audio runs mouths 250-500 ms off (see RULES.md section 4). Kling 3.0 has no Replicate slug. |

For a talking generated character, RULES.md is the rule: one Seedance
text-to-video take per speaker, and real people through a real recording plus
sync.so (`scripts/lipsync.py`).

### Images

Relative cost, measured as Kling credits for a 2-image job at 2k:

| Model | Platform | Cost | Use it for |
|---|---|---|---|
| `gpt-image-2` (t2i) / `gpt-image2` (i2i) | Kling | 70 credits | Part A portraits, the **Part C triptych compile**, base images, and any shot where instruction-following must be exact (from-behind framings, precise blocking). Holds an analog film grade best. |
| `gemini-3.1-flash-image` (Nano Banana 2) | Kling | 30 credits | General image work with no identity matching. **Rejects likeness prompts** (section 6). |
| `kling-image-v3_0_omni` | Kling | 4 credits | Reference consistency and identity matching: Part B profiles, new angles off an approved base image, location sheets, no-face detail shots. The default for everything except the compile. |
| `kling-image-o1` | Kling | ~2 credits | Surgical single-change edits on an approved frame: removing debris, replacing a background behind an untouched subject. |
| `google/nano-banana-pro` | Replicate | USD, section 8 | Text-to-image sheets and stills and multi-reference edits when you are already on Replicate and do not need Kling's identity lock. **Returns wrong sizes: always normalise** (section 5). |

The spread is about 17x (70 credits vs 4). Two rules follow:

> **Reference-consistency work goes to Kling's own image models.**
> **The graded hero compile goes to the GPT-image class.**
> Everything else: the cheapest model that can do it.

Kling name trap: text-to-image is `gpt-image-2`, image-to-image is `gpt-image2`
(no second hyphen). Using the t2i name on an i2i call fails. Confirm against the
MCP's own model list.

---

## 2. The runners

The engine has three, from simplest to safest:

- **`scripts/rep.py <owner/model> '<json>' [outfile]`**: any Replicate slug with a
  literal JSON payload. Creates the prediction, polls every 3 s, prints the
  output URLs and saves the first to `outfile`. Reads `REPLICATE_API_TOKEN` from
  the environment, then `.env` at the engine root. No dry run, no size
  normalisation, no retry policy: anything you run spends money.
- **`scripts/fal.py <endpoint> '<json>' [outfile]`**: the same shape for fal
  endpoints (Seedance on fal, sync.so, MiniMax). Reads `FAL_KEY`. Also exposes
  `upload(path)` and `download(url, out)` for other scripts.
- **`motion-graphics/scripts/generate.py`**: the guarded Replicate runner for the
  four models in this file. **Every call is a dry run until you pass `--go`**:
  without it, it prints the exact payload and a cost note and stops.

```bash
python3 motion-graphics/scripts/generate.py --list              # models, slugs, notes
python3 motion-graphics/scripts/generate.py --schema seedance   # real inputs, free
python3 motion-graphics/scripts/generate.py seedance "aerial over a coastal \
  city at golden hour, slow push in, no people" --out public/footage/city.mp4
python3 motion-graphics/scripts/generate.py nano "..." --set aspect_ratio='"9:16"' \
  --set resolution='"2K"' --out gen/still.jpg --go
```

Knobs: model key (`seedance`, `veo`, `kling`, `nano`), the prompt, `--out`
(relative to `motion-graphics/`), `--set K=V` (repeatable, JSON values allowed,
used for image inputs and any parameter beyond the defaults), `--go`. Defaults:
Seedance 5 s 1080p 9:16, Veo 8 s 1080p 9:16, Kling 5 s 9:16. Images saved with
`--out` are cover-fit to 1080x1920 on download. Note it looks for `.env` inside
`motion-graphics/`, not the engine root; check `--help` if the token is not
found.

Two gaps to know before you use it:

- It normalises **every** image it saves. A character or location sheet must keep
  its native size (section 5), so for a sheet run without `--out` and download
  the printed URL yourself.
- It has no batch mode, no automatic retry, and no refusal detection. Apply the
  policies in sections 7 and 9 by hand.

### Model registry: slugs and parameter names

The four models disagree about parameter names. Sending the wrong name is either
rejected or silently ignored. Run `--schema` for anything beyond this table.

| Generic slot | `seedance` (`bytedance/seedance-2.0`) | `veo` (`google/veo-3.1`) | `kling` (`kwaivgi/kling-v2.5-turbo-pro`) | `nano` (`google/nano-banana-pro`) |
|---|---|---|---|---|
| first frame | `image` | `image` | `start_image` | - |
| last frame | `last_frame_image` | `last_frame` | - | - |
| reference images | `reference_images` | `reference_images` | - | `image_input` (array) |
| audio | `generate_audio` | `generate_audio` | none, silent | - |
| negative prompt | - | `negative_prompt` | `negative_prompt` | - |
| seed | `seed` | `seed` | - | - |
| aspect ratio | `aspect_ratio` (`9:16`) | `aspect_ratio` (`16:9`, `9:16`) | `aspect_ratio` | `aspect_ratio` (incl. `match_input_image`) |
| resolution | `resolution` (`720p`, `1080p`) | `resolution` (`720p`, `1080p`) | - | `resolution` (`2K` used) |
| duration | `duration` | `duration` (4, 6, 8) | `duration` | - |
| format | - | - | - | `output_format` |
| poll every | 5 s | 10 s | 8 s | 3 s |

Traps in that table:

- `match_input_image` on Nano Banana Pro is meaningless on a text-to-image call.
  With no input image, always pass an explicit `aspect_ratio`.
- Replicate accepts file inputs as inline `data:` URIs (base64), so no upload step
  or public bucket is needed for images of a few hundred KB.
- Do not guess slugs. Plausible variants (`seedance-2-pro`, `kwaivgi/kling-v3`)
  404. Use `--list` or the model page.

---

## 3. Recipes

**A 9-second aerial, text to video, native audio.** A whole wave of aerial ads was
this one call with a different prompt and seed each time: Seedance, 9:16,
1080p for the final (720p while iterating), duration 9, `generate_audio` on.

Copy the shape of this prompt, not its subject. The movement is stated as a
constraint, the camera artefacts are demanded explicitly, and the last line is an
`AUDIO:` block, which Seedance honours:

```
Shaky handheld phone video shot through a scratched airliner window in bad
weather, vertical, filmed by a frightened passenger. Heavy overcast storm
light. EVERYTHING IS ONE FLAT DESATURATED BLUE-GREY WASH: sky, cloud and
subject all the same narrow range of tone, almost monochrome, low contrast, low
dynamic range, washed out. Thick turbulent cloud fills the frame and streams
past the window fast. Far out in the murk stands something impossibly enormous,
mountain-scale, only a BACKLIT SILHOUETTE against the brighter cloud behind it,
no surface, no material, no detail, no face, just a dark shape. Torn cloud
constantly drifts ACROSS AND IN FRONT of it, so it is never fully visible at
once. It does not move at all. Only the cloud and the aircraft move. PHONE
CAMERA ARTEFACTS ARE ESSENTIAL: heavy compression blocking, blown-out
highlights, motion blur, autofocus hunting, grain, glare and condensation on
the window glass. It should look like genuinely bad amateur footage, not a
clean render. No cuts, one continuous shot, no zoom, no cinematic camera move.
AUDIO: loud muffled cabin roar and turbulence rumble. A frightened passenger
close to the microphone says quietly: wait, do you see that?
```

**First-frame to last-frame interpolation.** How you get a specific piece of
motion instead of whatever the model feels like:

1. Generate the start state as a still (Nano Banana Pro, 9:16, 2K), normalise to
   1080x1920.
2. Edit that still into the end state (Nano Banana Pro with the first still as
   `image_input`, `match_input_image`), normalise to 1080x1920.
3. Seedance with `image` = first, `last_frame_image` = last, a motion prompt,
   720p while iterating.

Both stills must be the same size. A 1080x1920 first frame and a 1536x2752 last
frame produce a drift that looks "a bit off" with no error anywhere.

**A surgical edit: change exactly one thing, freeze everything else.** The model
does what you literally ask, so ask literally:

```
Keep this photograph exactly as it is: identical aircraft engine, window
frame, atoll, reef, clouds, colour and lighting. Change one thing only: in the
open deep blue water in the middle of the frame, add an enormous marine
creature swimming just beneath the surface. It reads as a colossal whale-like
animal: a long dark body, two clear pectoral flippers, and a wide tail fluke,
outline softened and blued by the water above it. It must be unmistakably an
animal and not a reef or a seagrass patch, but it stays under the surface and
does not breach. Photorealistic, matching the existing water colour and light.
```

The shape: **freeze list first** (name every element that must not move), then
`Change one thing only:`, then the change, then a negative stated as a positive
("unmistakably an animal and not a reef"), then the grade-matching clause.

**A batch of stills for one scene.** Keep the location-anchor paragraph and the
tone paragraph byte-identical across every shot; any drift between shots shows up
as a continuity error. Example shot prompt (with the location plate and the
character sheet as references):

```
Use the provided kitchen photo as the exact location: same table, window,
curtains, laptop, mug, sandwich plate, notebook, chair, doorway to the hallway,
kettle, plant, tea towel. Keep its lighting and palette. The woman from the
reference sheet sits at the table in profile, typing on the laptop, headphones
round her neck, mid-bite of the sandwich in her left hand. Calm ordinary
afternoon. Wide shot, eye level, whole room visible, she is small in frame.
Modern A24 indie drama look: 35mm film, natural window light from camera-left,
warm but desaturated, muted tones, lifted blacks, low contrast, visible grain,
slight halation, real skin texture, unglamorous domestic realism, completely
photorealistic.
```

Batch rules that cost money to learn: run jobs **sequentially** (a parallel batch
of ten Veo jobs got rate-limited); **skip any job whose output already exists** so
an interrupted batch reruns for free; and **catch a per-shot failure and
continue**, so one refused shot does not throw away the four that worked.

---

## 4. Seedance refuses human face inputs. All of them.

Not documented on the model page. Three jobs sent a human face to Seedance by
three routes and all failed identically:

```
ModelError: The input or output was flagged as sensitive. Please try again
with different inputs. (E005)
```

- `image` (image-to-video from a portrait still): refused.
- `reference_images` (the character-consistency slot): refused.
- A white-background **character sheet**: refused.

The identical prompt with **no image input** succeeded first roll. So: **Seedance
can generate people. It cannot be shown one.** Text-to-video with a person
described in words is fine. The moment you need *that* person, you are on Veo,
Kling, or a real recording.

Landscape, sky, water and architecture inputs pass fine. It is faces
specifically. The same holds for Seedance on fal, which refuses real likenesses
with `content_policy_violation`.

E005 is not transient. Do not retry, do not reword around it, do not spend
another roll confirming it.

---

## 5. Nano Banana Pro returns the wrong size. Always normalise.

Measured on files it actually wrote, all requested at `"resolution": "2K"`:

| Requested aspect | Returned |
|---|---|
| `16:9` | 2752 x 1536 |
| `9:16` | 1536 x 2752 |
| `1:1` | 2048 x 2048 |
| (early job) | 768 x 1344 |

None is 1080x1920. **Every generated still that will seed a video generation or
be composited into a 9:16 cut is normalised to exactly 1080x1920 by cover-fit:**
scale so both axes meet or exceed the target, then centre-crop.

```bash
ffmpeg -y -i in.jpg -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" out.jpg
```

Do not scale to width and crop the height. On a 2752x1536 source that gives
1080x603; an unguarded PIL crop then silently returns 1080x1920 **letterboxed with
black bands** (no error, and the black goes into the next generation), and a
guarded crop returns a short 1080x603 that breaks ffmpeg downstream.

**Exception, deliberate: sheets are not frames.** A 16:9 triptych character sheet
or a 1:1 location sheet keeps its native size. Centre-cropping a triptych to 9:16
removes the outer panels, which is the whole document.

Kling's image models have their own fixed sizes:

| Model | 16:9 | 9:16 | 1:1 |
|---|---|---|---|
| `gpt-image-2` / `gpt-image2` | 2048 x 1152 | 1152 x 2048 | 2048 x 2048 |
| `kling-image-v3_0_omni` | 2720 x 1536 | 1536 x 2720 | 2048 x 2048 |

Same normalise rule applies. To tell which family made a PNG: OpenAI's outputs
carry a C2PA `caBX` chunk, Kling's a `tEXt` `AIGC` chunk. The two agree at 1:1, so
never use a 1:1 size to guess the model.

---

## 6. Gemini image models reject identity-matching prompts

Part B of the sheet process asks for "the same person in true side profile" from
an approved portrait. On `gemini-3.1-flash-image` that job **failed in about five
seconds with no error text**: a silent likeness-policy rejection tripped by the
language the task needs ("the SAME man, identical person, same bone structure,
same jawline") applied to a supplied photograph. `kling-image-v3_0_omni` ran the
identical intent without complaint. The failed job appeared to be refunded, which
is not a reason to keep trying.

> **Rule: identity-matching work goes to Kling's image models. Gemini / Nano
> Banana is for work where nobody has to be the same person as before.**

Whether Replicate's `nano-banana-pro` carries the same filter was never tested;
identity work there always used multi-reference stills rather than "make this the
same person".

---

## 7. Error codes and what to do

| Symptom | Meaning | Action |
|---|---|---|
| `flagged as sensitive (E005)` | Content refusal: a face into Seedance, or disallowed content. | **Never retry.** Re-route (section 4) or change the shot. |
| `Service is temporarily unavailable (E004)` | Transient. | Retry after 30 s, at most twice. |
| HTTP `402` on submit | Replicate account out of credit. | Top up, then retry once a minute or two later. Never re-bill finished steps. |
| HTTP `429` (Veo especially) | Rate limit. | Sequential submits, 45 s backoff, up to ~8 attempts. Never parallelise Veo. |
| fal `TOP_UP` / exhausted balance | Out of credit, not a bad key. | Top up. |
| Gemini image job dies in ~5 s, no text | Likeness policy. | Re-route to a Kling image model (section 6). |
| Replicate job looks stuck | Replicate's status is accurate. | Poll normally. |
| Kling job looks stuck | Its task API is badly stale: a finished job reported QUEUING for 8 minutes, a 58 s job reported RUNNING for 14. `finishTime` means nothing until COMPLETED. Balances are cached. | Poll every 5+ minutes. **Never switch models or resubmit because a job looks stuck.** |

Match refusals on the prose ("flagged as sensitive", "temporarily unavailable")
as well as the code; the codes may be renamed.

**Download output immediately, in the process that generated it.** Kling result
URLs expire 24 hours after finish; Replicate's are also temporary. A URL pasted
into a note is worth nothing later.

---

## 8. Money

Rough public prices; check the model page before quoting a number, and ask the
operator before any paid call (RULES.md section 0).

- **Replicate** bills per prediction, video per second of output. Resolution is
  the biggest lever: iterate at 720p, render finals at 1080p. Veo 3.1 with audio
  is the expensive one (in the order of $0.40 per second); Kling 2.5 turbo and
  Seedance are much cheaper per second; a Nano Banana Pro 2K image is in the
  order of $0.15. A heavy generation day across all four models ran to about
  $100.
- **Kling**: about **12 credits per second of output** on every v3_0 video tier
  (15 s = 180, 9 s = 108, 8 s = 96). Duration is the only lever that moved the
  price, so splitting a long generation into shorter ones costs nothing and gives
  better results. Images: 70 / 30 / 4 / ~2 credits for gpt-image / gemini-flash /
  kling-omni / o1.
- Keys live in `.env` at the engine root (`REPLICATE_API_TOKEN`, `FAL_KEY`,
  `GEMINI_API_KEY`). Kling is an MCP entry, not a key. Rotate any key that has
  appeared in a chat transcript.

---

## 9. The character-sheet process: Part A, Part B, Part C

This stage decides whether the finished film reads as a film or as AI. A first
attempt that skipped it (references assembled ad hoc, synthetic-looking faces
fought with prompt wording) was thrown away whole. Do not skip it. The three parts
build one reference per character; every downstream still and video generation of
that character points at it.

### Part A: the front portrait

**Model: `gpt-image-2`. 16:9, 2k, quality high. Generate 2-3 variants and pick.**

Widescreen because film and TV training data is widescreen, so a 16:9 portrait
reads as a production still rather than a headshot. GPT Image 2 because it holds
an analog grade; the alternatives apply their own colour and drift off a muted
palette, and everything downstream inherits this image's tone.

Light it for the **actual scene**, not a white studio. Flat white studio light
with burned-in text labels is a large part of why the abandoned run read as
synthetic.

```
PHOTOGRAPH, not an illustration, not a render, not CGI. A real photographic
film still of a real man.

Visual tone: Modern A24 indie drama. Shot on 35mm film, single warm practical
light source from camera-left, deep unlit shadow on the shadow side of the
face, warm highlights, lifted blacks, low contrast, muted desaturated palette
of greens and ochres, visible film grain, slight halation around the light
source, naturalistic and unglamorous.

Subject: a man in his mid-40s, photographed front-facing, head and shoulders,
looking just past the camera. [wardrobe, hair, skin, sweat, stubble: be
specific, this is casting]
```

`PHOTOGRAPH, not an illustration` is load-bearing: image models return drawings
for male subjects otherwise. On Nano Banana Pro a first sheet came back as
illustration and needed "looks like a casting agency headshot sheet, completely
photorealistic".

**Then measure it and write the numbers down.** Contrast = mean of the per-channel
standard deviations; saturation = mean S of the HSV conversion. Those two numbers
are the contract for everything that follows.

```python
from PIL import Image, ImageStat
im = Image.open(path).convert("RGB")
contrast = sum(ImageStat.Stat(im).stddev) / 3
saturation = ImageStat.Stat(im.convert("HSV")).mean[1]
```

### Part B: the true side profile

**Model: `kling-image-v3_0_omni`, from the approved Part A image. Not Gemini
(section 6). Generate 3 variants.**

The prompt has to demand identity hard: "Take the man in 图片1 and photograph him
from a TRUE SIDE PROFILE, a full 90-degree side view of his head, facing
frame-left. Same face, bone structure, nose, jawline, age, hair, stubble and
wardrobe as 图片1." On Kling, reference images are addressed in the prompt as
`图片1`..`图片7`, matching inputs `image_1`..`image_7`. Use those tokens
literally.

**The acceptance test is not "does it look good". It is "does the tone match
Part A".** If grain, contrast or saturation drift between front and side, the
triptych is inconsistent and every video built on it inherits that.

### The saturation-matching lesson

Two Part B candidates both held the face perfectly. Neither matched the tone:

| Image | Saturation |
|---|---|
| Part A portrait (target) | 70.9 |
| Profile candidate A | 48.9 (drained, -22) |
| Profile candidate B | 101.5 (oversaturated, +31) |

Side by side they looked fine. Cut together in a film, that reads as two grades.
A re-roll with colour explicitly pinned in the prompt ("COLOUR MUST MATCH 图片1
EXACTLY... do not intensify it... do not drain the colour out") still missed.

**Prompt-level colour pinning does not work. Correct it numerically:**

1. Pick the candidate with the smallest combined drift,
   `|Δcontrast|/contrast_ref + |Δsaturation|/saturation_ref` (weights both axes
   proportionally).
2. Sweep ffmpeg's `eq=saturation` multiplier and keep the one whose measured
   saturation lands closest to the target.

In one worked case a candidate at saturation 80.7 against a 103.5 target was fixed
by `eq=saturation=1.13`, landing at 103.3. The correction is small; the drift is
invisible by eye and large enough to matter.

**Use one dense sweep, not a coarse-then-refine search.** Measured saturation is
not monotonic in the multiplier on dark images (1.12 gave 105.1, 1.13 gave 103.3,
1.14 gave 101.3, 1.15 jumped to 112.0), because near-neutral dark pixels tip
across rounding boundaries in clumps. A two-pass search returned 1.183 (sat 107.0)
on the job where 1.13 was right, and reported success. Sweep 0.80-1.40 at 0.01,
take the global minimum, and say so when the residual is over about 1 point:

```python
import subprocess
from PIL import Image, ImageStat
w, h = Image.open(src).size
def sat_at(v):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"eq=saturation={v:.3f}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return ImageStat.Stat(Image.frombytes("RGB", (w, h), raw).convert("HSV")).mean[1]
best = min((abs(sat_at(0.80 + i / 100) - target), 0.80 + i / 100) for i in range(61))
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", f"eq=saturation={best[1]:.3f}", out])
```

Piping rawvideo instead of writing temp PNGs gives identical pixels about 7x
faster (a 61-point sweep in ~11 s).

**Second-order lesson:** two leads can sit far apart (in one film, 70.9 vs 103.5)
and they share every frame. **Decide the relationship between the characters'
grades deliberately**: set the second character's target with the first one's
numbers in view.

### Part C: the triptych compile

**Model: `gpt-image-2` / `gpt-image2`. 1:1, T-cut layout. Not negotiable.**

Compile the approved front portrait and the tone-matched profile into one sheet.
Nano Banana produces a clean compile and then applies its own colour, shifting off
the muted palette; since this sheet is the reference for every later generation of
the character, that shift propagates into the whole film.

```
Compile 3 images into one image. Triptych, T-cut layout, on a clean pure white
studio backdrop.

Top left panel  - white studio backdrop - front face close up of the [subject]
                  from the FIRST provided image.
Top right panel - white studio backdrop - side profile from the SECOND provided
                  image.
Bottom panel    - full body, [wardrobe described in words].

Do not change the face lighting. Do not remove the graininess.
```

Do not drop the last line. Preserving lighting and grain is the reason the two
sources were built to a measured tone match.

---

## 10. Face sheet only when the face is visible

Learned over three failed rolls, and it generalises to every model.

The shot was over-the-hip from **behind** the character in a dark hallway, with
the character sheet passed as a reference. The sheet is almost all face panels;
the prompt demanded a framing with no face. The model resolves the contradiction
by **rendering the face somewhere anyway**: two rolls produced a duplicate second
man, one produced a shadow figure on the wall with his face. Re-prompting did not
fix it, because the contradiction was in the inputs.

**Fix, first try:** drop the sheet for from-behind framings and carry identity in
wardrobe words ("broad heavy build, navy suit jacket, short dark disordered hair
on the back of his head, face completely invisible. THERE IS ONLY THIS ONE MAN IN
THE IMAGE, no other figure, no shadow man."), on `gpt-image2` for precise
instruction-following.

> **Rule: pass the face sheet when the face is visible. Otherwise do not pass it.**

No-face detail shots (a laptop on a table) get no sheets and the cheap Kling
model.

**Neighbouring rule: do not overload a generation with references.** A Kling Omni
video take handed a location sheet with everything else rendered the **sheet as a
shot**: the last 0.9 s became a top-down view of the wrong character in the wrong
scene. For single-character shots use non-omni `kling-video-v3_0` with the scene
still as `first_image`. That fixed it and rendered in half the time (6 min vs 13).

---

## 11. How sheets and stills feed a shoot

Worked structure from a twelve-shot scripted ad: **twelve shots, five camera
setups.** A (low angle on character 1) in shots 4, 6, 8; B (tight close-up on
character 2) in 5, 7, 9; C (locked wide) in 3, 10, 12; D (over-the-hip from
behind) in 1, 2; E (laptop detail) in 11. Reusing setups **is** the technique:
dynamism comes from alternation, not novelty. Five stills, twelve shots.

So the still-stage deliverable is:

1. **One base image**: the peopled still, both character sheets as references, on
   `gpt-image2`. It doubles as setup C.
2. **One wide** derived from it, pulled back to expose the room. Cheap model; it
   is spatial reference, not a hero frame.
3. **One location sheet (four views)** generated **from the peopled wide**, never
   from scratch, because models render empty rooms unconvincingly. Settle here
   which side the door is on, how it is hinged, where the window is.
4. **One start frame per setup**, from the base image (look) plus the location
   sheet (geometry) plus the character sheet **only if the face is visible**.

Routing per shot: action and wides with no supplied faces (the approach, a door
break, the reveal, the stop) go to Seedance; faces, dialogue and emotion go to
Kling (silent) or the RULES.md talking route; a detail insert is a still animated
lightly. Putting the one real action beat on Kling was the wrong tool.

Cheap to remember, expensive to rediscover:

- **Step the reference frame by frame** (`ffmpeg -vf fps=10` into a strip sheet)
  before building any sequence still. It caught three physics errors prose could
  not: a bat swung at a door a shoulder actually breaks, a "sequence" with no
  forward progression, a raised bat carried while walking.
- **Some concepts cannot be negatively prompted away.** "Broken white door
  debris" came back as shattered china on five attempts. Remove the concept from
  the prompt and delete the leftovers with a `kling-image-o1` edit (~2 credits,
  first try). Reach for the edit model sooner.
- **Never trust model-rendered UI text.** Generate the screen bright and
  illegible ("a clean white webpage layout softly out of focus, NO legible text")
  and corner-pin the real screenshot in post.
- **Stamp contact sheets.** Label alternatives OPTIONS and sequences CLIP N START;
  a grid of alternatives reads to a client as a storyboard.
