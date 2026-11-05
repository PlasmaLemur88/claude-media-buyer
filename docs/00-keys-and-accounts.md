# Accounts, keys and costs

Every person who runs this engine uses their own accounts and pays for their own
generations. Nothing in this folder belongs to anyone else, and no key is ever
shared.

## 1. What you need

| Account | Needed? | What it unlocks | Where the key goes |
|---|---|---|---|
| **fal** (fal.ai) | Yes | Voices (MiniMax, ElevenLabs v3, Seed Audio), sync.so lip-sync, Seedance video and audio | `FAL_KEY` in `.env` |
| **Replicate** | Yes | Stills and video: GPT Image 2, Nano Banana, Seedance, Wan, Veo and others | `REPLICATE_API_TOKEN` in `.env` |
| **Google AI Studio** | Optional | Gemini TTS voices, the `gemini-video` skill (watch a video), Nano Banana images | `GEMINI_API_KEY` in `.env` |
| **Kling** (kling.ai) | Optional | Kling 3.0 video and Kling image models (identity work, silent B-roll) | Not a key: an MCP entry in your Claude config, OAuth login |

Free, local, no account: Whisper (transcripts and read checks), Chatterbox
(local voice clone), Robust Video Matting (`scripts/matte.py`), ffmpeg,
Remotion, and the composed music bed (`scripts/bed.py`).

A missing optional key is not a blocker. The doctor says what it would unlock
and the rest of the engine keeps working.

## 2. Where keys live

One file: `.env` at the engine root. `setup.sh` creates it from `.env.example`,
which lists the three names and where to get each one:

```
REPLICATE_API_TOKEN=
FAL_KEY=
GEMINI_API_KEY=
```

Spell the names exactly. `REPLICATE_API_TOKEN` is TOKEN, not KEY; a
misnamed line is invisible to the loader. `scripts/keys.py` reads each key from
the environment first, then from `.env`, so every script finds it the same way
whatever folder you run from.

Rules:

1. **Paste keys into `.env`, never into a chat.** A key that appeared in a chat
   log, a screenshot, a screen share or a support ticket is burned. There is no
   partial exposure.
2. **Never print a key.** No `cat .env`, no `echo $FAL_KEY`, no key as a
   command-line argument (arguments show up in `ps` and shell history). To see
   what is set, print names only: `cut -d= -f1 .env`.
3. **`.env` is gitignored. Keep it that way.** Before committing anything, run
   `git check-ignore -v .env` and see it matched. Never zip the engine with a
   filled-in `.env` inside.
4. **Rotate in this order:** create the new key, put it in `.env`, verify it
   with a free call, then delete the old one. You are never locked out
   mid-render.
5. **Your Claude config file is a secret file too.** It holds your MCP entries,
   and some MCP servers store keys in it. Do not paste it anywhere.

If you prefer typing a key without it echoing, this appends it safely:

```bash
read -r -s -p 'FAL_KEY: ' V && printf '%s=%s\n' FAL_KEY "$V" >> .env && unset V
chmod 600 .env
```

(If `.env` already has an empty `FAL_KEY=` line, delete that line first, or
just paste the value after the `=` in a text editor.)

## 3. Setting up each account

**fal.** Sign up at https://fal.ai, add a payment method or credit, create a
key at https://fal.ai/dashboard/keys. Pay as you go. An error saying
"exhausted balance" or `TOP_UP` means top up, not a bad key; retry once a
minute or two after topping up and never re-run steps that already finished.

**Replicate.** Sign in at https://replicate.com (GitHub login), add billing,
create a token at https://replicate.com/account/api-tokens. The token starts
`r8_` and is shown once. Pay per prediction. If you turn on auto-reload there
is no ceiling except the one you set, so set a stop-loss (section 5).

**Google AI Studio.** Create a key at https://aistudio.google.com/apikey. There
is a free tier with rate limits; paid use is billed through Google Cloud.

**Kling.** Sign up at https://kling.ai and buy a plan or credits. Then register
the MCP server so Claude can drive it:

```bash
claude mcp add --transport http kling https://kling.ai/mcp
```

or add this under `mcpServers` in your Claude config:

```json
"kling": { "type": "http", "url": "https://kling.ai/mcp" }
```

The entry holds no secret; you log in over OAuth. Three things that waste a
session if you miss them:

- **MCP tools only load in a session started AFTER the entry exists.** Add it,
  quit Claude entirely, start a new session, then look for the tools.
- **Quit Claude before editing the config file by hand.** Claude writes that
  file on exit and can overwrite your change.
- **Authorize with `/mcp` in an interactive session while your browser is
  logged into the account you pay for.** If you have more than one Kling
  login, the MCP binds to whichever one the browser has. Check with the free
  calls `who_am_i` and `query_membership_and_credits`: a balance far lower
  than you bought means you are on the wrong login. Switch, do not top up.

Kling plan credits are granted monthly and **expire on a fixed date**; they do
not roll over. Read the expiry on the Credit Details page. The MCP spends the
same plan credits as the website (there is no separate API meter), though the
MCP may show a slightly different number because it leaves out bonus credits.
Use `kling.ai/app/...` URLs in the browser; other Kling domains can redirect
and drop the session.

## 4. What it costs (rough public prices, check each provider's page)

| Job | Rough cost |
|---|---|
| Kling 3.0 video | 12 credits per second of output on every tier; a 15 s take is 180 credits. Duration is the only lever. |
| Kling image, 2 images at 2k | `kling-image-v3_0_omni` about 4 credits, Nano Banana 2 about 30, `gpt-image-2` about 70. A single surgical edit on `kling-image-o1` about 2. |
| sync.so Lipsync v2 Pro (fal) | about $5 per output minute |
| Paid video background removal | about $0.14 per second. Use `scripts/matte.py` instead: local and free. |
| Seed Audio voice clone (fal) | about $2.50 once to mint a reusable speaker |
| TTS (Gemini, MiniMax, ElevenLabs v3) | cents per script |
| Replicate video models | per second of GPU time; a heavy exploration day can run to $100+ |

Prices change. Look up the model page before quoting a cost, and state the
cost to the operator before every paid call (see `CLAUDE.md`, SPEND).

## 5. Rules that keep spend sane

1. **Take one shot all the way through before batching.** Voice, picture, cut,
   and a human who watched and listened. Batches built on an unchecked setup
   get thrown away whole.
2. **Write the stop-loss down before the first paid call.** Deciding mid-run,
   with sunk cost on the table, does not work.
3. **Kling Omni: set `enable_audio: true` when you want sound** (it defaults to
   false, and a silent 15 s take is 180 credits of nothing) **and set
   `resolution: 1080p`** (it defaults to 4k, which costs more and is not the
   finishing size).
4. **Never resubmit because a job looks stuck.** Kling's task status can lag by
   up to about 14 minutes and the balance display is cached. Poll every 5+
   minutes.
5. **Download results as soon as they land.** Result URLs expire about 24 hours
   after the job finishes.
6. **Failed and policy-rejected jobs appear to be refunded.** Do not
   panic-spend to make up for one.
7. **Verify a key with a free call, never with a render.** A test render on a
   video model is a real charge.
8. **Never ship audio no human has heard.**

## 6. What the doctor checks

`python3 scripts/doctor.py` spends nothing and never prints a key. It reports:

- **Command line tools:** ffmpeg and ffprobe.
- **Python packages:** numpy, scipy, Pillow, Whisper, librosa, OpenCV,
  Playwright (and its headless Chromium for the widow check).
- **Fonts:** a caption font for the acted-scene assembly.
- **Keys:** whether `.env` exists and whether `REPLICATE_API_TOKEN` and
  `FAL_KEY` (required) and `GEMINI_API_KEY` (optional) are filled in. It checks
  that a value is present, not that it is valid; a revoked key still passes.
  It reminds you that Kling is an MCP entry, not a key.
- **Motion graphics:** Node.js 18 or newer and the Remotion packages.
- **Repo:** the director spec, camera library, reference images and option
  sheets are present.
- **Self-test:** runs `tests/regression.sh`, which spends nothing.

Exit code is the number of problems. Fix those, then run `bash setup.sh` if
packages are missing. Two things setup cannot do for you: installing ffmpeg on
a Mac (Homebrew asks for your login password) and installing Node.js (a normal
installer from https://nodejs.org).
