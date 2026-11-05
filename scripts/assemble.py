#!/usr/bin/env python3
"""Assemble a Kling dialogue film - J-cut edition, plus the grade/grain pass.

    python3 assemble.py build                      # the built-in example config
    python3 assemble.py build --config mycut.json   # any other cut
    python3 assemble.py grade in.mp4 out.mp4       # default look, standalone
    python3 assemble.py grade in.mp4 out.mp4 --strong   # for shiny close-ups
    python3 assemble.py grade in.mp4 --compare     # before/after stills pair

Video: concat of trimmed, captioned segments.
Audio: ONE timeline. Each clip's room-treated audio is placed at its segment's
start, but interrupters lead early (J-cut) and every clip keeps a breath tail
(L-cut). A continuous kitchen room-tone bed glues the cuts.

Everything film-specific is in CONFIG below, and every key can be overridden by
a JSON file passed to --config. The built-in values are the ones that actually
rendered out_9x16.mp4 / out_4x5.mp4.
"""
import argparse
import copy
import json
import os
import pathlib
import subprocess
import sys

import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as sig
from PIL import Image, ImageDraw, ImageFont

# =========================================================================
# GRADE AND GRAIN - the realism step, done in code rather than prompts.
#
# Why this exists: AI video is mathematically clean, and clean is the tell. Real
# sensors add grain and real lenses do not deliver sculpted contrast. Knocking
# the contrast and saturation down and laying grain back on is the single
# biggest realism win available in post, and it costs one ffmpeg pass.
#
# A note on the skin fix. Premiere's HSL Secondary lets you eyedropper the shiny
# forehead and pull only that. ffmpeg has no eyedropper, so `--strong` uses
# selectivecolor on reds and yellows, which is where skin highlights live. It is
# blunter than the Premiere move and it is applied to the whole frame, so it is
# worth using only on tight faces where the shine actually reads.
#
# Values are a starting point, tuned by eye against the engine's sample aerials. Grain of
# 6/255 is about 2.4% of full scale (6/255), at the low end of the 3-8% the teardown calls for, because
# Kling output already carries some texture and stacking reads as noise.
# =========================================================================

# Contrast and saturation come DOWN: AI renders both too punchy, which is what
# makes skin look sculpted. gamma_r nudged up warms the midtones a touch, which
# suits the warm, desaturated look the example is written for (warm but desaturated).
BASE_EQ = "eq=contrast=0.94:saturation=0.92:gamma_r=1.01"

# alls = strength, allf=t+u = temporal + uniform, so the grain moves between
# frames like real grain instead of sitting on the image like a static overlay.
BASE_NOISE = "noise=alls=6:allf=t+u"

# Blunt stand-in for an HSL-secondary skin pull: take saturation out of the reds
# and yellows where skin highlights live. Whole-frame, so tight faces only.
SKIN_PULL = "selectivecolor=reds=0 0 0 -0.12:yellows=0 0 0 -0.10"


def chain(strong: bool = False) -> str:
    """Return the -vf filter chain string."""
    parts = [BASE_EQ]
    if strong:
        parts.append(SKIN_PULL)
    parts.append(BASE_NOISE)
    return ",".join(parts)


def grade_run(src: str, dst: str, strong: bool = False, crf: int = 17) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", chain(strong),
           "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "copy", dst]
    subprocess.run(cmd, check=True)
    print(f"graded {src} -> {dst}  ({'strong' if strong else 'base'})")


def grade_compare(src: str, at: float = 1.0) -> None:
    """Write before/after stills so the numbers can be judged by eye."""
    stem = src.rsplit(".", 1)[0]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", src,
                    "-frames:v", "1", "-q:v", "2", f"{stem}_before.jpg"], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", src,
                    "-frames:v", "1", "-vf", chain(), "-q:v", "2",
                    f"{stem}_after.jpg"], check=True)
    print(f"wrote {stem}_before.jpg and {stem}_after.jpg")


# =========================================================================
# CONFIG - the built-in example cut. Override any key with --config file.json.
#
# A cut entry is one segment of the film:
#   clip   basename resolved through paths.clip  (a generated take)
#   still  basename resolved through paths.still (a frozen image insert)
#   in     seek into the source, seconds
#   dur    length on the timeline, seconds
#   lead   start this clip's AUDIO this much EARLY (J-cut, interrupters)
#   tail   keep the audio breathing this much PAST the cut (L-cut)
#   crop   optional ffmpeg crop applied before the scale, for a punch-in
#   caps   [[TEXT, in, out], ...] burned-in captions, times relative to the cut
# =========================================================================
def _active_brand_asset(sub, ends):
    """First file in brands/<active>/assets/<sub>/ ending in one of `ends`, or None."""
    root = pathlib.Path(__file__).resolve().parent.parent
    cur = root / ".current_brand"
    if not cur.exists():
        return None
    d = root / "brands" / cur.read_text().strip() / "assets" / sub
    hits = sorted(p for p in d.glob("*") if p.name.endswith(ends)) if d.is_dir() else []
    return str(hits[0]) if hits else None


CONFIG = {
    "video": {
        "width": 1080, "height": 1920, "fps": 24, "sample_rate": 48000,
        "crf_segment": 18, "crf_master": 17, "preset": "medium",
    },
    "paths": {
        "work": "tmp/example",
        "clip": "gen/{name}.mp4",
        "still": "gen/{name}.jpg",
        # macOS system font. San Francisco carries a Condensed Heavy variation,
        # which is the caption weight. On Linux substitute a condensed grotesk.
        # first of these that exists. macOS SF carries the Condensed Heavy
        # variation the captions use; the others are sane stand-ins.
        "caption_font": next(
            (f for f in ("/System/Library/Fonts/SFNS.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                         "C:/Windows/Fonts/arialbd.ttf")
             if os.path.exists(f)), "/System/Library/Fonts/SFNS.ttf"),
        # the active brand's end-card font and mark (scripts/brand.py use <slug>);
        # override either in your cut config
        "card_font": _active_brand_asset("fonts", (".ttf", ".otf")),
        "card_mark": _active_brand_asset("logos", ("mark.png",)),
    },
    "captions": {
        "size": 78, "min_size": 40, "max_width_frac": 0.92,
        "y_frac": 0.72, "stroke": 6, "weight": "Condensed Heavy",
    },
    "audio": {
        # fade the head and tail of every placed clip so overlaps blend
        # instead of clicking
        "fade_s": 0.12,
        "roomtone_gain": 0.14,
        "roomtone_seed": 9,
        "room_seed": 4,
        "peak_ceiling": 0.97,
        # clips whose picture is used but whose audio must never be placed.
        # s2k is the Kling alternate of the same beat; it was a hardcoded name
        # in the original assembler and is kept here as data.
        "skip_clips": ["s2k"],
    },
    "music": {
        # the engine's composed bed (scripts/bed.py), low, looped, dead stop on the cut stop_index names
        "bed": "motion-graphics/public/audio/bed_phrygian.wav",
        "stop_index": 9,
        "gain": 0.22,
        "fade_s": 0.25,
    },
    "card": {
        "duration": 2.4,
        "bg": [11, 11, 13],
        "title": "Example",   # the brand name; set it in your cut config
        "title_size": 110,
        # Lora's variation is spelled SemiBold; the SF tagline weight below is
        # spelled Semibold. Font-specific, both verified against the shipped
        # files, do not "tidy" them into one spelling.
        "title_variation": "SemiBold",
        "mark_px": 96, "gap_px": 24, "y_frac": 0.44,
        "tag": "YOUR TAGLINE",
        "tag_size": 46, "tag_weight": "Semibold",
        "tag_color": [210, 210, 215], "tag_offset_px": 170,
    },
    "outputs": {
        "master": "out_9x16.mp4",
        "ratios": [
            # 4:5 is cropped from the graded master so both ratios share one grade
            {"file": "out_4x5.mp4", "crop": "crop=1080:1350:0:285", "crf": 18},
        ],
    },
    "grade": {"strong": False},
    "cuts": [
        {"clip": "s1",  "in": 0.0, "dur": 1.8, "lead": 0.0,  "tail": 0.3, "caps": []},
        {"clip": "s2",  "in": 0.0, "dur": 3.0, "lead": 0.2,  "tail": 0.4,
         # single: punch in on him, empty chair leaves frame
         "crop": "crop=756:1344:324:110",
         "caps": [["YOU HAVE NO CFO.", 0.3, 1.6],
                  ["HOW ARE YOU DOING FINANCE?", 1.6, 3.0]]},
        {"clip": "s3",  "in": 0.0, "dur": 3.2, "lead": 0.0,  "tail": 0.5,
         "caps": [["IT READS THE STATEMENTS...", 0.3, 1.8],
                  ["FLAGS WHAT'S BLEEDING...", 1.8, 3.2]]},
        {"clip": "s4",  "in": 0.0, "dur": 2.4, "lead": 0.35, "tail": 0.4,
         "caps": [["SHOW ME THE PROMPTS.", 0.2, 2.4]]},
        {"clip": "s5b", "in": 0.0, "dur": 3.6, "lead": 0.0,  "tail": 0.4,
         "caps": [["A HUNDRED CREATIVES LAST WEEK.", 0.2, 1.9],
                  ["YOU HAVE NO DESIGNER!", 1.9, 3.6]]},
        {"clip": "s6",  "in": 0.0, "dur": 2.6, "lead": 0.0,  "tail": 0.5,
         "caps": [["IT WRITES THE VARIATIONS...", 0.2, 1.5],
                  ["I JUST PICK...", 1.5, 2.6]]},
        {"clip": "s8",  "in": 0.0, "dur": 2.8, "lead": 0.35, "tail": 0.0,
         "caps": [["NINE MINUTE REPLIES.", 0.2, 1.5],
                  ["NO SUPPORT TEAM.", 1.5, 2.8]]},
        {"clip": "s4",  "in": 0.0, "dur": 2.2, "lead": 0.0,  "tail": 0.3,
         "caps": [["SHOW ME THE PROMPTS!", 0.15, 2.2]]},   # clean repeat
        {"clip": "s9",  "in": 0.0, "dur": 2.4, "lead": 0.3,  "tail": 0.4,
         "caps": [["THEY'RE IN A NEWSLETTER!", 0.2, 2.2]]},
        {"clip": "s10", "in": 0.0, "dur": 2.2, "lead": 0.0,  "tail": 0.3,
         "caps": [["...WHOSE.", 0.4, 2.0]]},
        {"clip": "s11", "in": 0.0, "dur": 2.0, "lead": 0.0,  "tail": 0.4,
         "caps": [["IT'S FREE.", 0.3, 1.8]]},
        {"still": "example_insert", "dur": 1.5, "caps": []},   # the subscribe screen
        {"clip": "s10", "in": 3.7, "dur": 1.9, "lead": 0.0, "tail": 0.3,
         "caps": [["...FREE?", 0.6, 1.9]]},
        {"clip": "s12", "in": 0.0, "dur": 3.4, "lead": 0.0, "tail": 0.0, "caps": []},
    ],
}


def merge(base: dict, over: dict) -> dict:
    """Recursive dict merge. Lists replace wholesale - a partial cut list is
    never what anyone means."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: str | None) -> dict:
    if not path:
        return copy.deepcopy(CONFIG)
    with open(path) as fh:
        return merge(CONFIG, json.load(fh))


def font(path: str, size: int, weight: str):
    f = ImageFont.truetype(path, size)
    for w_ in (weight, "Heavy"):
        try:
            f.set_variation_by_name(w_)
            break
        except Exception:
            continue
    return f


def cap_png(cfg: dict, text: str, path: str) -> str:
    v, c = cfg["video"], cfg["captions"]
    W, H = v["width"], v["height"]
    size = c["size"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt = font(cfg["paths"]["caption_font"], size, c["weight"])
    while d.textlength(text, font=fnt) > W * c["max_width_frac"] and size > c["min_size"]:
        size -= 3
        fnt = font(cfg["paths"]["caption_font"], size, c["weight"])
    x = (W - d.textlength(text, font=fnt)) / 2
    d.text((x, int(H * c["y_frac"])), text, font=fnt, fill=(255, 255, 255, 255),
           stroke_width=c["stroke"], stroke_fill=(0, 0, 0, 240))
    img.save(path)
    return path


def room(x, SR: int, seed: int):
    """Small-kitchen convolution + tilt EQ on a float32 mono signal.

    Pasted or dry audio reads as dubbed. Measured against the reference:
    reverb index 0.93 (reference) vs 0.56 (ours, dry), spectral centroid
    597Hz vs 860Hz. RT60 around 350ms plus a high-shelf cut above 3.8kHz
    closes most of that gap.
    """
    rng = np.random.default_rng(seed)
    ir = np.zeros(int(0.45 * SR), dtype=np.float32)
    ir[0] = 1.0
    for dl, g in [(0.009, 0.5), (0.013, 0.42), (0.021, 0.36), (0.029, 0.3),
                  (0.041, 0.24), (0.055, 0.18), (0.07, 0.13)]:
        ir[int(dl * SR)] += g
    tail = rng.standard_normal(len(ir)).astype(np.float32)
    t = np.arange(len(ir)) / SR
    tail *= np.exp(-t / 0.085)
    b, a = sig.butter(2, 3600 / (SR / 2), btype="low")
    tail = sig.lfilter(b, a, tail).astype(np.float32)
    ir += 0.45 * tail
    ir /= np.abs(ir).max()
    wet = sig.fftconvolve(x, ir)[:len(x)].astype(np.float32)
    mix = 0.55 * x + 0.45 * wet
    b, a = sig.butter(2, 3800 / (SR / 2), btype="high")
    mix = mix - 0.5 * sig.lfilter(b, a, mix)
    return mix


def roomtone(n: int, SR: int, seed: int, gain: float):
    """One continuous bed of kitchen air. This is what turns a row of clips
    into a scene instead of a slideshow."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n).astype(np.float32)
    b, a = sig.butter(2, [30 / (SR / 2), 260 / (SR / 2)], btype="band")
    low = sig.lfilter(b, a, z) * 0.09
    b, a = sig.butter(2, [900 / (SR / 2), 5200 / (SR / 2)], btype="band")
    air = sig.lfilter(b, a, rng.standard_normal(n).astype(np.float32)) * 0.012
    t = (low + air)
    t /= np.abs(t).max()
    return t * gain


def build(cfg: dict) -> None:
    v = cfg["video"]
    W, H, SR, FPS = v["width"], v["height"], v["sample_rate"], v["fps"]
    work = cfg["paths"]["work"]
    os.makedirs(work, exist_ok=True)

    parts, starts, cursor = [], [], 0.0

    # ---- picture: one captioned segment per cut --------------------------
    for idx, cut in enumerate(cfg["cuts"]):
        seg = f"{work}/seg_{idx:02d}.mp4"
        dur = cut["dur"]
        if "still" in cut:
            still = cfg["paths"]["still"].format(name=cut["still"])
            # -loop 1 is mandatory on still overlays: without a timeline the
            # enable/fade expressions see nothing and the overlay is invisible.
            inputs = ["-loop", "1", "-t", str(dur), "-i", still]
        else:
            src = cfg["paths"]["clip"].format(name=cut["clip"])
            if not os.path.exists(src):
                raise SystemExit(f"cut {idx}: source not found: {src}")
            # Clamp to what the source actually holds. A captioned cut that
            # over-asks used to be padded with a repeated last frame, because
            # the caption PNG is a looping input and extends the timeline - and
            # the segment then measured exactly the requested length, so the
            # shortfall warning could never fire. A delivered master carried 47
            # identical frames with a caption burned over them.
            _sd = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", src],
                capture_output=True, text=True).stdout.strip()
            avail = (float(_sd) if _sd else 0.0) - float(cut.get("in", 0.0))
            if avail > 0 and dur > avail + 0.02:
                print(f"WARNING cut {idx} ({cut['clip']}): asked for {dur:.2f}s but only "
                      f"{avail:.2f}s remains after in={cut.get('in', 0.0)}. Clamped. "
                      f"Fix the beat map or pick a longer take.", flush=True)
                dur = round(avail, 3)
            inputs = ["-ss", str(cut.get("in", 0.0)), "-t", str(dur), "-i", src]

        pre = f"{cut['crop']}," if cut.get("crop") else ""
        filt = [f"[0:v]{pre}scale={W}:{H},setsar=1[base]"]
        prev = "base"
        for i, (txt, s, e) in enumerate(cut.get("caps", [])):
            p = cap_png(cfg, txt, f"{work}/c{idx:02d}_{i}.png")
            inputs += ["-loop", "1", "-i", p]
            filt.append(f"[{prev}][{i+1}:v]overlay=0:0:enable='between(t,{s},{e})'[o{i}]")
            prev = f"o{i}"

        subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs +
                       ["-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-an",
                        # output-side -t caps the segment; without it a looped
                        # still runs forever
                        "-t", str(dur), "-c:v", "libx264", "-crf", str(v["crf_segment"]),
                        "-preset", v["preset"], "-pix_fmt", "yuv420p",
                        "-r", str(FPS), seg], check=True)
        parts.append(seg)
        starts.append(cursor)
        # Measure what ffmpeg actually produced. Advancing by the requested
        # duration desynced every later cut's audio by the shortfall whenever a
        # cut asked for more than its source held.
        _probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", seg],
            capture_output=True, text=True).stdout.strip()
        actual = float(_probe) if _probe else dur
        if abs(actual - dur) > 0.04:
            print(f"WARNING seg {idx}: asked for {dur:.2f}s, source gave {actual:.2f}s. "
                  f"Timeline follows the real duration; check the beat map.", flush=True)
        cursor += actual
        print("seg", idx, cut.get("clip") or cut.get("still"),
              f"{actual:.2f}s", flush=True)

    body_dur = cursor

    # ---- end card ---------------------------------------------------------
    # The card is optional. It was previously built unconditionally, which meant
    # any project without the brand assets crashed here with
    # "OSError: cannot open resource" AFTER every segment had been encoded -
    # even with card duration set to 0.
    cd = cfg["card"]
    _card_font = cfg["paths"].get("card_font")
    _card_mark = cfg["paths"].get("card_mark")
    _want_card = float(cd.get("duration") or 0) > 0
    _have_assets = all(x and os.path.exists(x) for x in (_card_font, _card_mark))
    if _want_card and not _have_assets:
        missing = [x for x in (_card_font, _card_mark) if not (x and os.path.exists(x))]
        print(f"WARNING: end card skipped - missing {missing}. "
              f"Set card.duration to 0 to silence this, or supply the brand assets.",
              flush=True)
    if not (_want_card and _have_assets):
        card_path = None
    else:
        card = Image.new("RGB", (W, H), tuple(cd["bg"]))
        d = ImageDraw.Draw(card)
        lf = ImageFont.truetype(cfg["paths"]["card_font"], cd["title_size"])
        try:
            lf.set_variation_by_name(cd["title_variation"])
        except Exception:
            pass
        mark = Image.open(cfg["paths"]["card_mark"]).convert("RGBA").resize(
            (cd["mark_px"], cd["mark_px"]), Image.LANCZOS)
        tw = d.textlength(cd["title"], font=lf)
        lx = (W - (cd["mark_px"] + cd["gap_px"] + tw)) / 2
        ly = int(H * cd["y_frac"])
        card.paste(mark, (int(lx), int(ly + 10)), mark)
        d.text((lx + cd["mark_px"] + cd["gap_px"], ly), cd["title"], font=lf,
               fill=(255, 255, 255))
        sf2 = font(cfg["paths"]["caption_font"], cd["tag_size"], cd["tag_weight"])
        tag = cd["tag"]
        d.text(((W - d.textlength(tag, font=sf2)) / 2, ly + cd["tag_offset_px"]), tag,
               font=sf2, fill=tuple(cd["tag_color"]))
        card.save(f"{work}/card.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1",
                        "-i", f"{work}/card.png", "-t", str(cd["duration"]),
                        "-r", str(FPS), "-c:v", "libx264", "-crf", str(v["crf_segment"]),
                        "-preset", v["preset"], "-pix_fmt", "yuv420p",
                        f"{work}/seg_card.mp4"], check=True)
        parts.append(f"{work}/seg_card.mp4")

    with open(f"{work}/list.txt", "w") as f:
        for p in parts:
            f.write(f"file '{os.path.basename(p)}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", f"{work}/list.txt", "-c:v", "libx264",
                    "-crf", str(v["crf_segment"]), "-preset", v["preset"],
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    f"{work}/video.mp4"], check=True)

    # ---- single audio timeline -------------------------------------------
    au = cfg["audio"]
    total = body_dur + cd["duration"]
    N = int(total * SR)
    bus = roomtone(N, SR, au["roomtone_seed"], au["roomtone_gain"])

    for cut, t0 in zip(cfg["cuts"], starts):
        name = cut.get("clip")
        if name is None or name in au["skip_clips"]:
            continue
        inp = cut.get("in", 0.0)
        dur = cut["dur"]
        lead = cut.get("lead", 0.0)
        tailx = cut.get("tail", 0.0)
        raw = f"{work}/a_{name}_{t0:.1f}.wav"
        a_in = max(0.0, inp - lead)
        a_dur = (inp - a_in) + dur + tailx
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(a_in),
                            "-t", str(a_dur), "-i", cfg["paths"]["clip"].format(name=name),
                            "-vn", "-ac", "1", "-ar", str(SR), raw])
        if r.returncode != 0:
            continue      # a silent take has no audio stream; that is allowed
        sr_, x = wav.read(raw)
        x = x.astype(np.float32) / 32768.0
        if x.ndim > 1:
            x = x.mean(1)
        x = room(x, SR, au["room_seed"])
        # fade edges so overlaps blend instead of clicking
        f_n = int(au["fade_s"] * SR)
        env = np.ones(len(x), dtype=np.float32)
        env[:f_n] = np.linspace(0, 1, f_n)
        env[-f_n:] = np.linspace(1, 0, f_n)
        x *= env
        p0 = int((t0 - (inp - a_in)) * SR)
        p0 = max(0, p0)
        p1 = min(N, p0 + len(x))
        bus[p0:p1] += x[:p1 - p0]
        print("audio", name, f"@{t0 - (inp - a_in):.2f}s", flush=True)

    # ---- music: low, looped, dead stop on the deflation beat --------------
    mu = cfg["music"]
    _bed = mu.get("bed")
    if _bed and not os.path.exists(_bed):
        print(f"WARNING: music bed {_bed!r} not found - continuing with no music. "
              f"The default is inherited from the built-in example config; set "
              f'"music": {{"bed": null}} in your config to silence this.', flush=True)
        _bed = None
    if _bed and mu.get("stop_index") is not None and mu["stop_index"] < len(cfg["cuts"]):
        stop = starts[mu["stop_index"]]
        mn = int(stop * SR)
        msr, m = wav.read(_bed)
        m = m.astype(np.float32) / 32768.0
        if m.ndim > 1:
            m = m.mean(1)
        if msr != SR:
            import scipy.signal as _sg
            m = _sg.resample(m, int(len(m) * SR / msr)).astype(np.float32)
        reps = int(np.ceil(mn / len(m)))
        m = np.tile(m, reps)[:mn]
        fade = int(mu["fade_s"] * SR)
        m[-fade:] *= np.linspace(1, 0, fade)
        bus[:mn] += mu["gain"] * m

    peak = np.abs(bus).max()
    if peak > au["peak_ceiling"]:
        bus *= au["peak_ceiling"] / peak
    wav.write(f"{work}/bus.wav", SR, (bus * 32767).astype(np.int16))

    # Mux the audio bus onto the cut, and grade in the same pass. The grade is
    # the realism step (contrast/saturation down, grain back on). It has to
    # re-encode video, so it cannot be a stream copy like it was.
    master = cfg["outputs"]["master"]
    vf = chain(cfg["grade"]["strong"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{work}/video.mp4",
                    "-i", f"{work}/bus.wav", "-map", "0:v", "-map", "1:a",
                    "-vf", vf,
                    "-c:v", "libx264", "-crf", str(v["crf_master"]),
                    "-preset", v["preset"], "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest",
                    master], check=True)

    for r in cfg["outputs"]["ratios"]:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", master,
                        "-vf", r["crop"], "-c:v", "libx264", "-crf", str(r["crf"]),
                        "-preset", v["preset"], "-pix_fmt", "yuv420p",
                        "-c:a", "copy", r["file"]], check=True)

    print(f"ASSEMBLED body={body_dur:.1f}s total={total:.1f}s graded={vf}", flush=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="cut, treat, caption, card, grade, both ratios")
    b.add_argument("--config", help="JSON overriding any key of CONFIG")

    g = sub.add_parser("grade", help="the grade/grain pass on its own")
    g.add_argument("src")
    g.add_argument("dst", nargs="?")
    g.add_argument("--strong", action="store_true",
                   help="add the blunt skin-highlight pull, for tight faces")
    g.add_argument("--compare", action="store_true",
                   help="write before/after stills instead of a video")
    g.add_argument("--at", type=float, default=1.0, help="timestamp for --compare")

    a = ap.parse_args(argv[1:])

    if a.cmd == "build":
        build(load_config(a.config))
        return 0

    if a.compare:
        grade_compare(a.src, a.at)
        return 0
    if not a.dst:
        ap.error("dst required unless --compare")
    grade_run(a.src, a.dst, a.strong)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
