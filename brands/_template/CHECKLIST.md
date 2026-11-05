# Video checklist (template)

The video-reviewer agent checks every render against this list. Claude writes
`brands/<slug>/CHECKLIST.md` from this template, `RULES.md` and the brand's
`BRAND-GUIDE.md` the first time it makes a video for a brand, and adds a line every
time the operator corrects a video ("never that green", "too corporate"). Any note
the operator has had to give twice belongs here.

A render passes only if every item is true. For each failure: timestamp, what is
wrong, what would fix it.

## Picture
- No black or frozen frames the edit did not intend (measures.txt).
- No cut in the middle of a word or breath.
- No face cropped by a frame, card or window; no text over a face or chin.
- Resolution, ratio and duration match the brief (9:16 and 4:5 for ads).

## Captions and on-screen text
- Captions never cover a face.
- On 9:16, text stays inside the safe zone (safezone.txt shows no box outside it).
- Caption text matches the spoken words, word for word (readcheck.txt).
- The hook in the first 2 seconds is readable at phone size (first_2s.png).
- No widow: no caption or headline ends with one word alone on its last line.
- Every claim, number, price and name on screen is true to the brief and the brand guide.

## Sound
- Voice is clearly louder than music everywhere (voice minus music in measures.txt;
  without stems this is n/a).
- Final mix is about -14 LUFS integrated.
- The voice sounds like one continuous read, with no line that jumps in energy or pace.
- No clipped word at a cut or at the end.

## Structure
- Ads end on the brand's end card (brand.json `end_card`: its logo, line and call to action, shown for at least 1.5 s inside the safe zone); organic posts do not.
- Every ratio, thumbnail and copy sheet the delivery rules ask for exists.

## Brand
(Claude fills this from BRAND-GUIDE.md: colors, type, banned words, how the name is
written, what the brand never shows.)
