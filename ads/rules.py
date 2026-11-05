#!/usr/bin/env python3
"""The money rules for the ads part, as code, so they hold even if a prompt is misread.

    python3 ads/rules.py                       # reads ads/CAMPAIGN.md, ads/today.json, ads/LOG.md
    python3 ads/rules.py --today other.json    # a different numbers file
    python3 ads/rules.py --takeover            # reads ads/takeover.json: what to do with the live campaigns

Take stock (--takeover) reads ads/takeover.json, written by ads/BUILD.md from Pipeboard:
  {
    "wanted_event": "COMPLETE_REGISTRATION", "target_cost_per_result": 1.5,
    "campaigns": [ {"id": "1", "name": "...", "event": "COMPLETE_REGISTRATION", "budget_level": "campaign",
                    "n_adsets": 1, "lifetime_budget": false, "spend_7d": 7000, "results_7d": 4500,
                    "frequency_7d": 2.0, "ctr_7d": 1.3, "ctr_prev_7d": 1.6, "learning": "success"}, ... ],
    "overlaps": [ {"a": "1", "b": "2", "pct": 42} ]
  }
and prints one outcome per live campaign (adopt, refresh, restructure, leave), the
account-level call (manage an existing campaign, or build new), and overlap warnings.

The check-in writes ads/today.json from Pipeboard first:
  {
    "date": "2026-11-12",                    # today, in the ad account's time zone
    "current_daily_budget": 1000,
    "spend_to_date": 3000,
    "daily": [ {"date": "2026-11-11", "spend": 1000, "results": 640}, ... up to 7 days, oldest first ],
    "ads": [ {"id": "1", "name": "...", "status": "ACTIVE", "spend_7d": 340, "results_7d": 0, "days_running": 5,
              "frequency_7d": 2.1, "ctr_7d": 1.4, "ctr_first_3d": 1.9}, ... ]
  }

It prints JSON: what to pause, the one budget change (already capped), which ads
are tiring (refresh), the mode (autopilot only when the operator accepted the risk
in writing and the Meta safety rules exist), what autopilot may still do today, the questions to ask the operator, and why. Claude
writes the copy and the ideas; it only makes the changes this script returns.
Every limit comes from the interview, stored in ads/CAMPAIGN.md.
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent


def num(v, default=None):
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return default


def read_plan(p):
    plan = {}
    for line in p.read_text().splitlines():
        m = re.match(r"\s*([a-z_]+):\s*(.*)$", line)
        if m:
            plan[m.group(1)] = m.group(2).strip()
    return plan


def log_today(p, date):
    """Count today's autopilot actions and budget changes from ads/LOG.md."""
    counts = {"budget": 0, "copy": 0, "video": 0}
    if not p.exists():
        return counts
    blocks = re.split(r"(?m)^## ", p.read_text())
    for b in blocks:
        if not b.startswith(date):
            continue
        head = b.splitlines()[0].lower()
        body = b.lower()
        if "changed" in head and "budget" in body:
            counts["budget"] += 1
        if "built" in head and "autopilot" in body:
            counts["video" if "video" in body else "copy"] += 1
    return counts


def decide(plan, today, logc):
    out = {"pauses": [], "budget": None, "refresh": [], "autopilot_today": {}, "ask": [], "notes": [], "mode": "approval"}
    policy = plan.get("budget_policy", "fixed")
    if plan.get("mode") == "autopilot":
        accepted = "i accept the autopilot risk" in plan.get("autopilot_accepted", "").lower()
        rules_ok = plan.get("meta_rule_ids", "none").strip().lower() not in ("", "none", "no")
        if accepted and rules_ok:
            out["mode"] = "autopilot"
        else:
            out["notes"].append("autopilot not active: " + ("the risk was not accepted in writing" if not accepted else "the Meta safety rules do not exist") + "; acting as approval mode")
    target = num(plan.get("target_cost_per_result"))
    step = num(plan.get("scale_step_pct"), 20) / 100
    after = int(num(plan.get("scale_after_days"), 3))
    ceiling = num(plan.get("daily_ceiling"))
    ask_above = num(plan.get("ask_above_daily"))
    total = num(plan.get("total_budget"))
    end = plan.get("end_date", "none")
    date = today["date"]
    budget = num(today.get("current_daily_budget"), 0)
    spent = num(today.get("spend_to_date"), 0)
    daily = today.get("daily", [])
    ads = [a for a in today.get("ads", []) if a.get("status", "ACTIVE") == "ACTIVE"]

    # past the end date: report only
    if policy == "fixed" and end not in ("", "none") and date > end:
        out["notes"].append("past end_date: report only, no changes")
        return out

    # 1. pauses
    tot_spend = sum(num(a.get("spend_7d"), 0) for a in ads)
    tot_res = sum(num(a.get("results_7d"), 0) for a in ads)
    avg = tot_spend / tot_res if tot_res else None
    bleed = 3 * target if target else (3 * budget / max(len(ads), 1))
    for a in ads:
        s, r = num(a.get("spend_7d"), 0), num(a.get("results_7d"), 0)
        if r == 0 and s > bleed:
            out["pauses"].append({"id": a["id"], "name": a.get("name"), "why": f"${s:,.0f} spent, no results in 7 days"})
        elif r >= 10 and avg and s / r > 2 * avg:
            out["pauses"].append({"id": a["id"], "name": a.get("name"), "why": f"${s/r:,.2f} per result, over twice the ${avg:,.2f} average"})
    keep = len(ads) - len(out["pauses"])
    if keep < 2 and out["pauses"]:
        out["pauses"] = out["pauses"][: max(0, len(ads) - 2)]
        out["notes"].append("kept the last two active ads running")

    # 2. one budget change
    def cpr(rows):
        s = sum(num(r.get("spend"), 0) for r in rows); n = sum(num(r.get("results"), 0) for r in rows)
        return s / n if n else None
    recent = daily[-after:]
    recent_ok = target and len(recent) == after and all((num(r.get("results"), 0) and num(r.get("spend"), 0) / num(r.get("results")) < target) for r in recent)
    week = cpr(daily)
    new, why = None, None
    if logc["budget"] >= 1:
        out["notes"].append("budget already changed today")
    elif target and week and week > 1.5 * target:
        new, why = budget * (1 - step), f"7-day cost per result ${week:,.2f} vs ${target:,.2f} target"
    elif recent_ok and policy in ("fixed", "scale"):
        new, why = budget * (1 + step), f"last {after} days each under the ${target:,.2f} target"
    if policy == "fixed" and total:
        from datetime import date as D
        days_left = max(1, (D.fromisoformat(end) - D.fromisoformat(date)).days + 1) if end not in ("", "none") else None
        if days_left:
            cap = max(0.0, (total - spent) / days_left)
            if new and new > cap:
                new, why = cap, (why or "") + "; capped so the total lands on the end date"
                if recent_ok:
                    out["ask"].append(f"Beating the target at the total. Raise the total above ${total:,.0f}? Reply 'raise total to <amount>'.")
            elif not new and budget > cap * 1.05:
                new, why = cap, "lands the total on the end date"
    if policy == "scale" and ceiling and new and new > ceiling:
        if budget >= ceiling:
            new = None
            out["ask"].append(f"At the ${ceiling:,.0f} a day ceiling and beating the target. Raise it? Reply 'raise ceiling to <amount>'.")
        else:
            new, why = ceiling, (why or "") + "; stops at the ceiling"
    if new is not None and abs(new - budget) >= 1:
        b = {"from": round(budget, 2), "to": round(new, 2), "why": why, "needs_approval": False}
        if ask_above and new > ask_above:
            b["needs_approval"] = True
            out["ask"].append(f"Raise the daily budget to ${new:,.0f}? That is above your ${ask_above:,.0f} ask-first line.")
        out["budget"] = b

    # 3. tiring ads: frequency up and CTR down a third since launch
    out["refresh"] = []
    for a in ads:
        fq, c7, c3 = num(a.get("frequency_7d")), num(a.get("ctr_7d")), num(a.get("ctr_first_3d"))
        if fq and c7 is not None and c3 and fq > 3 and c7 < 0.7 * c3:
            out["refresh"].append({"id": a["id"], "name": a.get("name"),
                                   "why": f"frequency {fq:.1f}, CTR {c7:.2f}% vs {c3:.2f}% in its first 3 days"})

    # 4. what autopilot may still do today
    allowed = out["mode"] == "autopilot"
    out["autopilot_today"] = {"copy_variant": allowed and logc["copy"] < 1, "video": allowed and logc["video"] < 1,
                              "budget_change": allowed and logc["budget"] < 1}
    return out


def takeover(t):
    """What to do with each live campaign, by the rules a buyer taking over an account uses."""
    want = (t.get("wanted_event") or "").upper()
    target = num(t.get("target_cost_per_result"))
    out = {"campaigns": [], "account": None, "warnings": []}
    for c in t.get("campaigns", []):
        ev = (c.get("event") or "").upper()
        spend, res = num(c.get("spend_7d"), 0), num(c.get("results_7d"), 0)
        cost = spend / res if res else None
        fq, c7, cp = num(c.get("frequency_7d")), num(c.get("ctr_7d")), num(c.get("ctr_prev_7d"))
        tiring = bool(fq and c7 is not None and cp and fq > 3 and c7 < 0.7 * cp)
        structure_ok = (c.get("budget_level") == "campaign" and int(num(c.get("n_adsets"), 1)) <= 3
                        and not c.get("lifetime_budget"))
        if ev and want and ev != want:
            o, why = "leave", f"optimizes for {ev}, not {want}; it is a different job"
        elif not structure_ok:
            why = []
            if c.get("budget_level") != "campaign": why.append("ad-set budgets")
            if int(num(c.get("n_adsets"), 1)) > 3: why.append(f"{int(num(c.get('n_adsets'), 1))} ad sets")
            if c.get("lifetime_budget"): why.append("a lifetime budget")
            o, why = "restructure", "structure: " + ", ".join(why) + "; one new campaign with its winning ads, then pause it"
        elif res == 0 and target and spend > 3 * target:
            o, why = "refresh", f"${spend:,.0f} spent, no results in 7 days; the creative is the problem"
        elif target and cost is not None and cost > 1.2 * target:
            o, why = "refresh", f"${cost:,.2f} per result against the ${target:,.2f} target; new creative into the existing ad set first"
        elif tiring:
            o, why = "refresh", f"frequency {fq:.1f} and CTR {c7:.2f}% vs {cp:.2f}% the week before"
        elif c.get("learning") == "limited":
            o, why = "refresh", "learning limited; it needs results it is not getting"
        else:
            o, why = "adopt", (f"${cost:,.2f} per result" if cost is not None else "running") + ("" if not target else f" against the ${target:,.2f} target") + "; keep it and manage it as it is"
        out["campaigns"].append({"id": c.get("id"), "name": c.get("name"), "outcome": o, "why": why,
                                 "cost_7d": round(cost, 2) if cost is not None else None})
    live = [x for x in out["campaigns"] if x["outcome"] in ("adopt", "refresh", "restructure")]
    if not out["campaigns"]:
        out["account"] = {"call": "new", "why": "nothing is running"}
    elif not live:
        out["account"] = {"call": "new", "why": "the live campaigns do a different job; build new alongside and leave them"}
    else:
        best = sorted(live, key=lambda x: ("adopt", "refresh", "restructure").index(x["outcome"]))[0]
        out["account"] = {"call": best["outcome"], "campaign_id": best["id"],
                          "why": f"{best['name']}: {best['why']}"}
    for o in t.get("overlaps", []):
        if num(o.get("pct"), 0) >= 30:
            out["warnings"].append(f"campaigns {o.get('a')} and {o.get('b')} share {num(o.get('pct')):.0f}% of their audience; running both bids against yourself, so exclude one audience from the other or pause one")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--takeover", action="store_true", help="what to do with the live campaigns (reads ads/takeover.json)")
    ap.add_argument("--plan", default=str(HERE / "CAMPAIGN.md"))
    ap.add_argument("--today", default=str(HERE / "today.json"))
    ap.add_argument("--log", default=str(HERE / "LOG.md"))
    a = ap.parse_args()
    if a.takeover:
        print(json.dumps(takeover(json.loads((HERE / "takeover.json").read_text())), indent=2)); return
    plan = read_plan(pathlib.Path(a.plan))
    today = json.loads(pathlib.Path(a.today).read_text())
    print(json.dumps(decide(plan, today, log_today(pathlib.Path(a.log), today["date"])), indent=2))


if __name__ == "__main__":
    main()
