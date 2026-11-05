---
name: gemini-video
description: Watch a whole video with Gemini and answer questions about it (transcript, sections with timestamps, best moments, on-screen text, what happens visually). Use for any "watch / analyze / transcribe / summarize this video" request on a YouTube URL, Instagram or X link, or a local file. One API call sees every second of the video, so prefer this over claude-video-vision unless you need actual frame images in context.
---

# gemini-video

Gemini takes video as native input. This skill sends the video to Gemini once and returns
the answer, instead of sampling frames into Claude's context.

## Run

```bash
python3 .claude/skills/gemini-video/watch.py SOURCE -p "QUESTION"
```

SOURCE:
- YouTube URL: passed straight to Gemini, nothing downloaded (public videos only).
- Local file: uploaded to Gemini's File API (streams, any size Gemini accepts).
- Any other URL (Instagram, X, Vimeo, Loom): yt-dlp downloads it, then it uploads. Login-walled
  posts fail at the download step; say so rather than retrying.
- `files/xxxx`: a file kept from an earlier run with `--keep`. Use this for follow-up questions on
  the same upload so it is not uploaded twice. Gemini deletes kept files after 48h.

Flags:
- `-p/--prompt` the question. Default asks for sections, strongest moments, on-screen text, quotes,
  all with HH:MM:SS timestamps.
- `-m/--model` default `gemini-3.8-flash`. `gemini-pro-latest` for harder reasoning over the content.
- `--start/--end HH:MM:SS` watch only that span (cheaper, and the way to zoom in on one section).
- `--fps N` sampling rate, default 1. Raise for fast cuts, lower for talking heads.
- `--low-res` roughly a third of the video tokens; fine for talking heads and screen recordings
  with large text.
- `--keep` keep the upload on Gemini and print its `files/...` name.
- `--json` raw API response.

The key is read from `GEMINI_API_KEY`, then the engine's `.env`, falling back to the export line in `~/.bash_profile`
(Claude's shell does not source it). Token usage prints to stderr after every run.

## Working method

1. First pass on the whole video with the default prompt or a task-specific one. Ask for exact
   words at each timestamp so the answer can be checked.
2. Follow-ups: use `--start/--end` around the section, or a `files/` name if you uploaded.
3. Speech timestamps agreed with YouTube's caption track within about one second at five
   checkpoints on a 4-minute tutorial (2026-09-07). The wording of quotes did not always agree
   between the two transcripts, so listen before using a quote verbatim as a caption. Treat
   visual timestamps as within a few seconds and re-check with a clipped pass before cutting on them.
4. When the user needs an actual frame image (thumbnail, a still to reuse), use
   claude-video-vision `video_watch` with a tight `--start/--end` instead; this skill returns text only.

## Measured 2026-09-07

| video | path | model | wall | tokens in |
|---|---|---|---|---|
| 19s YouTube | URL | gemini-2.5-flash | 4s | 5,629 |
| 19s YouTube | URL | gemini-3.8-flash | 4s | 1,699 |
| 19s local mp4 | upload | gemini-3.8-flash | 7s incl. upload | 1,685 |
| 4m16s YouTube tutorial | URL | gemini-3.8-flash | 9s | 23,384 |

So an hour of footage on gemini-3.8-flash is on the order of 330k input tokens at 1 fps. Price per
token was not verified; check the Gemini pricing page before running many hour-long passes.
