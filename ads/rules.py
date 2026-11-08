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
    "overlaps": [ {"a": "1", "b": "2", "pct": 42} or {"a": "1", "b": "3", "shared": ["Free subscribers list"]} ]
  }
and prints one outcome per live campaign (adopt, refresh, restructure, leave), the
account-level call (manage an existing campaign, or build new), and overlap warnings.

The check-in writes ads/today.json from Pipeboard first:
  {
    "date": "2026-11-12",                    # today, in the ad account's time zone
    "current_daily_budget": 1000,
    "spend_to_date": 3000,
    "daily": [ {"date": "2026-11-11", "spend": 1000, "results": 640, "value": 0}, ... the 7 full days before today, oldest first ],
    "ads": [ {"id": "1", "name": "...", "status": "ACTIVE", "spend_7d": 340, "results_7d": 0, "value_7d": 0, "days_running": 5,
              "frequency_7d": 2.1, "ctr_7d": 1.4, "ctr_first_3d": 1.9}, ... ],
    "meta_rules_live": ["120255000000001"],     # the Meta rule ids that still exist, from get_ad_rules
    "spend_cap": 31000, "spend_lifetime": 27800  # the campaign's Meta spend cap (a lifetime cap) and its spend since it began
  }
  spend_to_date runs from start_date through yesterday. Insights spend is whole currency units
  as Meta returns it; only budgets and caps from campaign reads are minor units. "value" is the
  purchase value under result_action_type and matters only when the plan has target_roas.

It prints JSON: what to pause, the one budget change (already capped), which ads
are tiring (refresh), the mode (autopilot only when autopilot_accepted is the date plus
the quoted sentence and meta_rule_ids holds Meta rule ids), credit_limit (the day's
video cap; none or 0 means no video), what autopilot may still do today, the questions
to ask the operator, and why. Amounts are whole currency units (today.json too); the
check-in converts with currency_offset when it talks to Pipeboard. Claude writes the
copy and the ideas; it only makes the changes this script returns. The check-in
appends one JSON line to ads/actions.jsonl ({"date","kind": budget|copy|video|pause})
before every Pipeboard write, so an attempted change counts as today's change.
Every limit comes from the interview, stored in ads/CAMPAIGN.md (pause_multiplier, default 3:
how many times the target cost one ad may spend with no result before it is paused).
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent


def num(v, default=None):
    try:
        f = float(str(v).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return default
    return f if f == f and abs(f) != float("inf") else default


ENUM_KEYS = ("budget_policy", "mode", "autopilot_video", "takeover", "lead_source")
MONEY_KEYS = ("target_cost_per_result", "daily_budget", "total_budget", "daily_ceiling", "autopilot_credit_limit_per_day")


def read_plan(p):
    """ads/CAMPAIGN.md as a dict. A key written twice is an error: the last one would win silently."""
    plan, seen, dups = {}, set(), []
    for line in p.read_text().splitlines():
        m = re.match(r"\s*([a-z_]+):\s*(.*)$", line)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k in seen:
                dups.append(k)
            seen.add(k)
            plan[k] = v.lower() if k in ENUM_KEYS else v
    if dups:
        raise ValueError(f"ads/CAMPAIGN.md repeats {', '.join(sorted(set(dups)))}; keep one line per field")
    return plan


def log_today(p, date, actions=None):
    """Count today's budget changes, copy variants and videos from ads/LOG.md and ads/actions.jsonl.
    An attempted write counts: the check-in appends to actions.jsonl before it calls Pipeboard."""
    counts = {"budget": 0, "copy": 0, "video": 0}
    if p.exists():
        for b in re.split(r"(?m)^## ", p.read_text()):
            if not b.startswith(date):
                continue
            head = b.splitlines()[0].lower()
            body = b.lower()
            if "budget" in head or (("changed" in head or "approved" in head) and re.search(r"daily[ _]?budget[^\n]*(->|to [$€£¥₩₹0-9])", body)):
                counts["budget"] += 1
            kind = re.sub(r"^\S+\s+(\d{1,2}:\d{2}\s+)?", "", head)
            if kind.startswith("built"):
                if "copy" in kind or ("video" not in kind and "copy variant" in body):
                    counts["copy"] += 1
                elif "video" in kind or "video" in body:
                    counts["video"] += 1
    if actions and actions.exists():
        for line in actions.read_text().splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if not isinstance(j, dict):
                continue
            if str(j.get("date", ""))[:10] == str(date)[:10] and j.get("kind") in counts:
                counts[j["kind"]] += 1
    return counts


def money(plan):
    """Format amounts in the account's currency; offset 1 means no minor units (JPY, KRW)."""
    cur = (plan.get("currency") or "USD").strip().upper()
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "KRW": "₩", "INR": "₹"}.get(cur, cur + " ")
    dec = 0 if num(plan.get("currency_offset"), 100) == 1 else 2
    def f(v):
        return "none" if v is None else f"{sym}{v:,.{dec}f}"
    return f


def decide(plan, today, logc):
    out = {"pauses": [], "budget": None, "refresh": [], "ask": [], "notes": [], "mode": "approval", "credit_limit": 0,
           "pause_campaign": False, "cap_to": None, "autopilot_today": {"copy_variant": False, "video": False, "budget_change": False}}
    fmt = money(plan)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(today.get("date", ""))):
        raise ValueError(f"today.json date must be YYYY-MM-DD, got {today.get('date')!r}")
    policy = (plan.get("budget_policy") or "fixed").strip().lower()
    for k in MONEY_KEYS:
        raw = (plan.get(k) or "").strip().lower()
        if raw and raw not in ("none", "never", "no") and num(raw) is None:
            out["notes"].append(f"{k} '{plan.get(k)}' is not a number; treated as none")
    if (plan.get("mode") or "").strip().lower() == "autopilot":
        acc = plan.get("autopilot_accepted", "").strip().lower()
        accepted = bool(re.match(r'^\d{4}-\d{2}-\d{2},?\s*"i accept the autopilot risk"$', acc))
        ids = re.findall(r"\d{12,}", plan.get("meta_rule_ids", ""))
        rules_ok = bool(ids) and bool(re.fullmatch(r"\s*\d{12,}(\s*,\s*\d{12,})*\s*", plan.get("meta_rule_ids", "")))
        live = today.get("meta_rules_live")
        if rules_ok and isinstance(live, list) and not all(i in [str(x) for x in live] for i in ids):
            rules_ok = False
            out["notes"].append("a Meta safety rule named in meta_rule_ids is gone from the account")
        if accepted and rules_ok:
            out["mode"] = "autopilot"
        else:
            out["notes"].append("autopilot not active: " + ("autopilot_accepted must be the date and the quoted sentence, nothing else" if not accepted
                                else "meta_rule_ids holds no live Meta rule ids") + "; acting as approval mode")
    raw_target = num(plan.get("target_cost_per_result"))
    target = raw_target if raw_target and raw_target > 0 else None
    if raw_target is not None and target is None:
        out["notes"].append("target_cost_per_result must be above zero; treated as none")
    step = num(plan.get("scale_step_pct"), 20) or 20
    if not (0 < step <= 50):
        out["notes"].append(f"scale_step_pct {step:g} is outside 1 to 50; using 20")
        step = 20
    step = step / 100
    after = max(1, int(num(plan.get("scale_after_days"), 3) or 3))
    ceiling = num(plan.get("daily_ceiling"))
    ceiling = ceiling if ceiling and ceiling > 0 else None
    raw_ask = (plan.get("ask_above_daily") or "").strip().lower()
    if raw_ask in ("", "never", "none"):
        ask_above = None
    else:
        ask_above = num(raw_ask)
        if ask_above is None:
            ask_above = 0.0
            out["notes"].append(f"ask_above_daily '{raw_ask}' is not a number; every raise asks first")
    total = num(plan.get("total_budget"))
    total = total if total and total > 0 else None
    total_missing = policy == "fixed" and total is None
    if total_missing:
        out["notes"].append("fixed policy with no readable total_budget: no raises until it is set")
    limit = num(plan.get("autopilot_credit_limit_per_day")) or 0
    out["credit_limit"] = limit
    date = today["date"]
    budget = num(today.get("current_daily_budget"), 0) or 0
    spent = num(today.get("spend_to_date"))
    spent_missing = spent is None
    spent = spent or 0
    daily = sorted([d for d in today.get("daily", []) if str(d.get("date", "")) < date], key=lambda d: str(d.get("date", "")))  # today is a partial day and never counts
    ads = [a for a in today.get("ads", []) if a.get("status", "ACTIVE") == "ACTIVE"]
    from datetime import date as D
    end = (plan.get("end_date") or "none").strip()
    end_ok = None
    if end not in ("", "none"):
        try:
            D.fromisoformat(end); end_ok = end
        except ValueError:
            out["notes"].append(f"end_date '{end}' is not YYYY-MM-DD; fix ads/CAMPAIGN.md")

    def finish():
        allowed = out["mode"] == "autopilot"
        out["autopilot_today"] = {"copy_variant": allowed and logc["copy"] < 1,
                                  "video": allowed and logc["video"] < 1 and limit > 0,
                                  "budget_change": allowed and logc["budget"] < 1 and out["budget"] is not None}
        return out

    # a fixed campaign that is over: report only
    if policy == "fixed" and end_ok and date > end_ok:
        out["pause_campaign"] = True
        out["ask"].append(f"The end date ({end_ok}) has passed. Pause the campaign if it is still running: reply 'pause the campaign'.")
        out["notes"].append("past end_date: no budget changes; the only change is pausing the campaign")
        return finish()
    if policy == "fixed" and total and spent_missing:
        out["notes"].append("spend_to_date is missing from today.json; no budget change until the check-in reads it")
    if policy == "fixed" and total and not spent_missing and spent >= total:
        out["pause_campaign"] = True
        out["ask"].append(f"Total reached: {fmt(spent)} of {fmt(total)} spent. The campaign is paused (autopilot) or should be: reply 'pause the campaign'.")
        out["notes"].append("total reached: no budget change")
        return finish()

    # 0. the Meta spend cap is a lifetime cap; a campaign must not run into it unseen
    plan_daily = num(plan.get("daily_budget"))
    units_ok = not (plan_daily and budget and not (0.5 * plan_daily <= budget <= 2 * plan_daily))
    cap = num(today.get("spend_cap"))
    cap = cap if cap and cap > 0 else None
    life = num(today.get("spend_lifetime"))
    if cap and life is not None:
        month = 31 * (ceiling if (policy == "scale" and ceiling) else budget)
        if life > 1.5 * (cap + (spent if policy == "fixed" else 0)) or cap > 3 * (life + max(month, 1)):
            out["notes"].append(f"spend_cap {fmt(cap)} and spend_lifetime {fmt(life)} do not fit together, a units mix-up; the cap is left alone this run")
        elif not units_ok:
            out["notes"].append("the budget units look wrong, so the Meta spend cap is left alone this run")
        elif policy in ("scale", "steady") and life >= 0.9 * cap:
            if month <= 0:
                out["ask"].append(f"{fmt(life)} of the {fmt(cap)} Meta spend cap is spent and no daily budget was read; reply 'raise cap to <amount>'.")
            else:
                out["cap_to"] = round(min(life, cap) + month)
                state = "is reached, so the campaign is stopped" if life >= cap else "is nearly spent"
                out["ask"].append(f"The Meta spend cap ({fmt(cap)}) {state}: {fmt(life)} spent since the campaign began. Autopilot extends it by a month of budget; otherwise reply 'raise cap to {out['cap_to']:,.0f}'.")
        elif policy == "fixed" and total and not spent_missing and life >= cap and spent < total:
            out["cap_to"] = round(life - spent + total)
            out["ask"].append(f"The Meta spend cap ({fmt(cap)}) is reached before the total ({fmt(spent)} of {fmt(total)} spent in this campaign), because the cap counts spend from before adoption. Autopilot moves it to {out['cap_to']:,.0f}; otherwise reply 'raise cap to {out['cap_to']:,.0f}'.")

    # 1. pauses
    tot_spend = sum(num(a.get("spend_7d"), 0) or 0 for a in ads)
    tot_res = sum(num(a.get("results_7d"), 0) or 0 for a in ads)
    avg = tot_spend / tot_res if tot_res else None
    mult = num(plan.get("pause_multiplier"), 3) or 3
    if mult <= 0:
        out["notes"].append(f"pause_multiplier {mult:g} must be above zero; using 3")
        mult = 3
    bleed = mult * target if target else (mult * budget / max(len(ads), 1))
    share = budget / max(len(ads), 1)
    if target and ads and budget and budget * 7 / len(ads) < bleed:
        out["notes"].append(f"with {len(ads)} ads sharing {fmt(budget)} a day, no ad can reach the {fmt(bleed)} pause line in 7 days; lower pause_multiplier or run fewer ads")
    week_spend = sum(num(d.get("spend"), 0) or 0 for d in daily)
    tiny = False
    if daily and week_spend and tot_spend > 2 * week_spend:
        out["notes"].append(f"the ads' 7-day spend ({fmt(tot_spend)}) is more than twice the campaign's ({fmt(week_spend)}); a units mix-up, so no pauses this run")
        ads = []
    elif daily and budget and tot_res > 0 and 0 < tot_spend < 0.02 * budget * 7:
        tiny = True
        out["notes"].append(f"the ads' 7-day spend ({fmt(tot_spend)}) is under 2% of a week's budget while results exist; insights spend is already in whole units, so it looks divided by 100; no changes this run")
        ads = []
    for a in ads:
        s, r = num(a.get("spend_7d"), 0) or 0, num(a.get("results_7d"), 0) or 0
        running = num(a.get("days_running"), 99)
        if r == 0 and bleed > 0 and budget > 0 and s > bleed and running >= 3 and s >= share:
            out["pauses"].append({"id": a["id"], "name": a.get("name"), "why": f"{fmt(s)} spent, no results in 7 days"})
        elif r >= 10 and target and s / r > 2 * target:
            out["pauses"].append({"id": a["id"], "name": a.get("name"), "why": f"{fmt(s / r)} per result, over twice the {fmt(target)} target"})
        elif r >= 10 and not target and avg and s / r > 2 * avg:
            out["pauses"].append({"id": a["id"], "name": a.get("name"), "why": f"{fmt(s / r)} per result, over twice the {fmt(avg)} average"})
    if len(ads) - len(out["pauses"]) < 2 and out["pauses"]:
        out["pauses"] = out["pauses"][: max(0, len(ads) - 2)]
        out["notes"].append("kept the last two active ads running")

    # 2. one budget change
    # A lone day with spend and no results, while the other days convert, is most often a
    # tracking gap; it is left out of the cost math once and the operator is asked to check.
    if len(daily) >= 3:
        res = [num(r.get("results"), 0) or 0 for r in daily]
        gaps = []
        for i, r in enumerate(daily):
            others = [x for j, x in enumerate(res) if j != i]
            if res[i] == 0 and (num(r.get("spend"), 0) or 0) > 0 and others and sum(others) / len(others) >= 10:
                if not (i >= len(daily) - 2 and res[-1] == 0 and res[-2] == 0):
                    gaps.append(r)
        if len(gaps) == 1:
            g = gaps[0]; avg_r = sum(res) / max(1, len(res) - 1)
            daily = [r for r in daily if r is not g]
            out["notes"].append(f"{g.get('date')} spent {fmt(num(g.get('spend'), 0))} with 0 results while the other days averaged {avg_r:,.0f}; treated as a tracking gap and left out of the cost math")
            out["ask"].append(f"Check your own count for {g.get('date')}: Meta shows 0 results on {fmt(num(g.get('spend'), 0))} of spend. Reply with the real number if it differs.")

    def cpr(rows):
        s = sum(num(r.get("spend"), 0) or 0 for r in rows); n = sum(num(r.get("results"), 0) or 0 for r in rows)
        return s / n if n else (float("inf") if s > 0 else None)
    recent = daily[-after:]
    enough = len(daily) >= after
    troas = num(plan.get("target_roas"))
    use_roas = bool(troas and troas > 0 and daily and all("value" in r for r in daily))
    if use_roas:
        recent_ok = len(recent) == after and all(
            (num(r.get("spend"), 0) or 0) > 0 and (num(r.get("value"), 0) or 0) / (num(r.get("spend"), 0) or 1) >= troas for r in recent)
        wv, ws = sum(num(r.get("value"), 0) or 0 for r in daily), sum(num(r.get("spend"), 0) or 0 for r in daily)
        week_roas = wv / ws if ws else None
    else:
        recent_ok = bool(target) and len(recent) == after and all(
            (num(r.get("spend"), 0) or 0) > 0 and (num(r.get("results"), 0) or 0) > 0
            and (num(r.get("spend"), 0) or 0) / (num(r.get("results"), 0) or 1) < target for r in recent)
        week_roas = None
    week = cpr(daily) if daily else None
    new, why = None, None
    if not daily:
        out["notes"].append("no full days of numbers yet; no budget change")
    elif policy == "fixed" and total and spent_missing:
        pass
    elif not units_ok:
        out["notes"].append(f"the account's daily budget ({fmt(budget)}) is far from daily_budget in ads/CAMPAIGN.md ({fmt(plan_daily)}); a units mix-up? no budget change until that is fixed")
    elif logc["budget"] >= 1:
        out["notes"].append("budget already changed today")
    elif tiny:
        pass
    elif policy == "scale" and ceiling and budget > ceiling:
        new, why = ceiling, "above the daily ceiling"
    elif not enough:
        out["notes"].append(f"only {len(daily)} full day(s) of numbers; cost-based changes wait for {after}")
    elif use_roas and week_roas is not None and week_roas < troas / 1.5:
        new, why = budget * (1 - step), f"7-day ROAS {week_roas:.2f} vs {troas:.2f} target"
    elif not use_roas and target and week and week > 1.5 * target:
        if week == float("inf"):
            new, why = budget * (1 - step), "spend with no results in 7 days"
            out["ask"].append("No results in 7 days of spend. Pause the campaign? Reply 'pause the campaign'.")
        else:
            new, why = budget * (1 - step), f"7-day cost per result {fmt(week)} vs {fmt(target)} target"
    elif recent_ok and policy == "scale" and not ceiling:
        out["ask"].append("Beating the target, but ads/CAMPAIGN.md has no daily_ceiling, so no raise. Reply 'set ceiling to <amount>'.")
    elif recent_ok and total_missing:
        out["ask"].append("Beating the target, but total_budget is missing or unreadable, so no raise. Reply 'raise total to <amount>' to set it.")
    elif recent_ok and policy in ("fixed", "scale"):
        new, why = budget * (1 + step), (f"last {after} days each at or above {troas:.2f} ROAS" if use_roas else f"last {after} days each under the {fmt(target)} target")
    if policy == "fixed" and total and units_ok and daily and logc["budget"] < 1 and not tiny and not spent_missing:
        if end_ok:
            days_left = max(1, (D.fromisoformat(end_ok) - D.fromisoformat(date)).days + 1)
            cap = max(0.0, (total - spent) / days_left)
            if new and new > cap:
                new, why = cap, (why or "") + "; capped so the total lands on the end date"
                if recent_ok:
                    out["ask"].append(f"Beating the target at the total. Raise the total above {fmt(total)}? Reply 'raise total to <amount>'.")
            elif not new and budget > cap * 1.05 and cap > 0:
                new, why = cap, "lands the total on the end date"
        else:
            remaining = total - spent
            if new and new > budget and new > remaining:
                new = None
                out["ask"].append(f"Only {fmt(remaining)} of the total is left and there is no end date; set one or raise the total before any raise.")
    if policy == "scale" and ceiling and new and new > ceiling:
        if budget >= ceiling:
            new = None
            out["ask"].append(f"At the {fmt(ceiling)} a day ceiling and beating the target. Raise it? Reply 'raise ceiling to <amount>'.")
        else:
            new, why = ceiling, (why or "") + "; stops at the ceiling"
    if new is not None and new <= 0:
        new = None
        out["ask"].append("The rules would set the budget to zero. Pause the campaign instead? Reply 'pause the campaign'.")
    if new is not None and abs(new - budget) >= 1:
        b = {"from": round(budget, 2), "to": round(new, 2), "why": why, "needs_approval": False}
        if ask_above is not None and new > budget and new > ask_above:
            b["needs_approval"] = True
            out["ask"].append(f"Raise the daily budget to {fmt(new)}? That is above your {fmt(ask_above)} ask-first line.")
        out["budget"] = b

    # 3. tiring ads: frequency up and CTR down a third since launch
    for a in ads:
        fq, c7, c3 = num(a.get("frequency_7d")), num(a.get("ctr_7d")), num(a.get("ctr_first_3d"))
        if fq and c7 is not None and c3 and fq > 3 and c7 < 0.7 * c3:
            out["refresh"].append({"id": a["id"], "name": a.get("name"),
                                   "why": f"frequency {fq:.1f}, CTR {c7:.2f}% vs {c3:.2f}% in its first 3 days"})
    return finish()


def takeover(t):
    """What to do with each live campaign, by the rules a buyer taking over an account uses."""
    want = (t.get("wanted_event") or "").upper()
    target = num(t.get("target_cost_per_result"))
    target = target if target and target > 0 else None
    fmt = money(t)
    out = {"campaigns": [], "account": None, "warnings": []}
    if not want:
        out["warnings"].append("no wanted_event: ask the operator for the goal and the event before judging the live campaigns")
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
            o, why = "refresh", f"{fmt(spend)} spent, no results in 7 days; the creative is the problem"
        elif target and cost is not None and cost > 1.2 * target:
            o, why = "refresh", f"{fmt(cost)} per result against the {fmt(target)} target; new creative into the existing ad set first"
        elif tiring:
            o, why = "refresh", f"frequency {fq:.1f} and CTR {c7:.2f}% vs {cp:.2f}% the week before"
        elif str(c.get("learning") or "").lower() in ("limited", "fail"):
            o, why = "refresh", "learning limited; it needs results it is not getting"
        else:
            o, why = "adopt", (f"{fmt(cost)} per result" if cost is not None else "running") + ("" if not target else f" against the {fmt(target)} target") + "; keep it and manage it as it is"
        out["campaigns"].append({"id": c.get("id"), "name": c.get("name"), "outcome": o, "why": why,
                                 "cost_7d": round(cost, 2) if cost is not None else None})
    live = [x for x in out["campaigns"] if x["outcome"] in ("adopt", "refresh", "restructure")]
    if not out["campaigns"]:
        out["account"] = {"call": "new", "why": "nothing is running"}
    elif not live:
        out["account"] = {"call": "new", "why": "the live campaigns do a different job; build new alongside and leave them"}
    else:
        best = sorted(live, key=lambda x: ("adopt", "refresh", "restructure").index(x["outcome"]))[0]
        same = [x["id"] for x in live if x["outcome"] == best["outcome"]]
        out["account"] = {"call": best["outcome"], "campaign_id": best["id"], "campaign_ids": same,
                          "why": f"{best['name']}: {best['why']}" + (f"; {len(same)} campaigns get this call" if len(same) > 1 else "")}
    for o in t.get("overlaps", []):
        shared = o.get("shared") or []
        if num(o.get("pct"), 0) >= 30 or shared:
            what = (f"share {num(o.get('pct')):.0f}% of their audience" if num(o.get("pct"), 0)
                    else "target the same saved audiences (" + ", ".join(str(s) for s in shared[:3]) + ")")
            out["warnings"].append(f"campaigns {o.get('a')} and {o.get('b')} {what}; running both bids against yourself, so exclude one audience from the other or pause one")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--takeover", action="store_true", help="what to do with the live campaigns (reads ads/takeover.json)")
    ap.add_argument("--plan", default=str(HERE / "CAMPAIGN.md"))
    ap.add_argument("--today", default=str(HERE / "today.json"))
    ap.add_argument("--log", default=str(HERE / "LOG.md"))
    ap.add_argument("--actions", default=str(HERE / "actions.jsonl"))
    a = ap.parse_args()
    if a.takeover:
        print(json.dumps(takeover(json.loads((HERE / "takeover.json").read_text())), indent=2)); return
    pp = pathlib.Path(a.plan)
    if not pp.exists():
        print(json.dumps({"error": f"{pp} is missing; build the campaign first (ads/BUILD.md)"})); sys.exit(2)
    tp = pathlib.Path(a.today)
    if not tp.exists():
        import datetime
        tp.write_text(json.dumps({"date": datetime.date.today().isoformat(), "daily": [], "ads": [], "note": "no numbers read yet"}))
    ids = [l for l in pp.read_text().splitlines() if re.match(r"\s*campaign_id:\s*\S", l)]
    if len(ids) != 1:
        print(json.dumps({"error": f"ads/CAMPAIGN.md has {len(ids)} campaign_id lines; this folder runs exactly one campaign"})); sys.exit(2)
    try:
        plan = read_plan(pp)
        today = json.loads(pathlib.Path(a.today).read_text())
        print(json.dumps(decide(plan, today, log_today(pathlib.Path(a.log), today["date"], pathlib.Path(a.actions))), indent=2))
    except (ValueError, KeyError, OSError) as e:
        print(json.dumps({"error": str(e)})); sys.exit(2)


if __name__ == "__main__":
    main()
