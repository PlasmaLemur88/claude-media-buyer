# Stage 1: Setup

Do these once per Mac. Claude does the parts it can; you do the sign-ins. Then say
"run my ads" and Claude starts stage 2 (`WORKFLOW.md` has the whole path). Say
"how complete is my setup?" any time: `ads/status.py` scores what is connected
and says what each missing piece costs you.

## 1. Meta, through Pipeboard

1. Make an account at https://pipeboard.co, or accept the invite your team sent you.
2. Connect your Meta login there and pick the ONE ad account Claude will use.
3. Open this folder in Claude Code and say: "connect Pipeboard". Claude runs
   `claude mcp add --scope user --transport http pipeboard https://meta-ads.mcp.pipeboard.co/`
   and tells you to type `/mcp` and sign in. A browser window opens. Sign in with
   your Pipeboard login.
4. Start a new chat. Say: "list my Meta ad accounts". Claude names one account.
   If it names more than one, say which one is yours.
5. The first time Claude uses each Pipeboard tool, Claude Code asks for
   permission. Choose "Always allow" every time, so the scheduled runs never stop
   to ask while you are away. If your Claude Code has the /permissions command,
   you can instead allow the whole server once with the rule `mcp__pipeboard`.
6. The folder's `.claude/settings.json` denies every Pipeboard tool the ads part never
   needs (anything that changes targeting or an ad set, deletes, duplicates, or touches
   audiences, rules, catalogs, posts or account slots), so an unattended run cannot call
   them even in Auto mode. It assumes the server is named pipeboard, as the command above
   names it; keep that name.

Meta's own free connector can do most of this job on your own Meta login; this
engine's prompts are written for Pipeboard's tool names, so it is the supported route.

## 2. Your brand

Say "set up my brand". A short interview saves your brand's name, look, voice,
banned words and a file prefix, and writes the checklist every video is reviewed
against. Once per brand; you can have many. Claude picks the brand itself when
exactly one exists besides `example` and `_template` (`python3 scripts/brand.py
use <slug>`), and a brand with no `CHECKLIST.md` gets one from
`brands/_template/CHECKLIST.md` before production. One engine folder runs one brand
and one campaign at a time, and the campaign plan names its brand; someone with five
clients keeps five copies of the folder, each with its own scheduled tasks.

## 3. Optional, skip any of them

- **A video provider**, only to make new videos: fal, Replicate or Higgsfield.
  Their prices work differently (per second, per image, credits), so choose what
  suits you. This engine's own voice and lip-sync scripts call fal, and its stills
  and generated footage call Replicate, so those two cover the most. Higgsfield
  works through its own Claude connector. Keys go in `.env` (see `.env.example`),
  never in the chat. Without one, Claude still writes the briefs; it cannot make
  the videos.
- **Slack**: a copy of every report and alert in a channel. Put the channel name in
  `ads/SLACK-CHANNEL.txt`, turn on Slack in claude.ai (Settings, Connectors), and
  say "post a test message to the Slack channel". Approvals stay in the Claude
  Code chat; a reply in Slack does not reach Claude.
- **Google Drive**: finished ads, the plan, the log and the reports in a folder your
  team sees. Install Google Drive for desktop and sign in, then say "save the ads
  to Google Drive". Claude finds the Drive folder under
  `~/Library/CloudStorage/GoogleDrive-*`, asks which folder to use, creates
  `<that folder>/Claude ads`, links it as `~/claude-ads` (no spaces, because spaces
  break builds), sets the active brand's `brand.output_root` to it in
  `brands/<slug>/brand.json`, re-runs `python3 scripts/brand.py use <slug>`, puts
  one small test file there and asks you to confirm it shows in Drive on the web.

## What it costs

Pipeboard is a paid plan. A video provider bills per video. Meta bills the ads.
Claude asks before it spends credits (except in autopilot, inside the limit you
set) and never changes a budget the money rules did not return.
