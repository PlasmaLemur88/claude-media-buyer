# Lip-sync a real person (talking head)

How to make a real person say a new script on camera so that it still looks like them.
Proven on a client's founder, 24-25 Sep 2026, after five failed rounds. Script: `scripts/talking_head.py`.

**Consent first.** The person (or their team) signs off on the voice clone, the script and the final cut before anything runs.
Some people have said no to any AI version of them. Check before you start, not after.

**Cheaper cutout:** Bria on fal costs about $0.14 per second of video. For long takes, `scripts/matte.py` does the same cutout locally for free (Robust Video Matting). See `RULES.md`.

## The one rule that decides whether it works

**You need one continuous, raw take of them talking to camera that is at least as long as the new voice plus 1.5 s.**
No cuts, no captions or graphics burned in, no music under the voice, face unobstructed, roughly facing the lens.
A phone video of them explaining something for 60-70 s is perfect.

Produced ad edits, YouTube videos and reels do **not** work, even if there are hours of them. They are cut every 3-6 s,
and a lip-sync model cannot join shots: you get jump cuts, repeated head moves, or a "different person".
Check a source for cuts before trusting it (Gemini will call a 3-shot run "continuous"):

```bash
ffmpeg -i take.mov -vf "scale=480:-1,scdet=threshold=4:sc_pass=1,metadata=print:file=cuts.txt" -an -f null -
grep -c pts_time cuts.txt        # 0 = one continuous take
```

## Pipeline (all on fal, ~$10 per 55 s script)

| step | tool | notes |
|---|---|---|
| voice clone | `bytedance/seed-audio-1.0/voice-clone` | 10-30 s of clean speech (>30 s = HTTP 422). Best reference = the same raw take's audio (same mic and room as the face). Run Demucs first if there is music. ~$2.50 once, id valid ~12 months. |
| reads | `bytedance/seed-audio-1.0` | 3 takes. Post: trim pauses > 0.3 s to 0.25 s, atempo 1.15, loudnorm -16 LUFS. Spell numbers as spoken in the script. Pick by Whisper transcript match; a lower score is often just "$150,000" vs "a hundred fifty thousand". Always listen before lip-sync. |
| window | YuNet face detector | Pick the stretch of the raw take (voice + 1.5 s) where face size varies least. |
| crop | tracked square | 720 px square around the face (about 2.4x face width) from the 1080-wide frame, smoothed over 11 frames, upscaled to 1024. **Resample to 25 fps.** |
| lip-sync | `fal-ai/sync-lipsync/v2/pro` | `sync_mode: cut_off`. $5/min. Returns every frame at 25 fps. |
| paste-back | own code | Replace only a feathered ellipse around the mouth and jaw (from YuNet mouth corners, grown 1.3x) onto the ORIGINAL footage. Eyes, cheeks, hair, hands stay real. Convert 25 -> 30 fps only at the end. |
| cutout | `bria/video/background-removal` | Transparent webm. **Max 30 s per call**: split into ceil(len/29.5) equal chunks, matte each, concat the alpha channels, merge onto the full-quality RGB. |

```bash
python3 scripts/talking_head.py all --work projects/<p>/talking/<script> --source raw_take.mov --script script.txt
```

Each step writes into `--work` and skips itself if its output exists, so a crash or an empty fal balance never re-bills finished work.

## Why each choice (what failed first)

- **25 fps, not 30.** LatentSync and sync.so consume frames one-for-one at 25. Feeding 30 fps made the mouth run 1.2x behind the head (up to 1.5 s per clip) in every early version, and a face-crop paste turned that into a double face.
- **sync.so v2 pro, not LatentSync.** Head-to-head on the same crop and audio: LatentSync redraws a low-res generic mouth per frame (flicker, black mouth, "not his mouth"); sync.so keeps real teeth and beard texture and does not flicker. Never use LatentSync, not even as a fallback.
- **Face crop, not the whole frame.** Lip-sync on a full 1080 frame gives a tiny, waxy mouth.
- **Mouth-only paste.** Replacing the whole face crop pasted any model drift onto the eyes and hairline. Keep everything but the mouth real.
- **One continuous window.** Stitching three short clips (with one slowed to 0.8x) is what made the person look "like someone else".
- **Never loop a short clip** to cover a long read: it reads as nodding.

## QA before anyone sees it

1. Timing: compare the eye band (rows above the mouth) of the lip-sync output against the input crop at 5+ points; best offset must be 0.
2. Mouth: a strip of crops at p / b / m onsets (lips must close) and at open vowels.
3. Matte: composite the cutout over flat green, sample every ~4 s; no holes, no phone or table "promoted" to foreground.
4. Watch it at full size on a phone. Stills pass things motion does not.

## Composite rules (what the client approved)

- Presenter small in a lower corner (~38-40% of frame width), clear of the Reels action rail and CTA bar. Small hides flaws; big shows every one.
- Speed-ups: change voice and picture together (atempo + setpts), never one alone.
- Captions from Whisper word timings on the final voice; fix Whisper's hallucinations (it invented "$6 million" and "That's it for today" on one take).

## Gotchas

- fal returns `403 {"detail":"User is locked. Reason: Exhausted balance"}` mid-run. Top up and re-run; the script resumes.
- Two jobs writing one output name (e.g. both Bria calls saving `cutout.webm`) corrupt each other. The script gives every chunk its own file.
- Veo construction time-lapses invent trees, walls, sky and cars. Either lock them to the build area (`scripts/lock_background.py`, see guide/MOTION.md) or build a still-based reveal (`scripts/stage_build.py`). The client preferred the locked Veo version: watching crews frame and paint is the fun part.
- `fal` also returns `User is locked. Reason: TOP_UP` right after a top-up; it clears within a minute or two. Retry, don't re-bill.

## Pacing (check before lip-sync)

Run `python3 scripts/pace.py check voice.wav voice.json --speed <render speed>` on every read. 2.9-3.5 words/s as
played is right for a founder talking to camera; above ~3.6, or few pauses, reads as rushed. Fix with
`scripts/pace.py pad`, then re-run Whisper and the lip-sync on the padded wav, and don't speed the render up.
Padding silence after lip-sync does not work: the face would freeze.

## Measured QA: SyncNet (timing only)

`scripts/syncnet_qa.py <name> <video> <audio> [chunk_s]` tracks the face, makes SyncNet's 224 px crop at 25 fps and prints
the AV offset (frames; 0 = in sync) and confidence for the whole clip and each chunk. One-time setup:
`git clone https://github.com/joonson/syncnet_python tools/syncnet/syncnet_python`, then
`curl -L -o tools/syncnet/syncnet_python/data/syncnet_v2.model http://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model`,
`pip3 install python_speech_features`. (`tools/` is gitignored.)

How to read it (calibrated 27 Sep 2026 on the client's untouched raw take): real footage = offset 0, confidence 5.6, 10 s chunks
4.8-5.8, some chunks +1. So **0 or +1 is in sync; a chunk at ±2 or more is worth a look; confidence 4-6 is normal.**
Confidence is NOT a quality score: it rewards crisp, exaggerated mouths.

## Lip-sync model bake-off (27 Sep 2026, same 10 s clip and voice)

| Model (fal) | Confidence | Offset | Verdict |
|---|---|---|---|
| **sync.so v2 pro** (`fal-ai/sync-lipsync/v2/pro`) | 4.86 | +1 | **Keep. Client picked it by eye.** |
| Sync React-1 (`fal-ai/sync-lipsync/react-1`, lips) | 5.51 after a 2-frame shift | -2 raw | Highest score, 15 s input cap, per-chunk offsets; full ad scored 6.18 but the client preferred v2 pro |
| sync-3 (`fal-ai/sync-lipsync/v3`) | 4.88 | -2 | Second half fell to 3.1 |
| VEED v2 (`veed/lipsync/v2`) | 4.77 | -1 | Fine, a bit exaggerated |
| HeyGen Precision (`fal-ai/heygen/v3/lipsync/precision`) | 0.94 | -7 | Fails; also needs audio in the source video |
| Kling LipSync (`fal-ai/kling-video/lipsync/audio-to-video`) | 1.53 | -6 | Mouth barely moves |

If React-1 is ever retried: cut chunks at word gaps >= 0.4 s, shift each chunk to SyncNet offset 0, and paste back with
MASKGROW 3.0 (the v2 pro setting of 1.3 throws most of React's gain away).

## Gotcha: inserts used twice

A render loop that reads an insert (site demo, report sweep) as a forward-only ffmpeg pipe cannot rewind. If the same
insert appears twice in one ad, the second use freezes and then jumps. Give each use its own reader, play UI demos in
real time (never rate-fit typing into a short slot), and in a short slot show the END of the demo (result on screen),
not typing cut off mid-word.

