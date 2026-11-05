# AerialKinetic: aerial footage, kinetic words, one graphic per beat (example ad 103)

This is a Remotion format; example ad 103 in `brands/example/configs.mjs` renders it. It is
not the ffmpeg aerial format that the rest of this file describes, which still
runs through `scripts/render_aerial.py`. Both use aerial footage; everything
else differs.

**What it is for.** A paid cut that has to carry a whole offer with the sound
off. The spoken words slide in line by line and light up as they are said, so
they are the captions. Under them, each beat of the script gets its own
graphic on its own cue word: a crowd for the persona hook, a wall of course
videos that scatters, the brand byline with audience and customer counts, a
card for the free product, a card for the paid product with three rows, a dollar total counting up
over a logo wall, and the price button. One aerial shot runs per beat.

**How it decides what to draw.** Sentence by sentence, from the words in the
sentence (`aerial.beats` in the active brand's `brand.json`), not from the sentence's position.
A script that says more per beat still lines up. A script with a different
shape needs new beat words, set per ad with `beats`.

**Where the words live.** Nothing a viewer reads is in the component. Copy,
colours, logo paths, beat words and cue words are `AERIAL` in the active brand's `brand.json`.
The offer numbers are `OFFER` and the logo wall is `FEATURED`, both in
the active brand's `brand.json`, both sample values marked for checking before use; replace
them with the active brand's figures. The four shared strings (brand name, free
close, free CTA, paid outro) come from the active brand's `brand.json`
(`brands/<slug>/brand.json`).

**Config fields** (`src/configs.mjs`, `format: "AerialKinetic"`):

| field | what it does |
|---|---|
| `offer` | `"paid"` or `"free"`; lands in the id and filename |
| `vo`, `bed`, `bedVolume` | voiceover, music bed (looped), bed level under the voice (0.12) |
| `shots` | `[{ src, from }]`, one per beat run, in order; a clip may repeat |
| `brand` | `"person"` (end_card.avatar + aerial.personName) or `"logo"` (aerial.mark) |
| `eyebrow`, `headline` | persona callout on screen from frame 0; the cover headline |
| `voEnd`, `hold` | last word's end + 0.35, measured; seconds held after it |
| `price`, `total`, `tools`, `readers`, `members`, `featured` | override OFFER / FEATURED. Must match what the voice says |
| `accent`, `accentWord`, `accentInk`, `align`, `weight` | persona treatment, so Meta reads each persona as a new creative |
| `keys` | extra words lit in the accent colour |
| `button` | closing button text |
| `hook` | `{ count, show, fade?, light, all? }` crowd graphic for the hook |
| `classInsert` | a clip of a real live session before the paid-product card. Needs real footage; none ships |
| `presenter` | a cut-out presenter (transparent webm) in a corner. Needs real footage; none ships. Never an AI version of a real person without consent |
| `copy`, `cues`, `beats` | per-ad overrides of AERIAL's copy templates, cue words and beat rules |

**Render.**

```bash
./build.sh 103                       # both ratios, named to the convention
npx remotion still AerialKinetic103-About-PAID-9x16-cover out/103_cover_9x16.png
npx remotion studio                  # scrub it
```

The cover is a still for the Ads Manager thumbnail. It is registered for every
AerialKinetic ad as `<id>-cover`.

**The sample.** Example ad 103 in `brands/example/configs.mjs` is a Beginner
cut for the invented example brand: the free macOS voice, the house bed, four
aerial clips re-encoded small. Its figures are invented. It is there to prove
the format renders, not to upload.


---

# The static aerial format (ffmpeg): ads 405-408

A picturesque generated landscape clip, one static text block burned over it, an
original music bed mixed under the clip's own ambience, about 9 seconds, no
voiceover. It is the cheapest format in the engine to make: one clip, one
overlay, three ffmpeg passes. It is not Remotion and not pure Node; it needs
Python with Pillow and ffmpeg.

Naming and delivery follow `docs/80-naming-and-delivery.md` (format token
`Aerial`). Brand facts that may appear in copy (price, cadence, counts, banned
words) come from the active brand's `BRAND-GUIDE.md` and `brand.json` in
`brands/<slug>/`, never from this file.

## 1. What ships

| | |
|---|---|
| Concepts | one per persona (the sample set: Founder, Boss, Manager, Individual) |
| Offers | `FREE` (the free product or signup) and `PAID` (the paid product) |
| Hook arms | two hook styles per persona; only the first paragraph differs (section 7) |
| Ratios | 9x16 native 1080x1920, 4x5 centre crop 1080x1350 |
| Length | the clip's length, about 9 s |
| Video | H.264, CRF 18, preset medium, yuv420p |
| Audio | AAC 48 kHz stereo, 192k |
| Voiceover | none |

No spaces in filenames. They break globbing and some Drive syncs and have
silently broken renders. CamelCase the hook by stripping spaces.

## 2. Inputs

**Footage.** One generated landscape clip per persona per offer, H.264
1080x1920 with its own native ambience (wind, engine hum, city). The ambience
is half the final mix, so generate with audio on. Seedance on Replicate works
(`motion-graphics/scripts/generate.py seedance "..."`, or `scripts/rep.py`);
your own footage works just as well and costs nothing. The four sample aerials ship in
`motion-graphics/public/aerial/`.

- **Generate at 1080x1920.** Nothing in the pipeline resizes or reframes, and
  the layout math in section 4 assumes that frame.
- **Save the prompt next to the clip.** The engine's own sample aerials were made
  without saving their prompts, so they cannot be regenerated from text; only
  one-line mood notes survive. A mood line is not a prompt.
- **Give the PAID cut its own landscape.** Same persona and hook, different
  footage, so the FREE and PAID ads do not read as the same ad twice in one feed.

**Music bed.** `motion-graphics/public/audio/bed_phrygian.wav`, an original
drone in C Phrygian synthesised by `scripts/bed.py` (numpy + scipy; it is not
kept in git, `setup.sh` and `build.sh` make it). 48 kHz stereo, 10.0 s, peak-normalised to 0.72, no percussion or
melody, so it has no rights question and loops without an audible seam. The
bed is deliberately a little longer than the clip so it never runs out.

**Fonts and mark** (the active brand's `brands/<slug>/assets/`):

| Asset | Note |
|---|---|
| SF Pro, `/System/Library/Fonts/SFNS.ttf` | macOS only; there is no fallback in the code. This is the whole look |
| `Lora-var.ttf` | wordmark only (SIL OFL, re-fetchable) |
| the brand mark png | the real mark, 1000x1000 RGBA, not a redraw; the file `render_aerial.py` loads from the active brand's assets |
| `Montserrat-var.ttf` | spare, for a CapCut-style geometric arm if ever wanted |

On Linux you need a licensed SF Pro or an accepted substitute, and then the line
counts change, so re-check the layout (section 4).

**Variation names are exact strings and a typo fails silently.** SF Pro exposes
`Heavy` and `Semibold` (lowercase b); Lora exposes `SemiBold` (capital B). The
`font()` helper swallows the exception, so a wrong name renders Regular and you
only find out by eye.

## 3. The pipeline: three ffmpeg passes

```
clip.mp4 ──┐
           ├─► [1] score   ─► tmp/_<key>.mp4   (video stream-copied, new AAC)
bed.wav  ──┘
tmp/_<key>.mp4 ─► [2] overlay ─► ..._9x16.mp4   (H.264 CRF 18, audio copied)
                                   └─► [3] crop ─► ..._4x5.mp4 (CRF 18, audio copied)
```

Only pass 2 lives in `motion-graphics/scripts/render_aerial.py`. Passes 1 and
3 are the two ffmpeg commands below; run them yourself or wrap them in a small
build script.

The 4:5 is cropped from the already-burned 9x16 on purpose: the two ratios then
carry pixel-identical type. Rendering a second overlay at 1350 risks two
different layouts. At CRF 18 the second encode is not visible.

### Pass 1: the audio mix

```
ffmpeg -y -v error -i "$src" -i "$BED" -filter_complex "\
[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.55[amb];\
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=1.0[bed];\
[bed][amb]amix=inputs=2:duration=shortest:normalize=0,alimiter=limit=0.95[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k "tmp/_${key}.mp4"
```

- **Music at 1.0, clip ambience at 0.55.** The music leads and the ambience sits
  under it. Invert it and you get a stock drone reel, not an ad. (0.55 was
  chosen by ear.)
- **`aformat` on both legs.** Generated clips come back at 44.1 kHz, the bed is
  48 kHz. Pinning both to 48 kHz stereo keeps the output one predictable format.
- **`normalize=0` is the important flag.** `amix` defaults to `normalize=1`,
  which divides each input by the input count and undoes the balance you set.
  Measured: the same mix peaks at -7.9 dBFS with the default and -1.9 dBFS
  without it.
- **`duration=shortest`** ends the mix with the clip, not the 10 s bed.
- **`alimiter=limit=0.95`** is a safety net plus a fixed makeup gain: its
  `level` option defaults to true, so it lifts by 20*log10(1/0.95) = +0.45 dB.
  On typical clips it does no gain reduction. For a true ceiling instead, add
  `:level=disabled`.
- **`-c:v copy`**: the video never enters the filter graph, so do not re-encode it.
- No `loudnorm`. There is no voiceover to sit under.

## 4. Pass 2: the overlay (`render_aerial.py`)

```bash
cd motion-graphics
python3 scripts/render_aerial.py public/aerial/aerial_coast.mp4 individual out/test.mp4
```

Arguments are `<in.mp4> <copy_key> <out.mp4>`. It draws one RGBA PNG (text
block plus lockup), fades it in over the clip, copies the audio, and deletes the
PNG on success. An orphan `<name>.overlay.png` after a crash is safe to delete.

**Knobs**, all constants at the top of the script:

| knob | value | what it does |
|---|---|---|
| `COPY` | dict | the words, one list of paragraphs per key. Edit this to change the ad |
| `HOOK_V2` | dict | second-person hook per persona (section 7) |
| `OFFER` | string | the shared offer paragraph for PAID cuts; check it against the active brand's BRAND-GUIDE.md before use |
| `BODY` | 62 | starting body size in px; the shrink loop steps down by 2 to 34 |
| `LINE`, `GAP` | 1.16, 0.55 | line height and paragraph gap as a share of the size |
| `WIDTH` | 0.88 | text block width as a share of the frame (950 px) |
| `STROKE` | 4 | hard black outline in px |
| `SAFE_TOP` | 0.14 H | top of the text zone, below the Reels chrome |
| fade | `st=0.35:d=0.55` | clean landscape for 0.35 s, then the block fades up over 0.55 s |

Copy keys are `<persona>`, `<persona>_v2`, `<persona>_paid` and
`<persona>_paid_v2`. The lockup tagline switches to the paid line whenever
`_paid` appears anywhere in the key (an earlier `endswith("_paid")` check gave
`_paid_v2` the free tagline).

### Typography

Plain system font, everything on screen at once, no reveal, no flourish. It is
the Instagram Stories text-tool look on purpose: a pattern interrupt against a
feed of designed graphics. SF Pro is what Stories "Classic" renders in on iOS,
so it reads as native. Only the lockup is branded.

| Element | Value |
|---|---|
| Body | SF Pro `Heavy`, 62 px, pure white, 4 px hard black stroke, each line centred |
| Wordmark | Lora `SemiBold` 76 px, the brand name |
| Mark | the brand mark png resized to 78x78 LANCZOS |
| Tagline | SF Pro `Semibold` 34 px, 3 px stroke. FREE: a line like "Read it free on <platform>". PAID: a line like "Free guide · Paid course" (U+00B7 middle dot) |

Keep curly quotes (U+201C/U+201D) in copy. Straight quotes look wrong at 62 px
Heavy.

### Layout math

```
W, H      = 1080, 1920
SAFE_TOP  = int(H * 0.14)   = 268    # Meta Reels chrome, top ~14%
lock_y    = int(H * 0.735)  = 1411   # top of the lockup
avail     = (lock_y - 70) - SAFE_TOP = 1073
y_top     = SAFE_TOP + (avail - total) // 2
```

- The block is centred inside `avail`, not the whole safe band. The 70 px is the
  gutter above the lockup; without it a tall PAID block collides with the
  wordmark.
- `SAFE_BOTTOM` (0.795 H = 1526) is computed and never used. The PAID tagline's
  last painted row is y=1548, 22 px past it. It has shipped that way; know it
  before you lengthen the tagline.
- The shrink loop is `range(BODY, 33, -2)`, so its floor is 34 px. With the
  sample copy it never fires: the tallest block (a four-paragraph PAID cut) is
  883 px against 1073 of room. A PAID block is taller, not smaller.
- **No overflow guard.** If the loop reaches 34 px and the block still does not
  fit, it keeps the last values and the text runs into the lockup. Copy that long
  is too long for a 9-second ad anyway.

### Lockup geometry

Mark and wordmark are centred as one unit: `lx = (W - (78 + 20 + text_w)) / 2`,
20 px of air between them, mark nudged 8 px down so its optical centre meets the
cap height. The tagline sits 96 px below the wordmark top. Measured ink boxes
(Pillow `getbbox`, lower bound exclusive): mark at (310, 1419), wordmark
(408, 1429, 770, 1493), free tagline (355, 1512, 727, 1543), paid tagline
(288, 1512, 795, 1549).

### The ffmpeg call

```
ffmpeg -y -v error -i src -loop 1 -i overlay.png \
  -filter_complex \
  "[1]format=rgba,fade=in:st=0.35:d=0.55:alpha=1[ov];[0][ov]overlay=0:0:format=auto" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a copy -shortest out.mp4
```

See section 8 for why `-loop 1`, `-shortest` and `format=rgba` are all required.

## 5. Pass 3: the 4:5 crop, and why the offset is 285

```
ffmpeg -y -v error -i "..._9x16.mp4" \
  -vf "crop=1080:1350:0:285" -c:v libx264 -crf 18 -preset medium \
  -pix_fmt yuv420p -c:a copy "..._4x5.mp4"
```

Height 1350 is 1080 x 5/4. The 285 is arithmetic, not taste:
(1920 - 1350) / 2 = 285, a dead-centre crop keeping rows 285 to 1634.

It works only because the layout keeps all ink inside that window. On the
tallest block the measured ink runs from y=371 to y=1548: 86 px of margin top
and bottom. That is thin (one extra 62 px line is 71 px). If you raise `BODY`,
lower `SAFE_TOP` or add a paragraph, re-measure the overlay's `getbbox()` before
trusting the crop. Measure ink, not the layout box: glyphs start below the box
top and end above the box bottom.

Audio is stream-copied, so both ratios carry the identical mix.

## 6. How PAID differs from FREE

PAID is not a variant of FREE. Several things move at once, which is why the
offer has its own token in the filename rather than a version number.

| | FREE | PAID |
|---|---|---|
| Footage | its own landscape | a different landscape |
| Paragraph 1 (hook) | the hook | byte-identical hook |
| Paragraph 2 | `Every week: ...` | `The <free product> is free. ` + the same sentence |
| Paragraph 3 | `Subscribe free.` | the shared `OFFER` line |
| Paragraph 4 | none | `Join <Brand>.` |
| Lockup tagline | the free tagline | the paid tagline |
| Ads Manager CTA | Subscribe | Learn More |

- The offer paragraph is one string shared by every persona because the offer is
  one offer. Change it once and it changes in every PAID cut.
- **Every claim in the offer line must be true today.** Check cadence and
  wording against the active brand's `BRAND-GUIDE.md` before rendering. Put no
  item count, dollar value or price on screen unless the brand guide gives the
  current figure and the ad needs it.
- **Judge PAID on cost per paying customer at 30 days, not CTR.** Naming a paid
  product filters people at the click, so PAID should lose on CTR and can
  still win the number that matters.

## 7. Hook arms: only the hook changes

The two arms of one concept differ in paragraph 1 and nothing else. Footage,
music, body copy, offer, crop and CTA are byte-identical, so the hook is the one
variable under test. Both arms run; neither replaces the other.

The house hook rule: never open on a question, and do not address a category.
Name the reader's pain as a fact and let them feel called out ("Are you a
founder?" becomes "You're a founder and you already know"). Strong hooks open on
"you", "stop" or "instead". In this format arm 1 is third person (names the
category) and arm 2 is second person:

| Persona | Arm 1 (third person) | Arm 2 (second person) |
|---|---|---|
| Founder | For founders who want to grow without adding headcount or another tool subscription. | You're the bottleneck. Hiring is slow, and another subscription won't fix it. |
| Boss | For CEOs hearing “we need more people and more software” from every department. | Every department wants more people and more software. You already know most of it is avoidable. |
| Manager | For managers whose teams lose hours to reporting, follow-ups and copy-paste. | Your team loses hours every week to reporting, follow-ups and copy-paste. You've stopped noticing. |
| Individual | For anyone doing the work of two people. | You're doing the work of two people. That isn't changing this quarter. |

If you rename a persona token in the filename, re-render: a file called "Boss"
whose pixels say "For CEOs" is a mismatch a reviewer will catch. When one folder
holds both arms, open its caption with a short variants block naming each arm,
what differs, and whether both are still spending.

## 8. The ffmpeg traps

**`-loop 1` on the still overlay, or the fade never happens.** A single-frame
image gives `fade=` no timeline. Alpha stays at its t=0 value (0) and `overlay`
repeats that transparent frame for the whole clip. You get a clean landscape, no
text, and no error.

**`-shortest` is mandatory once you use `-loop 1`.** The looped image is
infinite and `overlay` does not stop on the main input's end by default, so the
encode runs forever (reproduced: over 100 MB of output from a 9 s source before
it was killed). More generally, cap segments with an output-side `-t` (after the
filter graph, before the output name); an input-side `-t` bounds the decode and
interacts badly with loops and filters.

**Do not stream-copy a hybrid.** A `-c copy` mux of streams that disagree
(sample rate, timebase, a looped input) does not fail loudly; it runs away or
plays wrong in one player. Re-encode any stream that changed shape, and copy a
stream only when it is provably untouched:

| Pass | video | audio | why copy is safe |
|---|---|---|---|
| 1 score | copy | re-encode AAC | video never enters the graph |
| 2 overlay | re-encode | copy | audio finalised in pass 1 |
| 3 crop | re-encode | copy | same |

**`format=rgba` before `fade`.** `fade=...:alpha=1` needs a pixel format with
alpha. Drop `format=rgba` and the fade is a silent no-op.

**Byte-identical rebuilds are machine-specific.** One ffmpeg build rebuilt the
shipped files bit for bit; a different ffmpeg or libx264 will not. Do not use
MD5 as an acceptance test across machines. Compare overlays with
`ImageChops.difference(a, b).getbbox()` (None means identical) instead.

## 9. Delivery

Finished mp4s go to the delivery drive, not into git. Each ad folder carries
caption files with the exact Ads Manager fields (primary text, headline,
description, CTA, ad name) plus how to judge the test and known caveats. The
link target is always the tracked landing page with UTMs, never the raw signup
platform's URL, or attribution is lost. Two concepts aimed at the same people bid against each
other; do not run both at once. Keep scheduling out of the path: batches belong
in a manifest, not in folder names. Full convention: `docs/80-naming-and-delivery.md`.
