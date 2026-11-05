#!/usr/bin/env python3
"""Tests for ads/status.py: the stage and step come from the files that exist."""
import pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
S = ROOT / "ads" / "status.py"
fails = 0

def run(root, cfg, today="2026-11-05"):
    return subprocess.run([sys.executable, str(S), "--short", "--root", str(root), "--cfg", str(cfg),
                           "--tasks", str(root / "no-tasks"), "--today", today], capture_output=True, text=True).stdout.strip()

def check(name, cond):
    global fails
    print(("  ok   " if cond else "  FAIL ") + name); fails += 0 if cond else 1

with tempfile.TemporaryDirectory() as d:
    root = pathlib.Path(d); (root / "ads" / "checks").mkdir(parents=True); (root / "ads" / "briefs").mkdir()
    (root / "brands" / "acme").mkdir(parents=True); cfg = root / "claude.json"; cfg.write_text("{}")
    check("fresh folder starts at setup step 1", run(root, cfg).startswith("Stage 1 of 4, Setup. Step 1 of 3"))
    cfg.write_text('{"mcpServers": {"pipeboard": {}}}')
    check("pipeboard moves to brand", "Step 2 of 3: Brand guide" in run(root, cfg))
    (root / ".current_brand").write_text("acme\n"); (root / "brands" / "acme" / "CHECKLIST.md").write_text("# x\n")
    (root / "brands" / "acme" / "brand.json").write_text('{"brand": {"output_root": ""}}')
    check("brand done moves to the write guard", "Step 3 of 3: Write guard" in run(root, cfg))
    (root / ".claude").mkdir(); (root / ".claude" / "settings.json").write_text('{"permissions": {"deny": ["mcp__pipeboard__update_adset"]}}')
    check("write guard done moves to strategy brief", run(root, cfg).startswith("Stage 2 of 4, Strategy. Step 1 of 5: Brief"))
    for f in ("BRIEF.md", "RESEARCH.md", "ANGLES.md"): (root / "ads" / f).write_text("x\n")
    (root / "ads" / "TEST-PLAN.md").write_text("round 1\n")
    check("unapproved plan is not done", "Step 4 of 5: Test plan approved" in run(root, cfg))
    (root / "ads" / "TEST-PLAN.md").write_text("approved: yes 2026-11-05\n")
    (root / "ads" / "briefs" / "100-first.md").write_text("status: briefed\n")
    check("briefs done moves to production", run(root, cfg).startswith("Stage 3 of 4, Production"))
    (root / "ads" / "DELIVERED.md").write_text("# Delivered\n100 first A1 existing ad 123 2026-11-05\n")
    check("delivered moves to buying take stock", "Step 1 of 9: Take stock" in run(root, cfg))
    (root / "ads" / "checks" / "takeover.md").write_text("new: nothing running\n")
    check("take stock done moves to tracking check", "Step 2 of 9: Tracking check" in run(root, cfg))
    (root / "ads" / "checks" / "tracking.md").write_text("FAIL\npixel silent\n")
    check("a FAIL check is not done", "Tracking check" in run(root, cfg))
    (root / "ads" / "checks" / "tracking.md").write_text("PASS\n")
    (root / "ads" / "CAMPAIGN.md").write_text("campaign_id: 1\nbudget_policy: fixed\nmode: approval\n")
    check("launch check line reads as the docs quote it", run(root, cfg) == "Stage 4 of 4, Buying. Step 4 of 9: Launch check.")
    (root / "ads" / "checks" / "launch.md").write_text("PASS\n"); (root / "ads" / "LOG.md").write_text("## 2026-11-05 10:00 Turned on\n")
    check("turned on moves to scheduling", "Step 6 of 9: Twice-daily check-in scheduled" in run(root, cfg))
    (root / "ads" / "CAMPAIGN.md").write_text("campaign_id: 1\nbudget_policy: scale\nmode: approval\n")
    check("always-on budget has no final report step", "of 8:" in run(root, cfg))
    (root / "ads" / "CAMPAIGN.md").write_text("campaign_id: 1\nbudget_policy: fixed\nend_date: 2026-11-01\nmode: approval\n")
    check("a fixed campaign past its end date reads as ended", run(root, cfg).startswith("Campaign ended (2026-11-01); report due"))
    (root / "ads" / "REPORT-2026-11-01.md").write_text("report\n")
    check("with the report written it says so", "report written" in run(root, cfg))

print(f"\n  {15 - fails} passed, {fails} failed"); sys.exit(1 if fails else 0)
