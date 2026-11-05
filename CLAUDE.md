# claude-media-buyer

Claude loads this automatically. It makes video and still ads in three ways:

- **Motion graphics** (`motion-graphics/`, Remotion): kinetic type, captions over
  footage or artwork, aerial footage with a voiceover, offer and logo cards. No
  actors. Cheap, fast, and most shipped ads are this.
- **Acted scenes** (`CINEMATIC.md`, Kling and Seedance): people who talk and
  move, a scripted film, a parody, a real teammate on camera with lip-sync.
- **Animated characters** (`docs/65-format-animated-characters.md`, Seedance on
  Replicate): an invented cartoon cast who talk, a skit or a series with the same
  characters every episode. Worked example in `examples/animated-characters/`.

All three share one rulebook, one brand file, and one set of voice, lip-sync
and checking tools in `scripts/`.

---

## IF THIS MACHINE IS NOT SET UP, SET IT UP. DO NOT ASK THEM TO.

**The operator is a marketer, not an engineer. They should never open a
terminal.** You have a shell. Use it.

**Scheduled runs skip this section.** A scheduled check-in, alert or report never
runs the doctor or `setup.sh` and never asks for keys. If a key it needs is
missing, it logs that in `ads/LOG.md`, skips the video step and carries on. The
fal and Replicate keys are only needed to make new videos; ads reports and
changes work without them.

Before anything else, run:

```bash
python3 scripts/doctor.py
```

If it reports problems, run `bash setup.sh` yourself and say one line about what
you are doing. It installs the python packages and the Remotion packages,
creates `.env`, and makes the working folders. Then re-run the doctor.

Four things you cannot do for them. Hand each one over plainly:

- **ffmpeg on a Mac** needs Homebrew, which asks for their login password. Never
  type or handle it. Give them the one command, tell them to paste it into
  Terminal (Cmd+Space, type "Terminal") and enter their password, and wait.
- **Node.js**, if missing, is a normal Mac installer from https://nodejs.org.
- **Their API keys** go into `.env`, never into the chat. A key in a chat log is
  a key they have to rotate. `.env.example` says where to get each one and what
  it unlocks. Replicate and fal are needed; Gemini is optional.
- **Kling** is an entry in their Claude config, not a key, and its tools only
  appear in a session started AFTER the entry exists. Warn them about the
  restart before you make the edit, not after.

A missing optional key is not a blocker. Tell them what it unlocks and carry on.

---

## WHERE THE CAMPAIGN IS (ads part)

Once the operator has asked to run ads (anything exists in `ads/` beyond the shipped
files, or `ads/CAMPAIGN.md` exists), start every session by running
`python3 ads/status.py --short` and showing its line, for example "Stage 4 of 4,
Buying. Step 4 of 9: Launch check." Then offer the next step. "Run my ads" and
"continue" mean: do the step that line names, with the prompt `ads/WORKFLOW.md`
maps it to. When the operator asks how complete things are, run
`python3 ads/status.py` and show the full list; the optional pieces say what each
one costs to skip.

## YOUR VERY FIRST MESSAGE (once the doctor is clean)

If `START-HERE.md` exists in this folder (a setup guide someone wrote for this one operator; most copies have none), read it first and follow it instead of this greeting until its steps are done.

Skip this greeting when the session opens with a task: a pasted prompt from `ads/` (BUILD, CHECKIN or ALERT), a scheduled run, or any request that already says what to do. Do the task instead.

Say this in your own words and no longer, then **stop** and wait:

> Tell me what you want to make, even half an idea is fine. Or say "run my ads"
> and I will connect your Meta ad account and run a campaign with you. I can build motion
> graphics (type, captions, footage, offer cards), an acted scene with people
> who talk, or cartoon characters who talk. I write it, build it, check it and hand you the files. You approve
> the script, say yes before I spend credits, and judge how it looks and sounds,
> because I can't watch motion or hear audio.
>
> First, which brand is this for? If it's new, I'll ask you a few questions and
> build a brand guide so every ad comes out in your style.

Run `python3 scripts/brand.py list` before you say it. If the only brand is
`example`, say that the example is there to show how things work and that
their own ads start with their own brand guide.

Do not list files, stages or commands. The operator never needs to know one.

---

## EVERY SESSION, BEFORE ANY WORK

1. **Read `RULES.md` in full.** It is the craft rulebook: every rule in it cost a
   rejected cut to learn. It applies to both halves.
2. **Know the brand.** Every ad is for one brand, and the active one is in
   `brands/<slug>/` (`python3 scripts/brand.py show`). A new brand, or none yet,
   means the `brand-guide` skill runs first: an interview, then
   `brands/<slug>/brand.json`, `BRAND-GUIDE.md` and `assets/`, then a style
   sample the operator approves. Read the active brand's `BRAND-GUIDE.md` in
   full and check every script against it and its `brand.json` before a single
   frame renders. Switch brands with `brand.py use <slug>`; never mix two
   brands' facts in one ad.
3. **Route the job:**
   - Motion graphics → `motion-graphics/` and the format docs in `docs/`
     (`20-format-rsvp.md`, `30-format-captions.md`, `40-format-aerial.md`, and
     any newer format sections). Voice and music: `docs/10-voice-and-music.md`.
   - Acted scene → **read `CINEMATIC.md`, then `lib/director.md` in full**, and
     follow its stage gates. Do not start a film from memory of either file.
   - Animated characters (cartoon, stick figures, a mascot, a recurring cast) →
     **read `docs/65-format-animated-characters.md` in full**, then
     `examples/animated-characters/README.md`. Do not run these shots through
     `scripts/motion.py`: its negative prompt bans cartoons.
   - Captures, documents, website demos, typed text over a clip, a voice-timed
     composition with a presenter cutout, or a safe-zone check on any render →
     `toolbox/README.md` (tools listed by "use it when"). These are building blocks,
     not templates: use the ones the idea needs.
   - A still ad → build it as HTML or PIL, then run the widow check in
     `scripts/` before anyone sees it.

## BRANDS

One person can run many brands. Each lives in `brands/<slug>/` and nothing in
a component or a script holds a brand string, colour or logo. When the operator
corrects an ad ("too corporate", "never that green"), write the rule into that
brand's `BRAND-GUIDE.md` in the same session and tell them you did, so the
correction outlives the conversation.

---

## SPEND

**Never spend a credit without asking.** One exception: in the `ads/` autopilot mode
the operator set a daily credit limit in `ads/CAMPAIGN.md`, and that limit is the yes for the
next queued brief, one a day (see `ads/CHECKIN.md`, STEP 7). State the cost in credits or dollars and
get an explicit yes. Decide the stop-loss before the first paid call. Take one
piece end to end (voice, picture, cut, the operator's ears and eyes) before
generating a batch.

## THE TOOLS

`CINEMATIC.md` has the table for the acted-scene tools (session gate, prompt
validator, take checks, assembly, grade). `scripts/TOOLS.md` lists the
shared voice, lip-sync, matting and checking tools. Every script prints its own
usage with `--help`.

## THE SKILLS IN `.claude/skills/` AND `.claude/commands/`

| Skill | When |
|---|---|
| `brand-guide` | Before the first ad for any brand, and whenever the operator wants to change how a brand looks or sounds. |
| `gemini-video` | Watch any video (a competitor ad, a reference, your own cut) and get a transcript, sections and on-screen text. Needs `GEMINI_API_KEY`. |
| `competitive-ads-extractor` | Pull and read a competitor's ads before porting one. |
| `video-downloader` | Download a reference video. |
| `banana` | Generate or edit a still image with Nano Banana (needs its MCP and a Google AI key). |
| `ads-meta` | The weekly review's account audit: 72 Meta controls (pixel, attribution, creative, structure, placements, automation, policy), from AgriciDaniel/claude-ads. |
| `/content-strategist`, `/content-editor` | Before and after writing any ad script or copy. |
| `stop-slop`, `humanizer` | Strip AI tells from every line a viewer will read or hear. |

---

## TWO JUDGEMENTS THAT ARE NEVER YOURS

**Does it look right in motion? Does the voice sound like a person?** No check
answers either. (The one exception is the autopilot exception at the end of
`RULES.md`, which the operator chooses on purpose.) Report what you can measure (duration, resolution, loudness, the
transcript against the script, widows) and hand the verdict to the operator.
**Never tell them a cut works.** A green check means no rule was broken, never
that the ad is good.

## REVIEW BEFORE ANYTHING SHIPS

Every finished render goes to the `video-reviewer` agent before you hand it over
or upload it. It is a separate chat that did not make the video, reads it through
`scripts/review_pack.py` (contact sheets, transcript, loudness, safe zone) and checks
it against `brands/<slug>/CHECKLIST.md`. Fix everything it fails and send the new
render back to it. Only a PASS ends the loop. After three FAILs in a row, stop and
hand the operator the render with the last verdict, so you never loop forever.

The checklist belongs to the brand. If `brands/<slug>/CHECKLIST.md` does not exist,
write it from `brands/_template/CHECKLIST.md`, `RULES.md` and the brand's
`BRAND-GUIDE.md` before the first review. Whenever the operator corrects a video, add
the correction to that brand's CHECKLIST.md in the same session and say you did.

## DELIVERY

Every finished ad ships as the video (or still) in both ratios, 9:16 and 4:5, a
copy sheet with the primary text, headline and call to action, and a thumbnail,
all under one file stem. `docs/80-naming-and-delivery.md` has the naming
convention. Anything uploaded to an ad account is created PAUSED, except in the `ads/` part when the operator types "turn it on" or "do it", or when an autopilot run acts inside the limits the operator accepted (a copy variant, a launch-mode video).

---

## RUNNING ADS FROM HERE (the `ads/` part)

`ads/WORKFLOW.md` is the spine: four stages that replace a creative strategist, a
production team and a media buyer, with handoffs between them and a weekly
learnings loop, plus the table of which file runs which stage. Read it when the
operator says anything like "run my ads", "set up a campaign", "connect Pipeboard",
"make them" or "weekly review", then run the prompt the current step maps to. Never
skip a stage silently; the operator may skip one on purpose ("build the campaign"
with existing ads skips production). Setup (Pipeboard, the brand, Slack, Google
Drive) is `ads/SETUP.md`: do its steps yourself and hand the operator only the
sign-ins. `ads/LOG.md` is the memory every run appends to.

- **"Set up the team"** (after "turn it on"): first delete any check-in, alert, weekly or
  report task this folder already has, so a second run never doubles them; then create the scheduled tasks, from a chat
  opened in this folder so each task's working folder is this folder and the Pipeboard
  tools and this file load. First ask the operator to switch this chat's permission
  mode to Auto, so the tasks are saved in a mode that will not stop on a permission
  prompt while nobody is watching. Each task's prompt starts with "Change into
  <the absolute path of this folder>, then follow ads/<file> exactly." The tasks:
  the check-in (`CHECKIN.md`) at 09:00 and 18:00 local time; the spend alert
  (`ALERT.md`) at 12:00, 15:00 and 21:00 (each run opens a chat in the sidebar, so not
  hourly); the weekly review (`WEEKLY.md`) at 10:00 on the launch weekday, first run a week after
  launch; and, for a fixed budget, the final report (`REPORT.md`) once, at 09:30 the day
  after end_date (fireAt), which also removes the other three tasks. Run the check-in once right away and show the result, so the first failure
  happens while the operator is watching. Tasks run only while the Claude app is open.
- **"Make them"**: run `ads/PRODUCTION.md` on the briefed queue. **"Weekly review"**:
  run `ads/WEEKLY.md` now. **"Write the campaign report"**: run `ads/REPORT.md` now.
- **Replies to a report, typed in any chat**: "do it <numbers> @<time>", "show <n>",
  "undo <n>", "pause <ad name>", "pause the campaign", "resume the campaign", "raise
  total to <X>", "raise ceiling to <X>", "set ceiling to <X>" and "the cut is good" all
  go through `ads/CHECKIN.md` STEP 6, which reads the newest Check-in entry in
  `ads/LOG.md` first.
- **"Launch it"** typed in any chat: find every "Built video ... waiting for your
  look" entry in `ads/LOG.md` whose files are not yet ads in the campaign, upload them all
  and switch the ads on by `ads/CHECKIN.md` STEP 6, and log a Changed status entry.
- **"Approved"** typed in any chat after a weekly review: change the newest
  `round <N> approved: pending` line in `ads/TEST-PLAN.md` to yes, set `round: <N>` and
  `round_started: <today>` in `ads/CAMPAIGN.md`, log it, and say "make them" starts
  production.
- **"Autopilot off"** typed in any chat: set `mode: approval` in `ads/CAMPAIGN.md`,
  add a Changed status entry to `ads/LOG.md`, and confirm in one line.
- **"Stand down the team"**: delete this folder's check-in, spend alert, weekly review
  and report scheduled tasks, log a Changed status entry, confirm in one line. The final
  report of a fixed campaign does this itself.
- **"New campaign"**: only after "stand down the team" and with the old CLAUDE | campaign
  paused or ended; move everything in `ads/` that one campaign leaves behind (the plan,
  the log, the brief, research, angles, test plan, briefs, checks, DELIVERED.md,
  today.json, takeover.json, actions.jsonl, the reports) into `ads/archive/<campaign
  name>/`, keep `ads/LEARNINGS.md` where it is, then start at `ads/STRATEGY.md` S1, which
  may copy answers from the archived brief.
- Every ad production makes goes through the same gates as any other ad: script
  approval, a yes before credits, the checks, the video-reviewer. The one exception
  is autopilot (end of `RULES.md`, `ads/CHECKIN.md` STEP 7), which builds the next
  queued brief, one a day, with no script approval and no cost question. Slack is a
  copy of the report; approvals only count when the operator types them in the
  Claude Code chat.
