# OfferCard: an offer card animated by the voiceover (example ad 104)

**What it is for.** Turning an approved static offer ad into a video without
changing the design. Everything is on screen from frame 0, so a muted scroll
reads the whole ad. The voiceover then drives the motion: a shine across the
headline, each benefit line pops as it is said, each card row lifts while it
is said, and the button pulses on the price. `captions: true` adds the spoken
words in a band (top on 9:16, under the button on 4:5).

**Where the words live.** The fixed strings (card title, byline lines, button,
per-day line, the caption word fixes for Whisper mishearing the platform
name) and the colours are `offer_card` in the active brand's `brand.json`. The price and
audience count (`readers`) default to `OFFER`. The headline, benefit lines and rows are the
ad's own copy and live in its config.

**Config fields** (`format: "OfferCard"`):

| field | what it does |
|---|---|
| `vo`, `bed`, `bedVolume` | voiceover, music bed (looped), bed level (0.12) |
| `bg`, `dark`, `btnBg` | background colour, light-on-dark or dark-on-light text, button colour |
| `brand` | `"person"` or `"logo"`, as in AerialKinetic |
| `headline`, `lineA`, `lineB` | the headline and the two benefits (`b` bold part, `t` the rest) |
| `rows` | `[{ pre, bold, post, cue, logos? }]`; `cue` is the word that lights the row |
| `cues` | `{ lineA, lineB, price }` spoken words that time the benefits and the pulse |
| `captions`, `eyebrow`, `perDay` | caption band, persona callout, per-day line under the button |
| `readers`, `price`, `button` | override OFFER and the button text |
| `voEnd`, `hold` | last word's end + 0.35; seconds held after it |

**Render.**

```bash
./build.sh 104
npx remotion still OfferCard104-Tell-PAID-4x5-cover out/104_cover_4x5.png
```

**The sample.** Example ad 104 in `brands/example/configs.mjs` is a sample offer
card with the free macOS voice. Captions, eyebrow and the per-day line are switched on so
every path renders. Its figures are sample values that prove the format
renders; the real ones for any ad come from the active brand's `brand.json`
and `BRAND-GUIDE.md` in `brands/<slug>/`.

# The Cards PAID ledger now matches the later AdPaid

An older `AdPaid.tsx` component had moved past what `AdCaptions.tsx` carried,
so it was not ported as a separate format; its changes went into the Cards
ledger instead, because Cards was built as the merge of AdPaid and the free
components. What changed:

- Every ledger line lands on the word that says it (`LEDGER.priceCues`,
  `LEDGER.worthCue`, and the cue word in each `extras` entry), with a timed
  fallback if a word is missing. The old fixed offsets drifted on re-records.
- The card is top-anchored, so 4:5 no longer slices its last rows.
- The logo wall is four real partner offers from `LEDGER.tools`, plus
  "+ many more". An old wall showed five well-known brands that were never
  partners.
- `worth` and `extras` can be overridden per ad, as ad 477 did.
- The paid end card prints `end_card.paidFollowOn` then `paidFollowOnAccent` in
  the accent colour (for example "The guide is free. The course is $X a year."). That
  puts a price on screen, which the older "no price on screen" rule forbids.
  Settle which rule wins before a paid cut ships.

Sample: `Cards403-Tell-PAID` in `configs.mjs`.

The end card's name, button and sublines now come from the active brand's
`brand.json` (brand.name, the_offer.free.cta, and the sentences of
the_offer.free.close).
So the "zero pixel difference" claim below no longer holds for the end card:
it prints whatever brand.json says today, not the audience count and CTA the
original cuts carried. The body and hook are unchanged.

---

# Format 2: Cards, captions over artwork

**A voiceover, a full-frame hook card, then static infographic artwork with the
transcript burned in underneath it, hard-cutting from one image to the next on
the beat of the read. On paid cuts, a two-column FREE vs PAID ledger before the
end card.**

- Component: `motion-graphics/src/AdCaptions.tsx` (`format: "Cards"`)
- Palettes: `motion-graphics/src/theme.ts`
- Ledger copy, logo wall, end-card strings: `ledger` and `BRAND` in
  the active brand's `brand.json`, plus the active brand's `brand.json` for
  the end card
- Configs: `ADS` in `motion-graphics/src/configs.mjs`; render with
  `motion-graphics/build.sh <number>`
- Word timings: `scripts/timings.py`; read checks: `scripts/prosody.py`,
  `scripts/readcheck.py`; music bed: `scripts/bed.py`

The component was built by merging five older per-persona components into one,
and was pixel-diffed and audio-diffed against them with zero difference. Every
behaviour that differed between them is now a config field.

## What the format is

```
 ┌──────────────────────────┐   0 → hookEnd
 │                          │   HOOK CARD. The opening line at 84-108px,
 │  Your company doesn't    │   full frame, no artwork. Each word is dim until
 │  have an AI person.      │   it is spoken, so the line types itself in.
 │                          │   One or two words are in the accent colour.
 └──────────────────────────┘

 ┌──────────────────────────┐   hookEnd → bodyEnd
 │ ┌──────────────────────┐ │   ARTWORK, 980px wide, top-aligned at y=90.
 │ │   the infographic    │ │   Hard cut to the next image on the beat.
 │ └──────────────────────┘ │   Optional static punch-in (zoom + focus).
 │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  │   Scrim fades the bottom of the frame to solid.
 │ ┌──────────────────────┐ │   CAPTION BAND, 940px, accent rule on top,
 │ │ caption phrase, the  │ │   4-7 words at a time from the timings file,
 │ │ spoken word accented │ │   the spoken word in the accent.
 │ └──────────────────────┘ │
 └──────────────────────────┘

 ┌──────────────────────────┐   bodyEnd → voEnd   (PAID cuts only)
 │  FREE      │ PAID        │   THE LEDGER. Left: what free gets you.
 │  Every…    │ [logos]     │   Right: partner logos, then "+" rows, each
 │  Forever   │ + …         │   landing on the word that says it.
 └──────────────────────────┘

 ┌──────────────────────────┐   voEnd → end
 │        (avatar)          │   END CARD. Avatar, brand name, audience line,
 │        brand name        │   button, wordmark. 3.2s free / 3.6s paid.
 │        [button]          │
 └──────────────────────────┘
```

Everything is authored in absolute pixels for 1080x1920. The 4:5 cut is the
**same layout rendered in a 1080x1350 frame**, not a crop of the 9:16 file (see
the gotcha on what that hides).

## When to use it

- You have a voiceover and real artwork worth showing. Without infographics it
  is just a caption over a colour field.
- You want it to work muted. Everything the voice says is on screen, and on paid
  cuts the free/paid boundary is a visual, not a claim.
- You are testing a **hook**. The hook card is its own act, so swapping the
  opening line changes one thing.

**When not to.** It is the most expensive of the motion-graphics formats to
produce: voiceover, word timings, hand-tuned scene boundaries, music. To test a
hook cheaply, the OneWord/RSVP format (`docs/20-format-rsvp.md`) reuses audio
you already have. Paid cuts run long for cold traffic: free cuts measured
24-32s, paid cuts 38-47s.

Example: `102 Beginner "CrackedMugs"` in `brands/example/configs.mjs` (free and
paid) is the reference Cards ad.

## The scene model: zoom + focus, and no Ken Burns

**There is no Ken Burns in this format.** Hard cuts only, no crossfades, nothing
moving inside a scene. `zoom` is a **static punch-in chosen per scene and
held**. Nothing in the component reads the frame number to move artwork. (If you
find ffmpeg `zoompan` in an old build script, that is a dead prototype path.)

A scene is one image plus a window onto it:

```js
{ img: "img/levels.jpg", zoom: 1.5, focusX: 1, focusY: 0.75, from: 10.88, to: 15.12 }
```

- `zoom: 1` lays the whole 980px-wide artwork in the frame. Above 1 the artwork
  is drawn larger than the 980x1240 box and the box clips it.
- `focusX` / `focusY` are the **centre of interest in the artwork's own
  coordinates** (0 = left/top edge, 1 = right/bottom, 0.5 = middle). The
  component puts that point at the centre of the frame, clamped by `offset()` so
  the artwork is never pulled past its own edge.

Lessons from an earlier Cards ad whose poster ran text to the frame's edge:

- That poster's text ran to x=1279 of 1280, so any punch-in not flush
  right (`focusX: 1`) slices words. **Losing the left of an illustration reads
  as a crop; losing text reads as a bug.**
- Know when *not* to punch in. Level one stays wide because the poster's L1 tip
  contradicts the voiceover line, and that contradiction only becomes legible
  if you punch in. Wide also lands the title and the whole ladder.
- **Scene boundaries land on the word that opens each beat**, read from the
  timings file. Not evenly spaced, not guessed. Regenerating a voiceover
  invalidates every one of them.

**The aspect assumption.** `ART_ASPECT = 1.25` is hard-coded because the house
infographics are 1280x1600. In the crop path, artwork of another aspect gets its
vertical focus wrong (a 978x1348 image overran the box by about 118px, all off
the bottom; a near-square 2000x1969 image sat about 130px too high). Set the
per-scene `aspect` (height/width) for any artwork that is not 1.25, and look at
the frame.

## How `words.json` drives the burned-in captions

The captions are not written by hand. They are the measured word timings of the
voiceover, grouped into phrases at render time.

**1. Transcribe.** `scripts/timings.py` runs Whisper with word timestamps and
writes a flat array to the brand's `assets/words/<number>.json` (paid cuts
`<number>_paid.json`, or set the ad's `words` stem to override):

```json
[ {"w":"Does","s":0.0,"e":0.32}, {"w":"your","s":0.32,"e":0.44}, … ]
```

**Always read the transcript it prints.** Whisper mishears brand names (for
example "Mapleworks" as "Maple works") and splits numbers (`250,000` into `250` +
`,000`, `100%` into `100` + `%`). Split numbers are repaired at render time; a
misheard word has to be fixed in the file.

**2. Group into phrases.** `phrases()` in the component:

- Close a group when a word ends a sentence *and* the group has 3+ words, or at
  7 words.
- Walk each group and glue punctuation-only tokens (`%`, `,`, `.`) and
  punctuation-then-digit tokens (`,000`) onto the word before.
- Merge any group under 3 words into the previous one if the result stays at 8
  or fewer.

Two consequences to know. The glue only runs **inside** a group, so if the
7-word cap falls between `100` and `%`, the cards read `…readers 100` /
`% free forever.` Check the last cards of every render; the fix is to reword the
line or change `phrases()` and re-check every Cards ad. And the 7-word cap wins
over sentence boundaries, so cards like `yet? Someone everyone goes to, someone
who` are normal. Sentence-clean cards mean changing `phrases()`, not the config.

**3. Pick the group for this frame.** The caption finds the group whose span
contains `t`. When `t` falls in a silence between groups it **holds the last
group that finished**, so the band never blinks out between sentences.

**4. Accent the spoken word.** The word where `s <= t <= e` is in the accent
colour; the rest is ink.

**5. Paid cuts use one merged file.** Concatenate the body voiceover, a 0.55s
gap and the shared offer outro into one wav, and merge the word arrays by
shifting every outro word by `body duration + 0.55`. One timings file then spans
body and offer, and the captions keep running over the ledger with no extra
machinery. Because the outro audio is identical in every paid ad,
`voEnd - bodyEnd` is the same constant in every paid cut; a config that
disagrees has a wrong number.

## The hook card

The hook gets the whole frame, no artwork, at 84-108px.

**Which words appear** is `w.e <= hookEnd + hookLead` (`hookLead` default
0.35s), a filter on the same timings array. So the card's content is a function
of `hookEnd` alone. `hookEnd` may deliberately run past the first sentence so
the card carries the setup line too: a short question like "Are you the boss?"
is gone before it can be read, so hold the card through the next line.

**`hookSize` is set by eye, not a formula.** More words, smaller type, but
shipped cards put 14 words at 96px and 11 at 84-88px. There is no auto-fit; a
hook too large wraps into the vertical middle of the frame and looks broken.
Render the 4:5 and look at it.

**Each word is dim until spoken** (`t >= w.s`), so the line assembles in time
with the read.

### Why `hookAccent` is a string, not a `RegExp`

Remotion serialises `defaultProps` to JSON, and `JSON.stringify(/founder/i)` is
`{}`. A `RegExp` in a config arrives as an empty object and the render crashes,
or, if guarded, silently accents nothing. Pass the regex **source** as a string
and the flags separately; the component builds the RegExp.

- **Escaping is doubled.** `"(AI|yet\\?)"` in JS gives the source `(AI|yet\?)`.
  Writing `"(AI|yet?)"` makes `?` a quantifier: a silent wrong-word accent.
- **The pattern is tested against the token including its punctuation**, as
  Whisper emits it (`yet?`, `one.`, `don't.`). Hence patterns like
  `(Francisco\.|up\.)` and `one\.?$`.
- **Never put `g` in `hookAccentFlags`.** `.test()` on a global regex advances
  `lastIndex` and matches every other occurrence.

The same JSON round-trip is why the theme is passed by **name** (`"dark"` /
`"paper"`), not as an object. Object identity does not survive serialisation.

## Theme switching

Two themes in `theme.ts`, chosen per ad **by the artwork, not the persona**:

| | dark | paper |
|---|---|---|
| background | `#12100E` | `#F7F5F1` |
| ink | `#F7F3EC` | `#16130F` |
| accent | `#E4703C` | `#D9541F` |
| muted | `#8B8378` | `#6E675E` |
| dim (unspoken hook words) | `#3A352F` | `#CFC9BF` |
| caption band | `rgba(18,16,14,0.94)` | `#F7F5F1` + drop shadow |
| scrim | fade to 0.97 at 58%→70% | fade to 1.0 at 56%→68% |
| logo chip | `#F4F1EB` | `#FFFFFF` |

Light artwork goes on paper; anything goes on dark. Dark artwork on paper
punches a hole in the page; the `inset` scene flag frames it as a deliberate
card with a border and shadow instead. The paper caption band gets a drop
shadow because it is the same colour as the background and needs the lift.

The "READ IT ON" label on the **large** end card is `#6E675E` on both themes
while the subtitle above it uses `muted`; the `READ_ON` map in the component
preserves that. Do not collapse it to `muted`.

## The two-column FREE vs PAID ledger

Only on `offer: "paid"`, between `bodyEnd` and `voEnd`. It replaces the artwork;
captions and scrim keep running.

**The split is the point.** Listing everything together leaves the free/paid
boundary to the voiceover alone, and most of the feed plays muted. The screen
has to carry it.

**Timing.** The turn to the ledger sits at `OUTRO_SPLIT = 0.46` of the way
through the outro. From there each line lands on the word that says it:
`LEDGER.priceCues` for the price, `LEDGER.worthCue` for the value line, and the
cue word in each `extras` entry, with a timed fallback if a word is missing.
Cue words survive re-recorded outros; fixed offsets drifted.

All ledger copy lives in `ledger` in the active brand's `brand.json`: `freeLabel`, `freeRows`,
`paidLabel`, `price`, `worth`, `tools`, `more`, `extras`. A config may override
`worth` and `extras`. Offer facts (price, item count, value) come from the
active brand's `BRAND-GUIDE.md` and `brand.json` in `brands/<slug>/`; never
type them into a config from memory.

### The partner logo wall

Real marks, not names, each in a light chip at uniform size, because the set
mixes monochrome and full-colour marks and half of them vanish on the dark
theme. `kind: "icon"` means the partner publishes no wordmark, so the name is
set beside the icon.

- **Only show offers customers can actually redeem.** An earlier wall showed
  five brands from a partner *target* list that had never signed.
- **Screen every SVG before it goes in `public/`.** An SVG is executable markup:
  check for `<script>` elements and external references.
- If the logo files go missing, set the names in the accent colour rather than
  ship broken images.

## The end card

Two size sets; pick deliberately with `endCard`.

| | `large` | `compact` (default) |
|---|---|---|
| avatar | 260px | 230px |
| brand name | 104px | 98px |
| subtitle | 42px | 38px |
| CTA | 58px, `30px 84px` | 54px, `26px 76px` |
| wordmark | 380px | 330px |
| hold | 3.2s | 3.6s paid / 3.2s free |

The name, button and sublines come from the active brand's `brand.json` and
`BRAND` in the active brand's `brand.json`. On paid cuts the end card adds `end_card.paidFollowOn` then
`paidFollowOnAccent` in the accent colour, which puts a price on screen; see the
note at the top of this file before a paid cut ships.

When the funnel is ad → landing page → free signup → paywall, the button stays
the free call to action on both offers and the paywall does the selling. Set
it to whatever the brand's own funnel needs.

## The config, field by field

| Field | Type | Required | Default | What it does |
|---|---|---|---|---|
| `offer` | `"free"` \| `"paid"` | **always state it** | `"free"` | `"paid"` adds the ledger between `bodyEnd` and `voEnd`, the paid follow-on line, and a 3.6s end card. |
| `theme` | `"dark"` \| `"paper"` | yes | | Chosen by the artwork. |
| `vo` | string | yes | | Voiceover under `public/`. Paid: the merged body+outro file. |
| `bed` | string | yes | | Music bed under `public/`. Looped, but build it to length anyway. |
| `hookEnd` | seconds | yes | | End of the hook card and `from` of the first scene. |
| `hookAccent` | regex source string | yes | | Accent words on the hook card. Escapes doubled, matched with punctuation. |
| `hookAccentFlags` | string | no | none | Usually `"i"`. Never `"g"`. |
| `hookSize` | px | yes | | 84-108, set by eye. No auto-fit. |
| `hookLineHeight` | number | no | `1.12` | |
| `hookLead` | seconds | no | `0.35` | How far past `hookEnd` a word may end and still be on the card. |
| `scenes` | `Scene[]` | yes | | Body artwork in order, tiling `hookEnd` → `bodyEnd` with no holes. |
| `bodyEnd` | seconds | paid only | `voEnd` | Where the body VO stops and the offer outro starts. |
| `voEnd` | seconds | yes | | Where all speech stops: last word's end plus padding (0.22 on paid; 0 to 0.24 on free). `timings.py` prints the last word's end, not `voEnd`. Do not guess. |
| `endCard` | `"large"` \| `"compact"` | no | `"compact"` | |
| `endCardSeconds` | seconds | no | 3.6 paid / 3.2 free | |
| `worth`, `extras` | string, `[label, cue][]` | no | `ledger` | Paid ledger overrides. |

Ad-level fields around `config` (`number`, `persona`, `personaDir`, `format`,
`concept`, `conceptSlug`, `hookStyle`, optional `words`) drive the composition
id and the output filename; see `docs/80-naming-and-delivery.md`.

### `Scene`

| Field | Type | Required | Default | What it does |
|---|---|---|---|---|
| `img` | string | yes | | Path under `public/`. |
| `from` / `to` | seconds | yes | | Land on the word that opens the beat. |
| `zoom` | number | no | `1` | Static punch-in. Never animated. |
| `focusX` / `focusY` | 0-1 | no | `0.5` | Centre of interest in the artwork. |
| `fit` | `"crop"` \| `"contain"` | no | `"crop"` | `"contain"` fits the whole image and ignores zoom/focus. |
| `boxH` | px | no | `1240` | Artwork box height. |
| `aspect` | number | no | `1.25` | Artwork height/width, used for focus placement. |
| `inset` | boolean | no | `false` | Frames dark artwork as a card on the paper theme. |

## Worked example

The free 102 entry in `brands/example/configs.mjs`:

```js
{
  number: "102", persona: "Beginner", personaDir: "01-beginners",
  format: "Cards", concept: "CrackedMugs", conceptSlug: "cracked-mugs",
  hookStyle: "Tell",
  words: "101",                       // reuses ad 101's voiceover and word file
  config: {
    offer: "free",                    // never omit it
    theme: "dark",
    vo: "brand-active/audio/vo_example_free.mp3",
    bed: "audio/bed_phrygian.wav",
    hookEnd: 1.2, hookLead: 0.1,      // where the hook word ends, from the word file
    hookAccent: "cracking",
    hookAccentFlags: "i",
    hookSize: 108,
    voEnd: 15.26,                     // last word ends 15.06
    endCard: "compact",               // the long name overflows the "large" card
    scenes: [
      { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.0, focusY: 0.5, from: 1.2, to: 6.06 },
      { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.5, focusX: 1, focusY: 0.57, from: 6.06, to: 8.12 },
      { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.5, focusX: 1, focusY: 0.84, from: 8.12, to: 10.3 },
      { img: "brand-active/img/drying-order.jpg", zoom: 1.0, focusY: 0.5, from: 10.3, to: 15.26 },
    ],
  },
}
```

Its paid twin is the same config with `offer: "paid"`, `words: "101_paid"`, the
paid voiceover, `bodyEnd: 10.3` and `voEnd: 22.02` from its word file, and the
last scene's `to` moved to `bodyEnd`. Nothing else changes, so the pair isolates
the offer.

Render: `./build.sh 102` in `motion-graphics/`. Both ratios are separate
compositions of the same component, never cropped from each other.

## Assets this format needs in `motion-graphics/public/`

```
img/*.jpg|png          the artwork; 1280x1600 (1.25) unless you set `aspect`
brand/                 avatar and wordmarks used by the end card
logos/*.svg|png        the ledger's partner marks, screened
words/<number>[_paid].json   one per cut, from scripts/timings.py
audio/vo_*  audio/bed_*      one pair per cut
```

**Screen reused social-post artwork at full resolution before it goes in an
ad.** Infographics pulled from past posts have carried live share links with
access tokens and a teammate's local file path. Brightness-ranking will not
catch that.

## Gotchas

**The 4:5 cut hides the bottom third of the artwork.** The layout is authored
for 1080x1920; at 4:5 the scrim is fully opaque from y=945 while the artwork
box still runs to y=1330, so about the bottom 31% of every image is invisible.
**Choose `focusY` on the 4:5 render**, and never move the artwork's top padding
or the caption's bottom padding without checking both ratios.

**Scene windows must tile without holes.** The lookup falls back to the *last*
scene, so a gap silently shows the final image instead of erroring. First
`from` = `hookEnd`; last `to` = `bodyEnd` (paid) or `voEnd` (free).

**`voEnd` is not a design choice.** Too low and the end card cuts into the read;
too high and the ad ends on silence.

**Regenerating a voiceover invalidates every number in the config.** A rewritten
hook shifts every later word and every scene boundary. A new hook arm needs its
own timings file and its own scene times; never copy another arm's boundaries.
Two arms of one ad number with different voiceovers need distinct `words` stems
or they read each other's timings.

**The music bed must loop.** The component loops it, which matters when a
generated bed is shorter than the ad; without the loop a 10s bed leaves the
rest of the ad, including the end card, silent.

**Read the transcript and run `scripts/prosody.py` before every render.** In one
session six of eight voice takes had a defect that would otherwise have shipped:
phantom repeated phrases, dropped words, an inserted contraction that reversed a
line's meaning, rising terminals on statements. Mechanical checks caught all of
them.

**The music duck reads `FPS = 30`, not the composition fps.** Render at another
frame rate and the duck is mistimed.

**Never edit one ad's copy of the offer.** The outro voiceover is generated once
and appended to every paid body. To change the offer: regenerate the outro,
re-merge every paid cut, re-render everything.

**The `offer` default is `"free"`.** A config that omits it silently loses the
ledger. State it on every entry.

**Brand and copy rules** (banned words, counts, price, people rules) live in
the active brand's `BRAND-GUIDE.md` and `brand.json` (`brands/<slug>/`) and
`RULES.md`. Check the hook, captions and ledger against them before rendering.
