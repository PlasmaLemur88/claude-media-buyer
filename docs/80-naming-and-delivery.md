# Naming, filing and delivery

`motion-graphics/build.sh` builds every path and filename from the same fields
as the composition, so a render cannot land in a folder that disagrees with its
config. If you change the convention, change it in `src/configs.mjs` and
`build.sh` together and re-render one ad to check. Brand-specific values (file
prefix, persona tokens, the delivery folder) are in the active brand's
`BRAND-GUIDE.md` and `brand.json` (`brands/<slug>/`).

## The shape

```
<outputRoot>/<NN-persona>/<number>-<format>-<concept>/
    <PREFIX>_<number>_<Persona>_<Format>_<Concept>_<HookStyle>_<OFFER>_<Ratio>.mp4
    <same stem>_THUMB.jpg      one per ratio
    <same stem>_COPY.txt       the copy sheet
```

`outputRoot` is set in the active brand's `brand.json` (`brand.output_root`) and may sit outside
the engine, so the tool and the work live apart. `OUTROOT=<dir> ./build.sh`
overrides it for one run.

| Token | Changes when | Values |
|---|---|---|
| **number** | the creative concept changes | three digits, claimed before use |
| **Persona** | never; it matches the folder | from the brand guide (for example `Broad`, `Founder`, `Individual`, `Manager`, `Beginner`) |
| **Format** | the presentation changes | `Cards`, `OneWord`, `AerialKinetic`, `Aerial`, `OfferCard`, or a new format's plain name |
| **Concept** | never within a concept | CamelCase, no spaces; the idea, not the wording. An alternate goes inside it (`Concept-A-Static`) |
| **HookStyle** | the opening line changes | `Ask` (a question), `Tell` (direct statement), `About` (third person) |
| **OFFER** | the destination changes | `FREE`, `PAID` |
| **Ratio** | per render | `9x16`, `4x5` |

**No spaces anywhere, and never "Copy of".** Spaces break globbing, break some
drive syncs, and silently broke renders during a build.

### Format names say what you will see

`Cards` is graphics in sequence with a voiceover (`AdCaptions.tsx`). `OneWord`
is one word at a time, voice-synced (RSVP, `AdRsvp.tsx`). `AerialKinetic` is
aerial footage with kinetic words and a voiceover. `OfferCard` is an offer
card animated by the voiceover. The code uses the technical name; the delivery
tree uses the plain one so nobody needs jargon to file a file.

### There is no version counter

`V1`/`V2` told you two files differed but never what differed; after three
arms only someone who was there could decode it. `HookStyle` says the thing
itself. For a brand whose rule is "hooks are statements", `Ask` also marks the
pattern to retire and `Tell` the rewrite, and the whole account sorts by it.

## Claim a number before using it

Two sessions once shipped the same concept number. Check both the local output
folder and the delivery folder, and claim the number by creating the concept
folder first.

## The two rules that will not change

**1. A defect fix is not a test arm.**

**2. Broken cuts leave the delivery tree entirely.** They go to a `_retired/`
folder outside the persona folders with a `WHY-RETIRED.md` naming the defect.
Never into the concept folder, not even a subfolder. The rule that makes the
tree usable is: **if a file is in a persona folder, it can be uploaded.** A
defect one level down still turns up in a search, a drive sync or a bulk
select, and then somebody runs it.

| Situation | Where the old file goes |
|---|---|
| Defect fixed | `_retired/`, with a note naming the defect |
| One variable moved on purpose | stays put, and the copy sheet explains how to judge the pair |
| A live set superseded in the delivery drive | an archive subfolder ("Archive - replaced <date>, do not use"), not the trash |

## Why persona is the top level

An ad set is an audience, so persona is the only axis that maps to how ads get
bought, and the only one that never changes: a creative's persona is fixed the
moment it is written; its format, offer and hook are not. Number the persona
folders by share of the paying base so the biggest audience sorts first.

**Scheduling is not in the tree.** Upload weeks change, split FREE and PAID
pairs, and mean nothing a month later. A file can be in two batches; a folder
cannot. Keep batching in a manifest or a view of links, never in a path,
because moving files is how files get lost.

Keep personas that point in opposite directions apart even when they look
alike. Example: senior leaders at large firms who want their team using AI,
versus team leads at smaller firms who want to be the person with AI figured
out. Merging them blurs both ads.

## Format tests share the voice file

A format test reuses the exact voiceover file of the ad it tests against. Not
a re-recording of the same script: two rolls of one script are not the same
take, and if the voice differs the format is no longer the only variable that
moved.

Avoid two concepts that target the same people with the same offer in the same
account: you end up bidding against yourself.

## Where files go

Finished video goes to the delivery drive, not git. Git holds source, configs
and copy sheets; a repo full of video is a repo nobody can clone. Re-encode for
the destination (see `RULES.md` section 8 for size-capped settings and the
drive-upload method), and after any upload verify by exact name and byte size.
Anything created in an ad account is created PAUSED, unless the operator is running the account from `ads/` and approved it live in the chat ("turn it on", "do it").

## The copy sheet (`_COPY.txt`)

What the person running the ad account reads.

```
NNN · FREE · Persona · "Concept" · Tell

Persona:     who, and what share of payers they are
Format:      Cards | OneWord | AerialKinetic | OfferCard | ...
Hook style:  Ask | Tell | About, and the opening line verbatim
Offer:       free signup | paid product
Creatives:   <stem>_9x16.mp4, <stem>_4x5.mp4
Length:      NN.Ns

What this tests
  The one variable, and what it is tested against.

VO script
  The exact words, verbatim.

Primary text
Headline
Description
CTA
Destination URL (with UTMs)

How to judge this
  Against what, on which metric. Cost per paying customer, nearly always.

Notes
  Voice used, where the music came from, anything unverified or on hold
  (mark your own inferences as yours), and whether a human has listened.
```
