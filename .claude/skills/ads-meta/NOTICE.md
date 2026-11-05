# Where this skill comes from

`SKILL.md` and the files in `references/` are the Meta slice of
[claude-ads](https://github.com/AgriciDaniel/claude-ads) by Daniel Agrici, release
v2.1.0 (commit fc3908e786c3, 17 October 2026), under the MIT license in `LICENSE`.

What is here: the `ads-meta` skill and the thirteen reference files it reads
(`meta-audit.md`, the 72-control catalog, plus the shared measurement, benchmark,
creative, automation, budget, policy and scoring references).

What is not here: the cross-platform `ads` conductor skill, the other 32 platform
skills, the audit agents, the Python scripts and their dependencies. This engine
runs the audit inside its weekly review (`ads/WEEKLY.md`, W3) instead of through
the conductor.

Lines changed from the original `SKILL.md`, so the skill works without the conductor:

1. Step 1 reads `references/thinking-framework.md` here instead of the conductor's
   operating contract.
2. Step 3 reads `references/meta-audit.md` here instead of `ads/references/`.
3. Steps 7 and 8 write `ads/checks/audit-<date>.md` in plain text instead of
   returning JSON to the conductor, and say that an audit never changes the account.
4. The boundary about the conductor's mutation gate now says the operator's approval
   in the chat is the gate.
5. The Output section describes the plain-text file instead of the JSON contracts.

The reference files are unchanged. `thinking-framework.md` still mentions
`ads/SKILL.md` and `/ads` commands, which belong to the conductor and are not in
this engine.
