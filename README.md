# claude-media-buyer

![Claude makes your Meta ads and runs them. From How to AI.](assets/cover.jpg)

We built this in a day, on 4 November 2026, because Ruben Hassid wanted to spend $10,000 on Meta ads for How to AI and let Claude run the whole thing, for a newsletter post about it. There was no media buyer on the job, no strategist and no production team, so the question was how much of their work Claude Code could do if you handed it the ad account, the brand and a folder of&nbsp;rules.

It can read your last 90 days of ads, write angles and briefs, make the videos, build the campaign paused, check that your pixel fires, preview every placement, and then check in twice a day with a short list of decisions for you. What it cannot do is watch a video or hear a voice. So a second Claude reviews every file against your brand's checklist, and the first thing that reviewer did was fail one of our own old ads on six counts, including text sitting where the Reels buttons go and a reader count that was out of&nbsp;date.

## What you get

You open the folder in Claude Code and say "run my ads". From there it works like three people and a schedule, and every chat starts by telling you where you are ("Stage 4 of 4, Buying. Step 4 of 9: Launch&nbsp;check").

1. **Setup, one sitting.** Claude checks your Mac, connects your Meta ad account through Pipeboard, and asks about your brand once.
2. **The strategist** reads your account's winners, pulls competitor ads and the words your customers use, and comes back with 8 to 12 angles, a test plan and a brief for each concept. You approve the plan.
3. **The production team** turns each brief into a video, three hook versions and a static. Motion graphics, an acted scene with people who talk, or animated characters, whichever the brief asks for.
4. **The media buyer** builds the campaign paused, runs the tracking and launch checks, and turns it on when you say so. Then, twice a day: what to pause, one budget change, which ads are tiring, what to upload next. Once a week it compares Meta's numbers with your real signups or sales, audits the account against the 72 Meta controls that ship with it, writes down what it learned, and briefs the next&nbsp;round.

You never open Ads Manager. Anything that touches money waits for you to type "do it", unless you choose autopilot, and even then it stays inside the limits you gave it in the&nbsp;interview.

## How it is different

We looked at the three closest tools on GitHub before building this. One audits your account, one connects Claude to Meta, one watches a campaign and moves budget. None of them does the strategy, makes the ads and runs the account in one place, with each week's results feeding the next round. Checked against each repo on 4 November&nbsp;2026.

| | Reads the account | Changes the account | Makes new video ads | Runs on a schedule |
|---|---|---|---|---|
| [claude-ads](https://github.com/AgriciDaniel/claude-ads) | Yes | No, it drafts changes | No | No |
| [pipeboard meta-ads-mcp](https://github.com/pipeboard-co/meta-ads-mcp) | Yes | Yes | No | No, it is the connector |
| [meta-ads-kit](https://github.com/TheMattBerman/meta-ads-kit) | Yes | Pauses and budgets | No, it writes copy for images you supply | Yes |
| claude-media-buyer | Yes | Yes, after you say "do it" | Yes, with the engine in this folder | Yes, twice a day |

The engine makes motion graphics on Remotion, acted scenes with people who talk
on Kling and Seedance, and animated characters on Seedance through&nbsp;Replicate.

We did not rebuild what claude-ads does well. Its Meta audit, 72 controls from the
pixel to policy, ships inside this repo under its MIT license, and the weekly review
runs it on your&nbsp;account.

## If you already run ads

Before it builds anything, Claude takes stock of every campaign already running:
what each one optimizes for, how it is structured, what it costs against your
target, whether its ads are tiring, and how much their audiences overlap. The
takeover rules in `ads/rules.py` then say, per campaign, adopt it and manage it
as it is (rebuilding resets what Meta learned), refresh its creative, restructure
it into one clean campaign, or leave it alone and build new alongside. You pick.
The check-in, the alert and the weekly review then run on whatever you&nbsp;chose.

## Your budget, your rules

Nothing is preset. The interview asks which budget policy you&nbsp;want:

| Policy | What Claude does |
|---|---|
| Fixed | Spends a set amount over set dates, then stops. Meta enforces the total as a spend cap. If you are beating your target, it asks whether to raise the&nbsp;total. |
| Scale while it works | Always on. Raises the daily budget while each of the last few days beats your target, up to a daily ceiling you set, then asks before going&nbsp;higher. |
| Steady | Always on at the same daily budget. Only cuts when results get&nbsp;worse. |

You also set how big one change may be, how many good days come first, a daily
budget above which every raise waits for your yes, and how much one ad may spend
with no result before it is paused. These rules run as code
(`ads/rules.py`, with tests), not as text Claude could misread. Autopilot is never
on by default: before it can be, Claude spells out in your own numbers what it
will do alone and the worst day in dollars, and you type a sentence to accept it.
Until that line and the Meta safety rules exist, autopilot behaves like
approval&nbsp;mode. A spend cap goes into Meta itself for every policy (the total, or 31 days of the
ceiling or the daily budget); for an always-on policy the check-in extends it by a
month when 90% is spent, on its own in autopilot and on your word otherwise. With autopilot or an always-on budget, two safety rules
go in as well, so they work while your Mac is off: pause any ad that spends your pause multiple of the target (3 by default) with no result,
and alert you when the campaign's cost runs 50% over&nbsp;target.

## What it will not do on its own

- Launch the campaign before you type "turn it&nbsp;on".
- Spend credits on a new video before you say yes to the cost, or in autopilot, past your daily&nbsp;limit.
- Change targeting or the ad set. The folder's settings deny 60 connector tools and make the build-time ones (a new campaign, a new ad set, a new Meta rule, a video from a link) ask first, so an unattended run cannot reach&nbsp;them.
- Act on a reply meant for an older report: every "do it" carries the report's time, and a bare "do it" gets a question&nbsp;back.
- Pause the last two running ads in the ad set, even in autopilot. It recommends it instead. Meta's own rule has no such floor, so the next check-in flags an ad set left with fewer than two live ads before anything&nbsp;else.
- Change a budget in any way `ads/rules.py` did not return, or go past your
  total, your ceiling or your ask-first&nbsp;line.

## Status

Not yet run end to end on a live campaign. Ruben is running it first: $10,000
on US free subscribers for How to AI, $1,000 a day for 10 days. We will post his results here when the campaign ends, good or&nbsp;bad.

## Pipeboard or Meta's own connector

This engine talks to Meta through [Pipeboard](https://pipeboard.co) today. Meta now
has its own free connector for Claude that signs in with your own Meta login, and
it can do almost the whole job: build campaigns, ad sets and ads, change budgets
and the spend cap, pause, switch on and read&nbsp;results.

| | Pipeboard | Meta's connector |
|---|---|---|
| Cost | Paid plan | Free |
| Upload a video from your Mac | Yes, directly | Only from a public link or a file you pick by&nbsp;hand |
| Changes go live | Directly | Can be saved as drafts that need a publish&nbsp;step |
| Extra tools | Bulk ads, duplicates, Drive and Dropbox import, rules | The core set |
| One login for many ad accounts | Yes, built for teams and&nbsp;agencies | Each person signs in to their&nbsp;own |

For one person running their own account, Meta's connector is the simpler
choice, and the only gap is the video upload: an autopilot video has to be put
at a public link before Meta can take it. Support for Meta's connector is not in
this engine yet; the prompts in `ads/` are written for Pipeboard's tool&nbsp;names.

## What you need

| What | Why | Where |
|---|---|---|
| A Pipeboard account (ads) | the connection to your Meta ad account | https://pipeboard.co |
| A video provider (new videos only) | fal, Replicate or Higgsfield. Prices work differently, so pick what suits you. This engine's voice and lip-sync scripts call fal; its stills and generated footage call&nbsp;Replicate. | fal.ai, replicate.com, higgsfield.ai |
| A Google AI key (optional) | Gemini voices, watching videos, Nano Banana images | https://aistudio.google.com/apikey |
| A Kling account (acted scenes) | dialogue video, added to Claude as a connector | Claude walks you through it |
| ffmpeg | every render | needs your Mac password once, Claude gives you the command |
| Node.js 18+ | motion graphics | https://nodejs.org |

To run ads you need only the first row. The rest are for making new videos.
Say "how complete is my setup?" any time: Claude scores what is connected and
says what each missing piece costs&nbsp;you.

Keys go in `.env` (Claude creates it from `.env.example`). Never paste a key
into a chat. Each person uses their own&nbsp;accounts.

`python3 scripts/doctor.py` checks all of it and names the fix for anything
missing. It never spends&nbsp;money.

## What is in here

| Path | What |
|---|---|
| `CLAUDE.md` | The front door Claude reads first: setup, the first message, and which part does the job. `AGENTS.md` points Codex at the same file. |
| `setup.sh`, `scripts/doctor.py` | Install everything, then check the machine. Claude runs both for you. |
| `ads/` | The ad team: `WORKFLOW.md` (the four stages), `STRATEGY.md`, `PRODUCTION.md`, `BUILD.md` (build and launch), `CHECKIN.md` (the check-in), `ALERT.md`, `WEEKLY.md`, `REPORT.md`, the money rules (`rules.py`) and the stage tracker (`status.py`). |
| `RULES.md` | The craft rulebook. Every rule in it cost a rejected cut to learn. |
| `brands/` | One folder per brand: its guide, its data and its assets. Claude builds yours by interview. `example/` shows a finished one. |
| `motion-graphics/` | The Remotion formats, sample assets and `build.sh`. Its `scripts/` holds the Remotion helpers; the shared voice, music and read checks live in the root `scripts/`. |
| `toolbox/` | General tools: page and UI captures, redaction, document sweeps, keystroke demos, typed text over a clip, a shot-list composer with a presenter cutout, a safe-zone check, motion and still runners, vocal separation. |
| `docs/` | How each format, the voice and music, generation, naming and delivery work, and `95-madlibs-templates.md`, how to port a proven ad's structure. |
| `CINEMATIC.md` | The acted-scene pipeline: four stages, gates, and its failure log. |
| `examples/animated-characters/` | A worked cartoon two-hander: character sheets, approved voices, prompt blocks and scripts. The method is `docs/65-format-animated-characters.md`. |
| `lib/` | The acted-scene spec (`director.md`), tones, camera library and the stage-by-stage checklist. |
| `guide/` | Reference prompts, images and camera sheets for acted scenes. |
| `scripts/` | Voice, lip-sync, matting, read checks, widow checks, validation, assembly, grade, music. |
| `.claude/skills/` | Skills Claude uses here: the brand interview, watch a video, pull competitor ads, download a reference video, images, copy cleanup, and the Meta audit (`ads-meta`, from claude-ads). |
| `.claude/agents/` | The video reviewer: a second Claude that checks every render against the brand's checklist. |
| `.claude/commands/` | `/content-strategist` and `/content-editor`, used before and after writing ad copy. |
| `assets/` | The cover image for this page. |
| `tests/` | The self-test the setup check runs. Every case is a bug that happened. |
| `projects/` | Your working files, one folder per film. Not shared. |

## Words used here

- **Stages**: setup, strategy, production, buying (`ads/WORKFLOW.md`). **BUILD / CHECKIN**: the campaign-building prompt and the twice-daily check-in prompt in `ads/`.
- **Approval mode / autopilot**: every change waits for "do it", or Claude acts alone inside limits.
- **Doctor**: the setup check, `scripts/doctor.py`.
- **RSVP**: a format that shows one word at a time in time with the voice.
- **Acted scene**: a short film with generated people who talk. **Two-hander**: a scene with two characters.
- **Stage gates**: points in the acted-scene process where you approve before Claude spends money.

## Credits and licenses

`.claude/skills/stop-slop` (Hardik Pandya) and `.claude/skills/humanizer`
(Siqi Chen) are MIT and keep their own LICENSE files. `.claude/skills/banana`
is from AgriciDaniel/claude-banana (MIT). `.claude/skills/competitive-ads-extractor` and `.claude/skills/video-downloader`
are from ComposioHQ/awesome-claude-skills (Apache&nbsp;2.0). `.claude/skills/ads-meta` is the
Meta audit skill and its reference files from AgriciDaniel/claude-ads v2.1.0 (MIT); its
`NOTICE.md` lists the five lines we&nbsp;changed.

## Limits

Claude cannot watch motion or hear audio, so whether an ad looks right and
sounds like a person stays with you. A green check means no rule was broken. It
never means the ad is&nbsp;good.