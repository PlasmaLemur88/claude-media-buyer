# The workflow: one ad team, four stages

This folder runs a Meta ad account the way an ad team does. A creative strategist
finds the angles and writes the briefs. A production team makes the ads. A media
buyer builds, launches, watches and scales the campaign. Each week the buyer's
analysis goes back to the strategist, and the next round starts from what was
learned. Claude plays all three roles. The operator approves.

`python3 ads/status.py` says where a campaign is by reading which files exist, for
example "Stage 4 of 4, Buying. Step 4 of 9: Launch check." Every session in this
folder opens with that line once the operator has asked to run ads, and "run my
ads" or "continue" picks up at the current step. Nothing is preset: every number,
limit and choice comes from the operator in stages 2 and 4.

| Stage | Replaces | Files | Leaves behind |
|---|---|---|---|
| 1 Setup | the account manager | `SETUP.md`; `SLACK-CHANNEL.txt` names the Slack channel, empty for none | the Pipeboard connection, `brands/<slug>/` with a guide and a checklist, optional: video provider, Slack, Drive |
| 2 Strategy | the creative strategist | `STRATEGY.md` | `BRIEF.md`, `RESEARCH.md`, `ANGLES.md`, `TEST-PLAN.md`, `briefs/<NNN>-<slug>.md` |
| 3 Production | the production team | `PRODUCTION.md` | each brief marked delivered with its files, `DELIVERED.md` |
| 4 Buying | the media buyer | `BUILD.md` to launch; then `CHECKIN.md` twice a day, `ALERT.md` three times a day (reads only), `WEEKLY.md` once a week, `REPORT.md` at the end; `rules.py` is the money rules as code, with tests | `takeover.json`, `checks/`, `CAMPAIGN.md`, `LOG.md`, `LEARNINGS.md`, `REPORT-<date>.md` |

`status.py` reads which of those files exist and prints the stage and step. What a
stage leaves behind is one campaign's state and is gitignored.

## The steps

Stage 1, Setup (`SETUP.md`)
1. Connect Meta through Pipeboard.
2. Brand guide and checklist (the brand interview, once per brand).
3. Optional: a video provider, Slack, Google Drive. Each can be skipped; `status.py` says what you give up.

Stage 2, Strategy (`STRATEGY.md`)
1. Brief: what is promoted, the result that counts, who buys, the offer, the destination, the target cost. One round of questions.
2. Research: the account's own winners, competitor ads, the customer's words, the category. Every line cites its source.
3. Angles: 8 to 12 hypotheses, at least 3 that the current winners do not cover.
4. Test plan: which angles go first, variants per angle, the metric, spend per test before a call, one variable per test. The operator approves angles and plan with "approved".
5. Briefs: one file per concept, enough for production to work from without asking.

Stage 3, Production (`PRODUCTION.md`)
1. Script per brief (approved in approval mode).
2. Build: the format the brief names. Three hook versions per concept and one static.
3. Review: the review pack and the video-reviewer agent, until PASS.
4. Deliver: named files, thumbnails, copy sheets, `DELIVERED.md`. A first round may reuse the account's proven ads instead; then `DELIVERED.md` lists their ids.

Stage 4, Buying (`BUILD.md` to launch, then the schedules)
1. Take stock: every campaign already running, read and judged by the takeover rules in `rules.py`: adopt it, refresh its creative, restructure it, or leave it and build new alongside. The operator picks. Written to `checks/takeover.md`.
2. Tracking check: the pixel fired in the last day, the event counted this week, the destination answers. Written to `checks/tracking.md`.
3. Build the campaign, paused (or adopt the live one): budget policy, dates, audience, exclusions, the delivered ads as the first ads. Approval mode or autopilot is chosen here.
4. Launch check: every placement previewed, the link with its tags answered, the copy read against Meta's standards. Written to `checks/launch.md`.
5. Turn on, the Meta safety rules, and "set up the team": the check-in, the alert, the weekly review and (fixed budgets) the final report, as scheduled tasks.
6. Monitor and optimize twice a day (`CHECKIN.md`): delivery problems, cost against target, pauses and the one budget change from `rules.py`, tiring ads, the next upload or build from the queue. The alert (`ALERT.md`) watches spend between runs.
7. Weekly (`WEEKLY.md`): reconcile Meta's count against the real one, audit the account with the `ads-meta` skill, analyze by element, write `LEARNINGS.md`, update the angles, write the next round's briefs. Production then builds them (one a day in autopilot, on "make them" in approval mode).
8. Report (`REPORT.md`): the full record and a one-page version, at the end of a fixed campaign or on request; the end-of-campaign report also removes the scheduled runs, and "new campaign" archives the state and starts the next one from the strategist.

## Handoffs

- Strategy to production: `briefs/<NNN>-<slug>.md`, status `briefed`.
- Production to buying: the same file, status `delivered`, with its paths, plus `DELIVERED.md`.
- Buying to strategy: `LEARNINGS.md`, which `STRATEGY.md` reads first on every round after the first.
- Every stage reads `BRIEF.md` and the brand's `BRAND-GUIDE.md` and `CHECKLIST.md`; no stage re-asks what they hold.

## Two modes

Approval, the default: each stage stops where the steps above say "approved", every change after launch waits for the operator to type "do it" with the report's time, and a new round waits for "approved" typed in any chat.

Autopilot: chosen in the build interview (stage 4, step 3). It stays off until two lines exist in `CAMPAIGN.md`: the operator's typed acceptance from `BUILD.md` Step 4b ("I accept the autopilot risk") and the ids of the two Meta safety rules; `rules.py` checks both before it reports mode autopilot. Then, after "turn it on", the check-in and the weekly review run on their own inside the limits in `CHECKIN.md` STEP 7 and the autopilot exception at the end of `RULES.md`: pauses and the one budget change the rules return, one copy variant a day, the next queued brief built one a day within the credit limit, and new videos held for the operator's look unless they chose "launch". "Autopilot off" in any chat ends it.

Rules that hold here as everywhere in the engine: Claude shows the script before it builds, asks before it spends credits, never activates an ad the operator did not name, and never sets a budget `rules.py` did not return.
