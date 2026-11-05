---
name: brand-guide
description: Build a brand guide for video and still ads, by interview, before the first ad for a new brand. Use when the operator has no brand yet, names a brand the engine does not have, wants to change how a brand looks or sounds, or says "set up my brand", "new brand", "make it look like us". Produces brands/<slug>/brand.json, BRAND-GUIDE.md and assets, then renders a style sample for approval.
---

# Build a brand guide

Every ad this engine makes comes from the ACTIVE brand: `brands/<slug>/`. A
brand is three things:

- `brand.json`, the data the renderers and scripts read (palette, fonts, logos,
  end-card lines, voice settings, format defaults). Every field is explained in
  `brands/_template/brand.json`.
- `BRAND-GUIDE.md`, the human guide: who it is for, voice and tone, visual
  style, what to always do and never do, people on camera, and the source for
  every claim.
- `assets/`, the logos, fonts, photos and reference ads.

`python3 scripts/brand.py list | new <slug> | use <slug> | show | check` manages
them. Run the commands yourself. The operator never needs to know them.

## The interview

Ask ONE question per turn, then stop and wait. Never answer for them and never
fill a field with a guess. If they do not know, write `UNKNOWN` in the field
and say what it blocks. Offer to find things out yourself (their website, their
social accounts, ads they point you to) before you ask them to type.

Go in this order, and skip anything they already told you:

1. **What is it and who is it for?** The product in one plain sentence, who
   buys it, and the problem it solves for them. Ask for the website.
2. **What do they want people to do?** The call to action and where it goes
   (a URL), and whether there is a free step and a paid step.
3. **The facts they will claim.** Prices, numbers, results, customer counts.
   Record each with its source and date. A claim with no source is not used in
   an ad until it has one.
4. **What they never say or show.** Banned words, competitor names, claims they
   cannot back, people who must not appear, anything legal has ruled out.
5. **Ads they love.** Their own best performer, and two or three ads from
   anyone that feel right. Get links or files. Watch video references with the
   `gemini-video` skill and write down the three or four visual moves that make
   each one work (layout, type, colour, pace, who is on camera).
6. **How it looks.** If they have a brand book, use it. If not, pull the logo,
   colours and fonts from their website and show them what you found. Confirm
   one accent colour whose only job is to mark what the eye lands on, and
   check text contrast is at least 7:1.
7. **How it sounds.** Their voice in writing (read a few of their own posts),
   and for voiceover: a real person recording, or a generated voice. If
   generated, render two or three short test reads with `scripts/voice.py
   --dry-run` first, state the cost, and only then generate. Add names the
   voice will misread to the `say_as` map.
8. **People on camera.** Who may appear, whether they have agreed in writing,
   and whether any of them refuse an AI version of themselves. A real
   recording beats any clone; see `RULES.md`.
9. **Formats and places.** Where the ads run (Reels, feed, Stories, TikTok,
   YouTube), and which engine formats fit. Both 9:16 and 4:5 by default.

## Build it

1. `brand.py new <slug>` and fill `brand.json` and `BRAND-GUIDE.md` from the
   answers, in their words where they gave words.
2. Put logos (transparent PNG), fonts (with a licence that allows use in ads)
   and approved photos in `assets/`.
3. `brand.py check <slug>` until it reports no problems, then `brand.py use
   <slug>`.
4. Render a style sample: one short motion-graphics ad and one cover still, in
   both ratios, from a script you write in their voice. Send the stills, and
   say plainly that you cannot judge how it looks in motion.
5. Change what they reject, one thing per round, until they approve. Write
   what they approved and what they rejected, with their reasons, into
   `BRAND-GUIDE.md` so the next session does not repeat a rejected direction.

A brand guide is never finished. When the operator corrects an ad ("too
corporate", "never that green"), add the rule to `BRAND-GUIDE.md` in the same
session and tell them you did.

## Last step: the checklist

After the brand guide is approved, write `brands/<slug>/CHECKLIST.md` from
`brands/_template/CHECKLIST.md`: keep the general items, and fill the Brand section
from the guide you just wrote (colors, type, banned words, how the name is written,
what the brand never shows). The video-reviewer agent checks every render against it.

