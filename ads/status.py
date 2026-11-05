#!/usr/bin/env python3
"""Where is this campaign? Reads which files exist and prints the stage and step.

    python3 ads/status.py            # the full list, with what each missing piece costs
    python3 ads/status.py --short    # one line, for the top of a session or a report

Stages and steps come from ads/WORKFLOW.md. Nothing is hand-edited: a step is
done when the file it leaves behind exists (and says PASS or approved where that
matters), or when its scheduled task exists. Optional extras are listed apart,
each with what you give up by skipping it.
"""
import argparse, json, pathlib, re, sys


def read(p):
    try:
        return p.read_text()
    except OSError:
        return ""


def plan(ads):
    out = {}
    for line in read(ads / "CAMPAIGN.md").splitlines():
        m = re.match(r"\s*([a-z_]+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def guard_ok(root, cfg_text):
    """The deny list is in place and the Pipeboard server carries the name it is keyed to."""
    try:
        deny = json.loads(read(root / ".claude" / "settings.json") or "{}").get("permissions", {}).get("deny", [])
    except json.JSONDecodeError:
        return False
    try:
        servers = json.loads(cfg_text or "{}").get("mcpServers", {})
    except json.JSONDecodeError:
        servers = {}
    return "mcp__pipeboard__update_adset" in deny and "mcp__pipeboard__create_adset" not in [d for d in deny if False] and "pipeboard" in servers


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--short", action="store_true")
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument("--cfg", default=str(pathlib.Path.home() / ".claude.json"))
    ap.add_argument("--tasks", default=str(pathlib.Path.home() / ".claude" / "scheduled-tasks"))
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests; defaults to this machine's date")
    a = ap.parse_args()
    root = pathlib.Path(a.root); ads = root / "ads"
    p = plan(ads)
    cfg = read(pathlib.Path(a.cfg))
    env = read(root / ".env")
    has = lambda k: re.search(rf"(?m)^{k}=\S", env) is not None
    cur = read(root / ".current_brand").strip()
    try:
        bj = json.loads(read(root / "brands" / cur / "brand.json") or "{}") if cur else {}
    except json.JSONDecodeError:
        bj = {}
    log = read(ads / "LOG.md")
    first = lambda f: read(ads / f).strip().splitlines()[0].strip() if read(ads / f).strip() else ""
    passed = lambda f: first(f).upper().startswith("PASS")

    def task(name):
        for f in pathlib.Path(a.tasks).glob("*/SKILL.md"):
            t = read(f)
            if name in t and str(root) in t:
                return True
        return False

    briefs = list((ads / "briefs").glob("*.md")) if (ads / "briefs").exists() else []
    delivered = [l for l in read(ads / "DELIVERED.md").splitlines() if l.strip() and not l.startswith("#")]
    fixed = p.get("budget_policy", "fixed").lower() == "fixed"
    auto = p.get("mode", "").lower() == "autopilot"
    always_on = p.get("budget_policy", "").lower() in ("scale", "steady")

    stages = [
        ("Setup", [
            ("Meta connected (Pipeboard)", "pipeboard" in cfg.lower() or bool(p) or passed("checks/tracking.md")),
            ("Brand guide and checklist", bool(cur) and (root / "brands" / cur / "CHECKLIST.md").exists()),
            ("Write guard (the Pipeboard deny list in .claude/settings.json, server named pipeboard)", guard_ok(root, read(pathlib.Path(a.cfg)))),
        ]),
        ("Strategy", [
            ("Brief", (ads / "BRIEF.md").exists()),
            ("Research", (ads / "RESEARCH.md").exists()),
            ("Angles", (ads / "ANGLES.md").exists()),
            ("Test plan approved", "approved: yes" in read(ads / "TEST-PLAN.md")),
            ("Briefs written", len(briefs) > 0),
        ]),
        ("Production", [
            ("Ads delivered (or existing ads named)", len(delivered) > 0),
        ]),
        ("Buying", [
            ("Take stock of running campaigns", (ads / "checks" / "takeover.md").exists()),
            ("Tracking check", passed("checks/tracking.md")),
            ("Campaign built or adopted", bool(p.get("campaign_id"))),
            ("Launch check", passed("checks/launch.md")),
            ("Turned on", bool(re.search(r"(?m)^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} Turned on", log))),
            ("Twice-daily check-in scheduled", task("CHECKIN.md")),
            ("Spend alert scheduled", task("ALERT.md")),
            ("Weekly review scheduled", task("WEEKLY.md")),
        ] + ([("Final report scheduled", task("REPORT.md"))] if fixed else [])),
    ]
    extras = [
        ("Video provider (fal, Replicate or Higgsfield)", has("FAL_KEY") or has("REPLICATE_API_TOKEN") or "higgsfield" in cfg.lower(),
         "Claude can brief new ads but not make them"),
        ("Slack updates", bool(read(ads / "SLACK-CHANNEL.txt").strip()), "reports only show up inside Claude Code"),
        ("Files saved to Google Drive", bool(bj.get("brand", {}).get("output_root")), "finished ads stay on this Mac only"),
    ]
    if auto or always_on:
        extras.append(("Meta safety rules", p.get("meta_rule_ids", "none") not in ("", "none"),
                       "dead ads keep spending while your Mac is off"))
    if auto:
        extras.append(("Autopilot risk accepted in writing", bool(re.match(r'^\d{4}-\d{2}-\d{2}[^"]*"i accept the autopilot risk"$', p.get("autopilot_accepted", "").strip().lower())),
                       "autopilot acts as approval mode until you accept it"))

    import datetime
    today = a.today or datetime.date.today().isoformat()
    end = p.get("end_date", "none")
    reports = sorted(ads.glob("REPORT-*.md"))
    ended = fixed and bool(p.get("campaign_id")) and bool(re.match(r"\d{4}-\d{2}-\d{2}$", end)) and today > end
    if ended:
        line = f"Campaign ended ({end}); report {'written' if reports else 'due'}. Say 'new campaign' to start another."
        if a.short:
            print(line); return
        print(line); return
    total_stages = len(stages)
    for si, (sname, steps) in enumerate(stages):
        for ti, (tname, done) in enumerate(steps):
            if not done:
                line = f"Stage {si + 1} of {total_stages}, {sname}. Step {ti + 1} of {len(steps)}: {tname}."
                break
        else:
            continue
        break
    else:
        line = f"All {total_stages} stages done; the campaign is running. Round {p.get('round', '1')}."
    if a.short:
        print(line); return
    print(line + "\n")
    for si, (sname, steps) in enumerate(stages):
        print(f"Stage {si + 1}: {sname}")
        for tname, done in steps:
            print(f"  {'done' if done else 'todo'}  {tname}")
    print("\nOptional (skip any; this is what you give up)")
    for n, d, why in extras:
        print(f"  {'done' if d else 'skip'}  {n}" + ("" if d else f": without it, {why}."))


if __name__ == "__main__":
    main()
