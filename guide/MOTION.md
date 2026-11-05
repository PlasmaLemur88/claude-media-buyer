# Motion on stills: the realism bar

Learned on a client ad set, 25-26 Sep 2026. Client bar: "it has to look real, we can't have it look like
generative AI" and "no weird trees popping up".

## Which model

| Shot | Model | Script |
|---|---|---|
| People (faces, hands, families, anyone doing something) | **Kling v3 pro i2v** (fal) | `python3 scripts/motion.py kling <still> "<action>" <out>` |
| Camera / scenery (drone glide, palms, water) | **Veo 3.1 i2v** (Gemini key) | `python3 scripts/motion.py veo <still> "<motion>" <out>` |
| Construction time-lapse (framing, roofing, painting) | **Veo 3.1 first/last frame**, then **lock** | `scripts/lock_background.py` |

Kling beat Veo head-to-head on the same people stills: Veo added a stranger's arm at a dinner table and changed faces on a
couch; Kling kept the same people. Veo is still better for camera moves and scenery.

## Rules that keep it real

1. **Start from a realistic still**, shot like a phone photo: overcast or indoor light, clutter, imperfect framing, no golden glow.
2. **Faces small**, side-on or from behind. Never a big close-up face that has to stay the same person.
3. **One small action** per shot (a door opening, a sigh, reaching for a remote). Say "nobody walks in or out" and "same people throughout".
4. **Use 2.5-3 s** of each clip. Most failures start after 3 s (people walking in, camera drifting, houses appearing).
5. **Trim Veo's first 0.3 s** on first/last-frame clips; it often opens on a morph smear.
6. **Lock every construction clip** to its build area (`lock_background.py before.png after.png`, add an `x0,y0,x1,y1` box to exclude
   neighbours' pools, the street and passing cars; `CLIPMASK=1 PLATE=first` when the stills don't line up with the clip).
7. **Reject** any clip with morphing, new clouds/objects, strangers walking in, changing faces or screens, a build going backwards
   (framing to block shell, wrapped to unwrapped). Check a 6-frame strip before using it.
8. Veo 1080p requires 8 s clips; 6 s only works at 720p.

## "Too perfect" is the tell (client note, 29 Sep 2026)

- No posed, smiling families facing the camera. No golden-hour postcards or glossy dusk mansions.
- **No faces straight on.** People from behind, side-on, over the shoulder, or hands only.
- Plain midday or overcast light, a bit of mess (hoses, toys, laundry, a crooked frame).
- Finish every generated shot with `scripts/grade.py` (lower contrast/saturation, grain). Leave text and number screens clean.
- When an asset is used in every ad (the city plate behind the presenter, the "credibility" house), it matters most: fix those first.

## Casting note (young adults)

Gen Z / young millennials read true when their adult life sits on top of their childhood room: RGB LED strips, gaming chair,
dual monitors, energy drinks, ring light, big tumbler, skincare fridge, over old trophies and plush. Warm, never mocking.
No real logos, consoles, cartoon or anime characters.
