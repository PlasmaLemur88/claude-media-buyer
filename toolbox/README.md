# Toolbox: captures, inserts, composition and checks

General tools to reach for when an idea needs them. None of them is an ad template. They grew out of a set of
talking-presenter news ads (a founder on camera over news cards, stills, a product demo and a closing card), and
that is one thing they can build together, shown at the end of this file. Each tool prints its usage with
`--help`. Every tool that can spend money has `--dry-run`. Styling (fonts, colours, pill and caption style,
presenter corner and size, safe zone, mix levels) comes from the active brand: see `brandstyle.py` and
`brands/_template/brand.json` for the `presenter` block. With no such block, neutral defaults apply.

Rules learned making the ads these tools come from: section 9 of `RULES.md`.

## The tools

| Tool | Use it when | Cost |
|---|---|---|
| `compose_shots.py` | You have a voice track and want a video cut to it: one shot per spoken phrase (stills with a push-in, clip spans, page cards, count-up number screens, two-up splits, pre-rendered inserts), optional presenter cutout in a lower corner, phrase captions, hook and label pills, a name card on a cue word, a closing clip, both ratios, mixed to -14 LUFS. Fails the render if any text leaves the safe zone or sits on the presenter or on other text. | free |
| `safezone.py` | You need to know whether text in ANY finished video or still sits where Reels/Stories UI covers it. OCR on sampled frames (Apple Vision on a Mac, else tesseract), shaded contact sheet. Also the exact check `compose_shots.py` and `type_overlay.py` run on their own text. | free |
| `capture_page.py` | You need a web page or a local HTML file as a clean image: pop-ups, cookie bars, sticky headers and ads hidden, private text boxed or blurred, whole page, one screen or one element (with a transparent background). Prints the shot-list card entry, including where the headline sits. | free |
| `quote_card.py` | A source cannot be captured cleanly (consent wall, paywall, time-outs, a pop-up over the headline). Builds a plain article-style card from the exact words. | free |
| `record_interaction.py` | You want a smooth demo of typing into a site, picking a suggestion and seeing the result. One full-resolution screenshot per keystroke, then assembled at 30 fps; any private element recorded per shot and blurred on request. | free |
| `redact.py` | A document (PDF or page images) shows names, addresses, account numbers or anything about a real person. Covers listed strings, patterns and regions, writes replacement text if asked, then re-reads the pages with OCR to prove the strings are gone. | free |
| `doc_sweep.py` | You want a document on screen as motion: pages in a viewer, travel between them, zoom onto chosen lines with a marker highlight. Takes redacted pages, PDF pages or a full-page web capture. | free |
| `type_overlay.py` | You want text typed, character by character with a caret, into any UI element (captured or drawn) over a background clip, optionally with checked lines and small print. It speeds the typing up so the final phrase is complete inside the seconds that will actually be shown. | free |
| `still_gen.py` | You need a still that reads as an ordinary phone photo. Appends the realism rules and lints the prompt for staged or glossy tells. | ~$0.08/image |
| `motion_runner.py` | You want one small real motion out of a still: Kling for people, Veo for camera and scenery, Veo first/last frame for a change between two stills. | Veo ~$3.20 per 8 s 1080p; Kling on fal: see fal pricing |
| `vocals.py` | Footage has music or noise under the voice: separate it (Demucs), cut a clean clone reference, or join the person's own lines into a real-voice cut. | free |
| `split_lipsync.py` | The script is longer than the one continuous take minus 1.5 s. Splits the voice at a gap where the presenter is off screen, lip-syncs each half from its own window, joins them unseen. Reuses `scripts/talking_head.py`. | sync.so ~$5/min |
| `matte_coverage.py` | Before showing any cutout: finds frames where the matte grabbed a phone, a laptop or a chair (coverage jumps, no face inside), and prints the clean spans. | free |
| `brandstyle.py` | See what style the tools will use for the active brand (or any brand.json). | free |

Engine tools these lean on (not duplicated here): `scripts/voice.py`, `readcheck.py`, `pace.py`,
`talking_head.py`, `lipsync.py`, `syncnet_qa.py`, `matte.py`, `lock_background.py`, `stage_build.py`,
`grade.py`, `fal.py`, `keys.py`. `scripts/motion.py` covers the same two motion calls as `motion_runner.py`
without `--dry-run`, first/last frame or the `keys.py` lookup.

## Shot lists (`compose_shots.py`)

A shot list is JSON. Paths are relative to the shot-list file; `{fmt}` becomes `9x16` or `4x5`.

```json
{
  "name": "my_ad",
  "voice": "voice.wav", "words": "voice.json",
  "presenter": "cutout.webm",
  "bed": "bed.wav", "speed": 1.0,
  "hook": "The statement on screen at frame 0",
  "labels": {"0": "", "4": "Section label from phrase 4 on"},
  "name_card": {"cue": "alex", "name": "Alex Example", "title": "Founder, Example Co"},
  "stills": "stills", "clips": "clips", "number_backgrounds": ["plain"],
  "motion": {"street": {"clip": "motion/street.mp4", "use": 3.0, "trim": 0.3}},
  "cards": {"article": {"file": "cards/article_full.png", "x0": 0, "x1": 2400, "headline_y": 138, "source": "Outlet · 16 Sep 2026"}},
  "inserts": {"sweep": {"file": "sweep_{fmt}.mp4", "fit": "rate"},
              "demo":  {"file": "demo/interaction_{fmt}.mp4", "fit": "cut"}},
  "close": {"file": "closing_{fmt}.mp4", "len": 7.5, "len_after_full": 5.5},
  "shots": {"0": ["s:street"], "1": ["c:article", "n:12,400|Label|sub line@thousand"], "2": ["+"], "3": ["i:sweep"], "4": ["i:sweep"], "5": ["i:demo:0-4"], "6": ["END"]}
}
```

- `voice.json` is Whisper word timings (`whisper voice.wav --word_timestamps True --output_format json`).
  `compose_shots.py segments voice.json` prints the numbered phrases the `shots` keys refer to.
- `presenter`: a transparent webm (or an opaque mp4). Omit it for no presenter. Its corner, width and bottom
  edge come from the brand. It is read every frame, shown or not, so picture and voice stay locked.
- `speed`: plays voice and presenter faster or slower together (never one alone).

Tokens, one shot each; several tokens in one phrase split it evenly unless a token names a cue word:

| Token | Shot |
|---|---|
| `s:NAME` | still from `stills/` with an eased push-in; if `NAME` is under `motion`, its clip plays instead (`use` s of it, from `trim`) |
| `v:NAME:a-b` | seconds a-b of `clips/NAME.mp4` |
| `c:NAME` | a registered card (from `capture_page.py` or `quote_card.py`), scrolling slowly, headline under the label zone, source line on the side away from the presenter. `"bleed": true` on a card fills the full width instead of the safe columns |
| `n:BIG\|label\|sub` | number screen; the digits in BIG count up |
| `x:A\|B\|Left\|Right` | two stills side by side with a pill label each |
| `i:NAME` / `i:NAME:a-b` | a registered insert. `fit: rate` time-fits the clip into the span (0.8-1.3x) and merges consecutive phrases; `fit: cut` plays in real time, and a short slot shows the END of the range; `fit: full` as the last shot plays in full and pushes the close back. Presenter hidden unless the insert says `"presenter": true`; captions at the bottom with a scrim |
| `END` | the `close` clip from this phrase on; the rest of the voice plays over it |
| `+` | hold the previous shot through this phrase |

Suffixes: `@word` cut to this shot when that word is spoken; `~` hide the presenter; `^` captions high;
`_` captions at the bottom.

What it enforces on every frame: all text inside the brand's safe zone, no text over the presenter's visible
pixels, no text over other text. Any hit renames the output `*_SAFEZONE-FAIL.mp4`, lists every hit in a json
beside it, and exits 2. `--qa` writes a contact sheet with the forbidden areas shaded.

## One way to put them together: a talking-presenter news ad

1. **Script.** Problem, news, bridge, product, in plain words (RULES.md section 1). Every news claim has a named
   source you can open; a political or dated claim gets an expiry date and a sign-off before it runs.
2. **Voice.** A real recording of the presenter first. With written consent, a Seed Audio clone
   (`scripts/voice.py seed-clone`), its reference cleaned with `vocals.py ref` if the footage has a bed.
   Real-voice fallback: `vocals.py lines`.
3. **Reads check.** `scripts/readcheck.py` against the script, `scripts/pace.py check`, then a person listens.
4. **Source window.** One continuous raw take, voice + 1.5 s long (guide/LIPSYNC.md). Longer script:
   `split_lipsync.py plan` with the spans where the presenter is off screen.
5. **Lip-sync.** `scripts/talking_head.py` (one window) or `split_lipsync.py run` (two). Then
   `scripts/syncnet_qa.py` and the plosive frame strips.
6. **Cutout.** `scripts/matte.py` locally, then `matte_coverage.py` on the result. Show the presenter only in
   the clean spans it prints.
7. **Words.** Whisper word timings of the final voice; `compose_shots.py segments` to number the phrases.
8. **Pictures.** `capture_page.py` for sources (`quote_card.py` when a page blocks capture), `still_gen.py` and
   `motion_runner.py` for photos and motion (`scripts/lock_background.py` on any construction or change clip),
   `record_interaction.py` for the product, `redact.py` then `doc_sweep.py` for a document, `type_overlay.py`
   for a closing clip.
9. **Shot list and render.** One literal shot per phrase, cut on the words that name it.
   `compose_shots.py check`, then `render --qa`.
10. **QA gates.** Render passes the safe-zone check (exit 0); `safezone.py` on the delivered file; Whisper the
    final mp4 against the script; loudness near -14 LUFS; the operator watches both ratios full size on a phone
    and listens end to end. A green check means no rule was broken, never that the ad works.

## Costs

Paid calls, as billed on the project these tools came from (September 2026). Check current prices before
quoting them to anyone.

| Call | Cost |
|---|---|
| Seed Audio voice clone (fal) | ~$2.50 once per person, id valid ~12 months |
| Seed Audio read (fal) | ~$0.10 per take |
| sync.so lipsync v2 pro (fal) | ~$5 per output minute |
| Bria video background removal (fal) | ~$0.14 per second (use `matte.py`, free, instead) |
| Veo 3.1 image-to-video, 1080p (Gemini) | ~$0.40 per second, 8 s clips, ~$3.20 each |
| Nano Banana still (Gemini) | ~$0.08 per 2K image |
| Kling v3 pro image-to-video (fal) | not recorded; check fal's model page |

Everything else in this folder runs locally for free (Playwright, Whisper, Demucs, PIL, ffmpeg, Apple Vision).

## The sample

`python3 toolbox/sample/make_sample.py` builds a 30 s demonstration from placeholder parts only: a macOS `say`
voice, PIL stills, an ffmpeg gradient clip, a silhouette standing in for the cutout, and local HTML pages for
the page capture, the recorded interaction and the redacted document. It spends nothing and writes to
`toolbox/sample/out/` (gitignored). It shows the tools working; it is not a style to copy.
