#!/usr/bin/env python3
"""Tests for ads/rules.py. Run: python3 tests/test_ads_rules.py (exit 0 = all pass)."""
import importlib.util, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rules", ROOT / "ads" / "rules.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
NOLOG = {"budget": 0, "copy": 0, "video": 0}
fails = 0
run = 0

def check(name, cond):
    global fails, run
    run += 1
    print(("  ok   " if cond else "  FAIL ") + name)
    fails += 0 if cond else 1

def days(spend, results, n=7):
    return [{"date": f"2026-11-{5+i:02d}", "spend": spend, "results": results} for i in range(n)]

def ads(*rows):
    return [{"id": str(i), "name": f"ad{i}", "status": "ACTIVE", "spend_7d": s, "results_7d": r, "days_running": 5}
            for i, (s, r) in enumerate(rows)]

base = {"date": "2026-11-12", "current_daily_budget": 1000, "spend_to_date": 3000}

# a bleeder is paused, a healthy ad is not
p = {"budget_policy": "scale", "target_cost_per_result": "1.50", "daily_ceiling": "3000"}
o = R.decide(p, dict(base, daily=days(1000, 700), ads=ads((400, 0), (3000, 2000), (2000, 1500))), NOLOG)
check("bleeder paused", [x["id"] for x in o["pauses"]] == ["0"])

# never pauses the last two ads
o = R.decide(p, dict(base, daily=days(1000, 700), ads=ads((400, 0), (500, 0))), NOLOG)
check("keeps last two ads", o["pauses"] == [])

# scale: three good days raise by 20%
o = R.decide(p, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("scale raises 20%", o["budget"] and o["budget"]["to"] == 1200)

# scale: stops at the ceiling, then asks
o = R.decide(p, dict(base, current_daily_budget=2800, daily=days(2800, 2400), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("scale stops at ceiling", o["budget"] and o["budget"]["to"] == 3000)
o = R.decide(p, dict(base, current_daily_budget=3000, daily=days(3000, 2600), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("at ceiling asks", o["budget"] is None and any("ceiling" in q for q in o["ask"]))

# cost too high cuts by 20%
o = R.decide(p, dict(base, daily=days(1000, 300), ads=ads((3000, 1000), (2000, 600))), NOLOG)
check("high cost cuts 20%", o["budget"] and o["budget"]["to"] == 800)

# one budget change a day
o = R.decide(p, dict(base, daily=days(1000, 300), ads=ads((3000, 1000), (2000, 600))), {"budget": 1, "copy": 0, "video": 0})
check("one change a day", o["budget"] is None)

# fixed: a raise is capped so the total lands on the end date, and asks to raise the total
f = {"budget_policy": "fixed", "target_cost_per_result": "1.50", "total_budget": "10000", "end_date": "2026-11-18"}
o = R.decide(f, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("fixed raise capped at the pace that lands the total", o["budget"] is None)
check("fixed asks to raise total", any("total" in q for q in o["ask"]))

# fixed: past the end date, no changes
o = R.decide(f, dict(base, date="2026-11-20", daily=days(1000, 300), ads=ads((400, 0), (3000, 2000), (2000, 1500))), NOLOG)
check("past end date: no changes", o["pauses"] == [] and o["budget"] is None)

# steady: never raises
s = {"budget_policy": "steady", "target_cost_per_result": "1.50"}
o = R.decide(s, dict(base, daily=days(1000, 900), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("steady never raises", o["budget"] is None)

# ask-first line
a = dict(p, ask_above_daily="1100")
o = R.decide(a, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("ask above line needs approval", o["budget"] and o["budget"]["needs_approval"])

# tiring ad flagged for refresh
tired = ads((3000, 2000), (2000, 1500)); tired[0].update(frequency_7d=3.6, ctr_7d=0.9, ctr_first_3d=1.6)
o = R.decide(p, dict(base, daily=days(1000, 800), ads=tired), NOLOG)
check("tiring ad marked refresh", [x["id"] for x in o["refresh"]] == ["0"])

# autopilot needs the written acceptance and the Meta safety rules
au = dict(p, mode="autopilot")
o = R.decide(au, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("autopilot without acceptance acts as approval", o["mode"] == "approval" and not any(o["autopilot_today"].values()))
au2 = dict(au, autopilot_accepted='2026-11-05, "I accept the autopilot risk"', meta_rule_ids="none")
o = R.decide(au2, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("autopilot without Meta rules acts as approval", o["mode"] == "approval")
au3 = dict(au2, meta_rule_ids="111, 222")
o = R.decide(au3, dict(base, daily=days(1000, 800), ads=ads((3000, 2000), (2000, 1500))), NOLOG)
check("autopilot with both is on", o["mode"] == "autopilot" and o["autopilot_today"]["video"])

# take stock: what to do with live campaigns
def camp(**k):
    d = {"id": "c1", "name": "live", "event": "COMPLETE_REGISTRATION", "budget_level": "campaign", "n_adsets": 1,
         "lifetime_budget": False, "spend_7d": 7000, "results_7d": 5000, "frequency_7d": 2.0, "ctr_7d": 1.4, "ctr_prev_7d": 1.5, "learning": "success"}
    d.update(k); return d
T0 = {"wanted_event": "COMPLETE_REGISTRATION", "target_cost_per_result": 1.5}
o = R.takeover(dict(T0, campaigns=[camp()]))
check("on-target CBO campaign: adopt", o["campaigns"][0]["outcome"] == "adopt" and o["account"]["call"] == "adopt")
o = R.takeover(dict(T0, campaigns=[camp(spend_7d=7000, results_7d=3000)]))
check("over target: refresh", o["campaigns"][0]["outcome"] == "refresh")
o = R.takeover(dict(T0, campaigns=[camp(frequency_7d=3.8, ctr_7d=0.9, ctr_prev_7d=1.6)]))
check("tiring: refresh", o["campaigns"][0]["outcome"] == "refresh")
o = R.takeover(dict(T0, campaigns=[camp(budget_level="adset", n_adsets=8)]))
check("ad-set budgets and 8 ad sets: restructure", o["campaigns"][0]["outcome"] == "restructure")
o = R.takeover(dict(T0, campaigns=[camp(event="PURCHASE")]))
check("different event: leave, account new", o["campaigns"][0]["outcome"] == "leave" and o["account"]["call"] == "new")
o = R.takeover(dict(T0, campaigns=[]))
check("empty account: new", o["account"]["call"] == "new")
o = R.takeover(dict(T0, campaigns=[camp(), camp(id="c2", name="two", event="PURCHASE")], overlaps=[{"a": "c1", "b": "c2", "pct": 45}]))
check("overlap over 30% warns", len(o["warnings"]) == 1 and o["account"]["campaign_id"] == "c1")

print(f"\n  {run - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
