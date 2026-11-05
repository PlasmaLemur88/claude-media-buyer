# Shared tools: voice, reads, lip-sync, cutouts, widows

These serve both halves of the engine. The acted-scene tools (session gate, prompt
validator, take checks, assembly, grade) are in the table in `CINEMATIC.md`. Every
script prints its usage with `--help`, and every paid one has `--dry-run`.

| Stage | Command | What it does |
|---|---|---|
| voiceover | `voice.py gemini\|minimax\|elevenlabs\|seed\|seedance --text-file s.txt --voice <v> [--style] [--say-as brands/x/say_as.json] [--speed] [--trim] --out read.wav` | The whole script in ONE call (never line by line), normalised to 48 kHz mono, loudnorm -16. `--say-as` swaps spellings only in the text sent to the TTS; captions keep the real spelling. `--dry-run` prints the text and payload and spends nothing. `seed-clone --ref 30s.wav` mints a reusable Seed Audio speaker_id (~$2.50 once). |
| voiceover | `readcheck.py read.wav --script s.txt [--alt "twelve thousand\|two thousand"]` | Whisper word-level transcript diffed against the script: MISSING / EXTRA / CHANGED, numbers compared by value and flagged NUMBER. `--alt` scores which wording the audio actually says. Several reads in one call are ranked. Run it on every read before anyone listens or anything is lip-synced. Exit code = flags. |
| talking head | `lipsync.py --video take.mov --audio read.wav [--start s] [--crop W:H:X:Y] --out synced.mp4` | sync.so Lipsync v2 Pro on fal (always sync.so, never LatentSync). Pre-encodes the chosen stretch to 1080x1920 at 25 fps (sync.so consumes frames one-for-one at 25; settled, see guide/LIPSYNC.md), crf 21 so the upload does not time out, pads the read, downloads the result immediately. `--dry-run` does the pre-encode only. ~$5 per output minute. Then `syncnet_qa.py`. |
| talking head | `matte.py in.mp4 out.webm [--feather 30] [--pad-width 1080] [--green] [--prores]` | Robust Video Matting cutout, local and free on the Mac GPU. Transparent VP9 webm by default, green-screen mp4 or ProRes 4444 on request, audio carried through. First run downloads the model into `tools/torch_hub/`. |
| stills | `widows.py still.html [--size 1080x1350]` or `from widows import find_widows` in a Playwright builder | Flags any text block whose last rendered line is one word. Call `find_widows(page)` right before each screenshot and refuse to ship on a hit. Exit code = widows. |

Supporting changes: `keys.py` (reads FAL_KEY / GEMINI_API_KEY / REPLICATE_API_TOKEN from the environment, then `.env` at the engine root) and two helpers added to `fal.py`: `upload(path)` (fal CDN) and `download(url, out)`. The existing `fal.py` CLI is unchanged.

Overlap: `talking_head.py` keeps its own copy of the fal upload and sync.so call; `lipsync.py` is the standalone version for footage that is already chosen.

| toolbox | `toolbox/README.md` | Captures (web page, UI element, keystroke demo, redacted document), a shot-list composer timed to spoken words with an optional presenter cutout, typed text over a clip, a safe-zone check for any render, motion and still runners with dry runs, vocal separation, split lip-sync, and a matte coverage check. |
