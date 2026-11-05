# <Brand>: brand guide

`python3 scripts/brand.py new <slug>` copies this folder to `brands/<slug>/`.
Fill every section, with the operator, in their words where they gave words.
Read it with `RULES.md` (craft, any brand) and `brand.json` in this folder (the
exact strings, palette, logos and numbers the renderers read). The two must
agree: a fact changes in both or in neither.

Every fact gets a source and a date. Anything you cannot source, write
UNVERIFIED and ask before it goes in an ad. Keep out people's private details,
pay, contracts, account IDs, folder IDs, emails and keys: this file travels.

Compiled <YYYY-MM-DD>.

## 1. Who it is

- **Name:** exact written form, and what never to write.
- **What it is:** one sentence. The free product and the paid product, if both exist.
- **Who buys:** personas with their share of buyers, and where that number comes from.
- **The problem it solves for them:** in their words.
- **Judged on:** the one metric an ad is judged on.

## 2. Claims and their sources (never type these from memory)

| Claim | Value | Source, date |
|---|---|---|
| Audience size | | |
| Customers / members | | |
| Price | | |
| What is included | | |

Rules: which file or page each number is re-read from before a render,
anything that counts in a total but may not be named, how to confirm a perk or
a feature is real before an ad claims it.

## 3. What the product is

What each tier, session or product actually delivers, in the owner's words.
Lengths and cadences, and which phrasings are banned for them.

## 4. Voice and tone

How the brand writes: sentence length, formality, contractions, humour or none.
Two or three of the owner's own lines that sound right. For voiceover: a real
person's recording or a generated voice (engine, voice, style; mirror them in
`brand.json` `voice`).

### Pronunciation (TTS text only; captions keep the real spelling)

| Say in TTS text | Shown on screen |
|---|---|
| | |

Mirror this table in `brand.json` `voice.say_as`.

## 5. Visual style

Palette (and the one accent's job), type, logo (and whether it is settled),
real vs generated material, what may never be generated. Ads the operator
loves, with the three or four visual moves that make each one work.

## 6. Do and never

**Always:** required words, the call to action, hook style, headline style.

**Never:** banned words, claims that are never made (income, refunds,
guarantees, pricing pressure), competitor names, framing to avoid. Mirror the
hard ones in `brand.json` `never`.

## 7. People on camera

For each person who may appear: real footage allowed? voice or face cloning
allowed, and with whose written consent? how they are named on screen? Any hard
"never" from the person themselves goes first, in their words.

## 8. Links and tracking

Destination URL pattern with UTMs per objective, and any domain that drops UTMs.

## 9. Delivery

File prefix (`brand.json` `brand.file_prefix`), persona tokens, where files go,
who activates ads, how the team is told.

## 10. Approved and rejected

What the operator approved and rejected, with their reasons and the date, so no
session repeats a rejected direction.

## 11. Open questions to raise, not resolve
