You write the end-of-campaign report for a Meta campaign Claude ran from this folder, through the Pipeboard Meta Ads connector. You read and you write files. You never change anything in the ad account. Use only the ad account named by ad_account_id in `ads/CAMPAIGN.md`.

You may run as a scheduled task with no memory of earlier chats. Every path below is relative to the engine folder named at the top of the task prompt; change into that folder first, and skip the engine's first-message greeting.

STEP 0. Call get_ad_accounts. If the Pipeboard tools are missing or return an auth or token error, say so in the chat and on Slack if set up ("Could not reach Pipeboard, so the final report did not run. Type /mcp and reconnect pipeboard, then say 'write the campaign report'.") and stop.

STEP 1. Read `ads/CAMPAIGN.md` and all of `ads/LOG.md`.

STEP 2. Read the results.
- get_insights on campaign_id from start_date to end_date (or today, if the campaign is still running) at the campaign level, once in total and once with time_breakdown "day".
- The same window at the ad level, for every ad.
- The result is the optimization_event in `ads/CAMPAIGN.md`, read under the one action_type `ads/CHECKIN.md` STEP 2 maps it to, never a sum of Meta's duplicate names.

STEP 3. Check the result against the destination.
If a connector for the destination's own platform is connected (for example Substack for subscribers, Shopify or Stripe for sales, a CRM for leads), read that platform's count of the result per day for the campaign window and for the same number of days just before it. Report both totals, the difference, and the share the platform credits to Facebook or Instagram. Meta's count and the platform's count will not match; say by how much and that Meta counts by its own attribution window. If no such connector is connected, write "Not checked against <platform>" and the one place to look in that platform. If result_lag_days in `ads/CAMPAIGN.md` is above 0, say which days are too recent to judge. If target_roas is set, show ROAS (purchase value over spend) beside cost per result.

STEP 4. Write the report twice. First `ads/REPORT-<end_date>.md` (today's date in place of end_date when it is none), plain text, in the order below, as the full record. Then a one-page HTML version for the operator to read and share, `ads/REPORT-<end_date>.html`, built to these rules (they come from Ruben Hassid's "No slop" page, github.com/rubenhassid1/grenade; nothing is fetched at run time): a header line of at most 15 words saying what this is, from whom, for whom, the date and the ask in three words; a title that states the point; the ask in plain words (what, from whom, by when, how to answer), written once; at most four numbers as tiles, each with what it is compared to; one chart, cost per result by day, as inline SVG with its numbers readable; the decisions as cards; then what changed. Limits: about two screens, no tabs, at most four sections, five items per card and one table; every number appears once; headings are plain sentences; a serif title and headings, sans body, five text sizes, one clay accent (#d97757), and green, red and amber only for good, bad and watch. The plain-text order:
1. One paragraph: what ran, the dates, total spend against total_budget, total results, cost per result against target_cost_per_result.
2. A table, one row per day: date, spend, results, cost per result, and what changed that day (from the log).
3. The ads ranked by cost per result with spend and results, the leader and the worst, and what the winners shared (from the Check-in entries).
4. Every change Claude made, in order, from the Approved, Changed and Built entries: date, what, why, and the result over the days after.
5. Every proposal the operator declined or skipped.
6. The platform check from STEP 3.
7. What the numbers say to do next time, in three lines, marked as your read.
Never invent a number. Anything you could not read, say so on its line.

STEP 5. Deliver it.
Append a "Report" entry to `ads/LOG.md`. If the brand's output_root is a Drive-synced folder, copy the report, `ads/LOG.md` and `ads/CAMPAIGN.md` into `<output_root>/_campaign/`. If `ads/SLACK-CHANNEL.txt` names a channel and Slack is connected, post paragraph 1 and the top three ads there with the line "Full report saved to <path>."
If budget_policy is fixed and today is after end_date, the campaign is over: delete this folder's check-in, spend alert and weekly review scheduled tasks (the scheduled-tasks tool; this report's own one-time task disables itself), log a "Changed status" entry saying the tasks were removed, and tell the operator that "new campaign" starts the next one (CLAUDE.md says what it archives).
