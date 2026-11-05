#!/usr/bin/env python3
"""Measure what a still frame cannot show, before the operator spends attention.

    python3 scripts/watch_take.py take.mp4
    python3 scripts/watch_take.py take.mp4 --strip out.jpg   # also write a dense contact strip

Exit code is the number of defects found.

WHY THIS EXISTS
The most expensive failure in this project's history: a session judged clips
from a handful of stills, called them good, and the operator rejected every
one. Stills cannot show a held pose, a stall, an unwanted cut, or a soft frame.
ffmpeg can measure all four. None of it needs a person.

WHAT IT STILL CANNOT DO
Decide whether the performance is believable, or whether the read sounds like a
person. Those stay with the operator, and no measurement replaces them. A clean
run here means "no measurable defect", never "this take is good".
"""
import argparse
import json
import re
import subprocess
import sys


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", *args, "-f", "null", "-"],
                          capture_output=True, text=True).stderr


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True).stdout
    d = json.loads(out or "{}")
    s = (d.get("streams") or [{}])[0]
    num, den = (s.get("r_frame_rate") or "0/1").split("/")
    return {"w": s.get("width"), "h": s.get("height"),
            "frames": int(s.get("nb_frames") or 0),
            "fps": round(float(num) / float(den or 1), 2) if float(den or 0) else 0,
            "dur": round(float((d.get("format") or {}).get("duration") or 0), 2)}


def static_runs(path, dur, thresh=0.012):
    """Spans where consecutive frames barely change - a held pose inside a clip
    that is supposed to be moving. This is the one that caught DOOR_BURST_v5:
    a third of a three second 'burst' was the same braced position."""
    # gte, not gt: gt drops every zero-score frame, which is precisely the
    # static ones this is looking for. That bug made the detector always silent.
    err = ff(["-i", path, "-vf", "select='gte(scene,0)',metadata=print"])
    scores = [float(m) for m in re.findall(r"lavfi\.scene_score=([0-9.]+)", err)]
    if not scores:
        return [], scores
    n = len(scores)
    per = dur / n if n else 0
    runs, start = [], None
    for i, s in enumerate(scores):
        if s < thresh:
            start = i if start is None else start
        else:
            if start is not None and (i - start) * per >= 0.5:
                runs.append((round(start * per, 2), round(i * per, 2)))
            start = None
    if start is not None and (n - start) * per >= 0.5:
        runs.append((round(start * per, 2), round(n * per, 2)))
    return runs, scores


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--strip", help="write a dense contact strip here")
    ap.add_argument("--static-max", type=float, default=0.33,
                    help="fail if a single held pose covers more than this share of the clip")
    ap.add_argument("--shots", type=int, default=1,
                    help="how many shots this generation is supposed to contain. "
                         "A Kling multi-shot generation legitimately has cuts inside it.")
    ap.add_argument("--kind", choices=["action", "dialogue"], default="dialogue",
                    help="action shots must actually move; dialogue shots are expected to be still")
    a = ap.parse_args(argv[1:])

    import os
    if not os.path.exists(a.path):
        print(f"  FAIL  {a.path} does not exist")
        return 1
    if os.path.getsize(a.path) < 1024:
        print(f"  FAIL  {a.path} is {os.path.getsize(a.path)} bytes - not a video")
        return 1
    p = probe(a.path)
    if not p["frames"] or not p["dur"]:
        print(f"  FAIL  {a.path} has no decodable video stream")
        return 1
    print(f"{a.path}")
    print(f"  {p['w']}x{p['h']}  {p['fps']}fps  {p['frames']} frames  {p['dur']}s")

    fails = []

    # A frozen span. Kling and Seedance both stall occasionally.
    fz = ff(["-i", a.path, "-vf", "freezedetect=n=-60dB:d=0.4"])
    for m in re.finditer(r"freeze_start: ([0-9.]+)", fz):
        fails.append(f"frozen from {float(m.group(1)):.2f}s - the clip stalls")

    # A scene cut inside what should be one continuous shot.
    sc = ff(["-i", a.path, "-vf", "scdet=threshold=14"])
    cuts = [float(m) for m in re.findall(r"lavfi\.scd\.time: ([0-9.]+)", sc)]
    expected = max(a.shots - 1, 0)
    if cuts:
        print(f"  cuts at {', '.join(f'{c:.2f}s' for c in cuts)} "
              f"({len(cuts)} found, {expected} expected for {a.shots} shot(s))")
    if len(cuts) > expected:
        fails.append(f"{len(cuts)} cut(s) inside a generation declared as {a.shots} shot(s) - "
                     f"pass --shots N if this is a multi-shot generation, otherwise the model "
                     f"cut where it should not have")

    # Held pose - measured, not eyeballed.
    runs, scores = static_runs(a.path, p["dur"])
    if runs:
        longest = max(runs, key=lambda r: r[1] - r[0])
        span = longest[1] - longest[0]
        share = span / p["dur"] if p["dur"] else 0
        line = (f"held pose {longest[0]:.2f}s-{longest[1]:.2f}s "
                f"({span:.2f}s, {share*100:.0f}% of the clip)")
        if share > a.static_max and a.kind == "action":
            fails.append(line + " - too much of a shot planned as ACTION is a still")
        else:
            note = "  ok" if a.kind == "dialogue" else "  ok"
            print(f"  {line}{note}"
                  f"{'  (expected on a dialogue shot)' if a.kind == 'dialogue' else ''}")
    if scores:
        avg = sum(scores) / len(scores)
        print(f"  mean frame-to-frame change: {avg:.4f}  "
              f"({'very little movement' if avg < 0.02 else 'moving'})")
        # Calibrated on real rejections: DOOR_BURST_v4 (0.0174) and v5 (0.0108)
        # were both turned down on physics, and both sit under 0.02. A shot the
        # plan calls action should not measure like a portrait.
        if a.kind == "action" and avg < 0.02:
            fails.append(
                f"mean frame-to-frame change is {avg:.4f} on a shot planned as ACTION. "
                f"Both door-burst takes rejected on physics measured below 0.02. "
                f"This one is barely moving.")

    # Soft frames.
    bl = ff(["-i", a.path, "-vf", "blurdetect=low=0.1:high=0.9,metadata=print"])
    blurs = [float(m) for m in re.findall(r"lavfi\.blur=([0-9.]+)", bl)]
    if blurs:
        mean_blur = sum(blurs) / len(blurs)
        # Calibration on real material: a shipped ad reads 5.5, real reference
        # footage 8.5, Kling output 8-10. There is no clean line between usable
        # and unusable, so this reports rather than gates. Only catastrophic
        # softness fails.
        print(f"  blur: mean {mean_blur:.1f} (reference material sits 5-10; not a gate)")
        if mean_blur > 20:
            fails.append(f"blur mean {mean_blur:.1f} is far outside anything measured here - "
                         f"the take is likely out of focus")
    else:
        print("  blur: not measured")

    # The last half second, where models morph.
    if p["dur"] > 1:
        tail = ff(["-ss", str(round(p["dur"] - 0.5, 2)), "-i", a.path,
                   "-vf", "select='gte(scene,0)',metadata=print"])
        ts = [float(m) for m in re.findall(r"lavfi\.scene_score=([0-9.]+)", tail)]
        if ts and max(ts) > 0.35:
            fails.append(f"large change in the final 0.5s (peak {max(ts):.2f}) - check the tail for a morph")

    if a.strip:
        step = max(p["dur"] / 24, 0.04)
        subprocess.run(["ffmpeg", "-v", "error", "-i", a.path,
                        "-vf", f"fps=1/{step:.4f},scale=220:-1,tile=6x4",
                        "-frames:v", "1", "-y", a.strip], check=False)
        print(f"  wrote contact strip: {a.strip}")

    print()
    for f in fails:
        print(f"  FAIL  {f}")
    if not fails:
        print("  PASS  no measurable defect.")
    print(f"\n{len(fails)} measurable defect(s). Believability and the read still need the operator.")
    return len(fails)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
