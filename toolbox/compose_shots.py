#!/usr/bin/env python3
"""Compose a video from a shot list timed to spoken words.

One voice track and its Whisper word timings set the clock. Each spoken phrase gets its shots: a still (with an
eased push-in, or its vetted motion clip), a span of any clip, a captured page as a scrolling card, a count-up
number screen, a two-up split, or a pre-rendered insert (a document sweep, a recorded site interaction, any clip).
Optional on top: a presenter cutout at one size in a lower corner, phrase captions that never strand a last word,
a hook and section labels as pills, a name card on a cue word, a source line on cards, and a closing clip.
Every text box is checked against the platform safe zone on every frame (safezone.py); a violation fails the
render. The soundtrack gets voice EQ, a ducked bed and a measured, linear loudness pass. Both ratios by default.
All styling comes from the active brand (brandstyle.py). Syntax: toolbox/README.md, "Shot lists".

  python3 toolbox/compose_shots.py segments <voice.json>          # numbered phrases, to write the shot list against
  python3 toolbox/compose_shots.py check <shots.json>             # every asset exists and every token parses
  python3 toolbox/compose_shots.py render <shots.json> [--ratio 9x16|4x5|both] [--out-dir DIR] [--qa] [--brand-json F]

Exit codes: 0 ok, 1 bad input, 2 safe-zone violation (the file is renamed *_SAFEZONE-FAIL.mp4)."""
import argparse, json, math, pathlib, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style
from safezone import Zone, sheet as zone_sheet

FPS = 30


def ffdur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode().strip())


def ffsize(p):
    w, h = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                    "-of", "csv=p=0", str(p)]).decode().strip().split(",")[:2]
    return int(w), int(h)


# ---------------------------------------------------------------- words, captions
def load_words(path):
    segs = json.load(open(path))["segments"]; words = []
    for s in segs:
        for w in s.get("words", []):
            t = w["word"].strip()
            if words and t[:1] in ",." and len(t) > 1: words[-1] = dict(words[-1], word=words[-1]["word"] + t, end=w["end"])
            else: words.append(dict(w))
    return segs, words


def caption_chunks(words, speed, cfg):
    """phrase chunks; look ahead so one word is never left alone before a full stop; never break after a weak word"""
    rep = cfg.get("replace", {}) or {}; weak = set(cfg["weak_words"])
    def text(ch):
        t = " ".join(x["word"].strip() for x in ch)
        for k, v in rep.items(): t = re.sub(re.escape(k), v, t, flags=re.I)
        return t
    caps, chunk = [], []
    for i, w in enumerate(words):
        chunk.append(w); t = w["word"].strip(); txt = text(chunk)
        nxt = words[i+1]["word"].strip() if i + 1 < len(words) else ""
        is_weak = t.lower().strip(".,?!") in weak
        sentence_end = t.endswith((".", ",", "?", "!"))
        next_closes = nxt.endswith((".", ",", "?", "!")) and len(chunk) <= cfg["hard_max_words"] - 2
        if sentence_end or ((len(chunk) >= cfg["max_words"] or len(txt) >= cfg["max_chars"]) and not is_weak and not next_closes) \
                or len(chunk) >= cfg["hard_max_words"]:
            caps.append((chunk[0]["start"]/speed, chunk[-1]["end"]/speed + 0.05, txt)); chunk = []
    if chunk: caps.append((chunk[0]["start"]/speed, chunk[-1]["end"]/speed + 0.05, text(chunk)))
    return caps


# ---------------------------------------------------------------- tokens
KINDS = ("s", "v", "c", "n", "x", "i")
def parse_token(raw):
    """-> dict(kind, ref, cue, hide, cap, raw). Kinds: s v c n x i, END, +"""
    t = raw.strip(); cue = None
    m = re.match(r"^(.*)@([^\s|@:]+)$", t)
    if m and t != "END": t, cue = m.group(1), m.group(2).lower()
    hide = cap = None
    while t and t[-1] in "~^_":
        c = t[-1]; t = t[:-1]
        if c == "~": hide = True
        elif c == "^": cap = "high"
        else: cap = "bottom"
    if t in ("END", "+"): return dict(kind=t, ref="", cue=cue, hide=hide, cap=cap, raw=raw)
    kind, sep, ref = t.partition(":")
    if not sep or kind not in KINDS: raise ValueError(f"bad shot token {raw!r}")
    return dict(kind=kind, ref=ref, cue=cue, hide=hide, cap=cap, raw=raw)


class ShotList:
    def __init__(self, path):
        self.path = pathlib.Path(path).resolve(); self.base = self.path.parent; self.d = json.load(open(path))
        self.shots = {int(k): v for k, v in self.d["shots"].items()}
        self.inserts = self.d.get("inserts", {})

    def p(self, rel, fmt=None):
        if rel in (None, ""): return None
        s = str(rel).replace("{fmt}", fmt) if fmt else str(rel)
        q = pathlib.Path(s); return q if q.is_absolute() else self.base / q

    def still_path(self, name):
        if pathlib.Path(name).suffix: return self.p(name)
        d = self.p(self.d.get("stills", "stills"))
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            if (d / (name + ext)).exists(): return d / (name + ext)
        return d / (name + ".png")

    def clip_path(self, name):
        return self.p(name) if pathlib.Path(name).suffix else self.p(self.d.get("clips", "clips")) / (name + ".mp4")

    def insert(self, ref):
        name = ref.split(":")[0]
        if name not in self.inserts: raise ValueError(f"insert {name!r} is not registered under 'inserts'")
        return name, self.inserts[name]

    def assets(self, fmt):
        need = [("voice", self.p(self.d["voice"])), ("words", self.p(self.d["words"]))]
        if self.d.get("presenter"): need.append(("presenter", self.p(self.d["presenter"], fmt)))
        if self.d.get("close"): need.append(("close", self.p(self.d["close"]["file"], fmt)))
        for i, toks in self.shots.items():
            for raw in toks:
                t = parse_token(raw); k, r = t["kind"], t["ref"]
                if k == "s":
                    need.append((raw, self.still_path(r)))
                    mo = self.d.get("motion", {}).get(r)
                    if mo: need.append((raw + " motion", self.p(mo["clip"])))
                elif k == "v": need.append((raw, self.clip_path(r.rsplit(":", 1)[0])))
                elif k == "c":
                    if r not in self.d.get("cards", {}): raise ValueError(f"card {r!r} is not registered under 'cards'")
                    need.append((raw, self.p(self.d["cards"][r]["file"])))
                elif k == "x":
                    for s_ in r.split("|")[:2]: need.append((raw, self.still_path(s_)))
                elif k == "i": need.append((raw, self.p(self.insert(r)[1]["file"], fmt)))
                elif k == "END" and not self.d.get("close"): raise ValueError("END used but no 'close' clip is registered")
        for b in self.d.get("number_backgrounds", []): need.append(("number_backgrounds", self.still_path(b)))
        return need


class Clip:
    """forward-only frame reader. One per use: a reader that has played cannot rewind, so a clip used twice freezes."""
    def __init__(self, path, W, H, start=0.0):
        self.W, self.H = W, H
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(path), "-vf",
                                   f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.i = -1; self.last = Image.new("RGB", (W, H))

    def at(self, idx):
        while self.i < idx:
            raw = self.p.stdout.read(self.W*self.H*3)
            if len(raw) < self.W*self.H*3: break
            self.last = Image.frombytes("RGB", (self.W, self.H), raw); self.i += 1
        return self.last.copy()

    def close(self):
        try: self.p.kill()
        except Exception: pass


class Render:
    def __init__(self, sl, st, fmt, out_dir, qa):
        self.sl, self.st, self.fmt, self.qa = sl, st, fmt, qa
        self.W, self.H = (1080, 1920) if fmt == "9x16" else (1080, 1350); W = self.W
        self.zone = Zone.for_frame(self.W, self.H, st)
        self.TOP, self.BOT, self.LEFT, self.RAIL = self.zone.top, self.zone.bottom, self.zone.left, self.zone.right
        self.TEXT_CX = W/2; self.TEXT_W = 2*min(self.RAIL - W/2, W/2 - self.LEFT) - 0.02*W
        stem = sl.d.get("name") or sl.path.stem
        self.out = pathlib.Path(out_dir) / f"{stem}_{fmt}.mp4"; self.out.parent.mkdir(parents=True, exist_ok=True)
        self.speed = float(sl.d.get("speed", st.get("audio.speed", 1.0)))
        self.cache = {}; self.BOXES = []

    # ---------- timing
    def plan(self):
        sl = self.sl; spd = self.speed
        self.segs, self.words = load_words(sl.p(sl.d["words"]))
        self.voice = sl.p(sl.d["voice"]); self.vdur = ffdur(self.voice)/spd
        starts = [s["start"]/spd for s in self.segs] + [self.vdur]; starts[0] = 0.0; self.starts = starts
        SH = []; end_t = None
        for i in range(len(self.segs)):
            a, b = starts[i], starts[i+1]
            toks = sl.shots.get(i)
            if toks is None: print(f"  note: phrase {i} has no shot, holding the previous one"); toks = ["+"]
            T = [parse_token(x) for x in toks]; k0 = T[0]["kind"]
            if k0 == "END": end_t = a; break
            if k0 == "+":
                if SH: SH[-1][1] = b
                continue
            if len(T) == 1 and k0 == "i" and SH and SH[-1][2]["raw"] == T[0]["raw"] and sl.insert(T[0]["ref"])[1].get("fit", "cut") == "rate":
                SH[-1][1] = b; continue                                    # a rate-fit insert over consecutive phrases is one shot
            n = len(T); cuts = [a]
            for k in range(1, n):
                cue = T[k]["cue"]; hit = None
                if cue:
                    hit = next((w["start"]/spd for w in self.segs[i].get("words", [])
                                if w["word"].strip().lower().strip(".,?!") == cue and w["start"]/spd > cuts[-1]), None)
                    if hit is None: print(f"  note: cue word {cue!r} not found in phrase {i}; splitting evenly")
                cuts.append(hit if hit is not None else a + (b - a)*k/n)
            cuts.append(b)
            for k in range(n): SH.append([cuts[k], cuts[k+1], T[k]])
        if end_t is None: end_t = self.vdur
        close = sl.d.get("close") or {}; end_len = float(close.get("len", 7.5)) if close else 0.0
        if SH and SH[-1][2]["kind"] == "i":                               # a closing insert with fit "full" plays in real time, in full;
            name, ins = sl.insert(SH[-1][2]["ref"])                        # the close waits for it
            if ins.get("fit") == "full":
                L = ffdur(sl.p(ins["file"], self.fmt))
                if end_t < SH[-1][0] + L: end_t = SH[-1][0] + L
                SH[-1][1] = end_t
                if close: end_len = float(close.get("len_after_full", end_len))
        self.end_t = end_t; self.dur = max(self.vdur + 0.6, end_t + end_len)
        if close: SH.append([end_t, self.dur, parse_token("END")])
        elif SH: SH[-1][1] = self.dur
        self.SHOTS = SH; self.N = int(math.ceil(self.dur*FPS))
        self.caps = caption_chunks(self.words, spd, self.st.d["caption"])
        labels = sorted((int(k), v) for k, v in (sl.d.get("labels") or {}).items())
        self.labels = [(starts[i] if i < len(starts) else 0, v) for i, v in labels]
        self.name_card = sl.d.get("name_card") or {}
        cue = (self.name_card.get("cue") or "").lower()
        self.name_t = next((w["start"]/spd for w in self.words if cue and w["word"].strip().lower().startswith(cue)), None)
        print(f"{self.out.name}: voice {self.vdur:.1f}s, video {self.dur:.1f}s, {len(SH)} shots")

    # ---------- type
    def wrap_fit(self, d, text, weight, size, maxw, maxlines=2):
        """balanced wrap into <= maxlines lines no wider than maxw, shrinking the font until it fits; never cuts text"""
        s = size; ws = text.split()
        while True:
            f = self.st.font(weight, s); tl = lambda t: d.textlength(t, font=f)
            if tl(text) <= maxw: return f, [text]
            best = None
            for k in range(1, len(ws)):
                ls = [" ".join(ws[:k]), " ".join(ws[k:])]; m = max(map(tl, ls))
                if m <= maxw and (best is None or m < best[0]): best = (m, ls)
            if not best and maxlines >= 3:
                for i in range(1, len(ws) - 1):
                    for j in range(i + 1, len(ws)):
                        ls = [" ".join(ws[:i]), " ".join(ws[i:j]), " ".join(ws[j:])]; m = max(map(tl, ls))
                        if m <= maxw and (best is None or m < best[0]): best = (m, ls)
            if best: return f, best[1]
            if s < 12: return f, [text]
            s *= 0.94

    def fit(self, d, text, weight, size, maxw):
        s = size; f = self.st.font(weight, s)
        while d.textlength(text, font=f) > maxw and s > 10: s *= 0.94; f = self.st.font(weight, s)
        return f

    def shadow_text(self, bg, xy, text, font, fill, blur=5, alpha=170, stroke=0, stroke_fill=(0, 0, 0)):
        m = Image.new("L", bg.size, 0); ImageDraw.Draw(m).text((xy[0], xy[1] + 3), text, font=font, fill=alpha)
        bg.paste(Image.new("RGB", bg.size, (0, 0, 0)), (0, 0), m.filter(ImageFilter.GaussianBlur(blur)))
        d = ImageDraw.Draw(bg); d.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        self.BOXES.append(("text", d.textbbox(xy, text, font=font, stroke_width=stroke)))

    def pills(self, bg, lines, f, y, pad=(28, 18), r=18, gap=10):
        d = ImageDraw.Draw(bg); cap = d.textbbox((0, 0), "H", font=f); ch = cap[3] - cap[1]
        bgc, ink = self.st.color("pill_bg"), self.st.color("pill_ink")
        for ln in lines:
            tw = d.textlength(ln, font=f); x = self.TEXT_CX - tw/2; box = (x - pad[0], y, x + tw + pad[0], y + ch + 2*pad[1])
            d.rounded_rectangle(box, radius=r, fill=bgc); d.text((x, y + pad[1] - cap[1]), ln, font=f, fill=ink)
            self.BOXES.append(("pill", box)); y += ch + 2*pad[1] + gap
        return y

    # ---------- pictures
    def grade(self, im):
        g = self.st.d["grade"]
        if "lut" not in self.cache:
            L = [min(255, int(g["lift"] + v*(255 - g["lift"])/255)) for v in range(256)]
            self.cache["lut"] = [min(255, int(L[v]*(1 + g["warm"]))) for v in range(256)] + L + [int(L[v]*(1 - g["warm"]*1.4)) for v in range(256)]
        im = ImageEnhance.Contrast(im).enhance(g["contrast"]); im = ImageEnhance.Color(im).enhance(g["saturation"])
        return im.point(self.cache["lut"])

    def still(self, name):
        key = "s:" + name
        if key not in self.cache:
            im = Image.open(self.sl.still_path(name)).convert("RGB"); sc = max(self.W/im.width, self.H/im.height)*1.10
            self.cache[key] = self.grade(im.resize((int(im.width*sc) + 1, int(im.height*sc) + 1), Image.LANCZOS))
        return self.cache[key]

    def kenburns(self, big, p):
        z = 1.0 + 0.06*(0.5 - 0.5*math.cos(math.pi*p))                  # one consistent eased push-in on every still
        cw, ch = min(big.width, int(self.W/z)), min(big.height, int(self.H/z)); x, y = (big.width - cw)//2, (big.height - ch)//2
        return big.crop((x, y, x + cw, y + ch)).resize((self.W, self.H), Image.BILINEAR)

    def frames_of(self, path, t0, use, n):
        key = f"f:{path}:{t0}:{use}:{n}"
        if key not in self.cache:
            W, H = self.W, self.H
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(use), "-i", str(path), "-vf",
                                  f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            fr = [Image.frombytes("RGB", (W, H), raw[i*W*H*3:(i+1)*W*H*3]) for i in range(len(raw)//(W*H*3))] or [Image.new("RGB", (W, H))]
            self.cache[key] = [self.grade(fr[min(len(fr) - 1, int(j*len(fr)/n))]) for j in range(n)]   # real time if it fits, else gently slowed
        return self.cache[key]

    def card(self, ref, p):
        key = "c:" + ref
        if key not in self.cache:
            c = self.sl.d["cards"][ref]; im = Image.open(self.sl.p(c["file"])).convert("RGB")
            x0, x1 = c.get("x0", 0), c.get("x1", im.width)
            cw = self.W if c.get("bleed") else int(self.RAIL - self.LEFT); sc = cw/(x1 - x0)   # default: the column fits between the safe edges
            page = im.crop((x0, 0, x1, im.height)).resize((cw, int(im.height*sc)), Image.LANCZOS)
            col = Image.new("RGB", (self.W, page.height), page.getpixel((2, 2))); col.paste(page, (0 if c.get("bleed") else int(self.LEFT), 0))
            self.cache[key] = (col, c.get("headline_y", 0)*sc, c.get("source", ""))
        col, hy, src = self.cache[key]
        y = int(hy - (self.TOP + 0.07*self.H) + 60*p)                     # the headline sits just under the label zone; slow scroll
        y = min(y, max(0, col.height - self.H))
        fr = Image.new("RGB", (self.W, self.H), col.getpixel((5, min(col.height - 1, max(0, y + self.H - 1)))))   # pad with the page's own colour, never black
        if y < 0: fr.paste(Image.new("RGB", (self.W, -y), col.getpixel((5, 0))), (0, 0))   # headline near the page top: push the page down
        fr.paste(col.crop((0, max(0, y), self.W, min(col.height, y + self.H))), (0, max(0, -y)))
        return fr, src

    def numscreen(self, spec, p, seed):
        W, H = self.W, self.H; big, label, sub = (spec.split("|") + ["", ""])[:3]; nc = self.st.d["number"]
        bgs = self.sl.d.get("number_backgrounds") or []
        bg = self.kenburns(self.still(bgs[seed % len(bgs)]), p) if bgs else Image.new("RGB", (W, H), self.st.color("shade"))
        key = "shade"
        if key not in self.cache:
            m = Image.new("L", (1, H))
            for y in range(H): m.putpixel((0, y), int(200*max(0, 1 - y/(0.72*H))**1.3))
            self.cache[key] = m.resize((W, H))
        bg.paste(Image.new("RGB", (W, H), self.st.color("shade")), (0, 0), self.cache[key])
        d = ImageDraw.Draw(bg); col = self.st.color("number"); x = int(self.LEFT + 0.01*W); y = int(self.TOP + 0.02*H); maxw = (self.RAIL - x)*0.95
        if label:
            fl = self.fit(d, label.upper(), "regular", nc["label_size"]*W, maxw)
            self.shadow_text(bg, (x, y), label.upper(), fl, col, blur=6, alpha=150); y += int(fl.size*1.9)
        m = re.match(r"^([^\d]*)([\d,]+)(.*)$", big); k = min(1, p/max(0.01, nc["count_up"]))
        val = f"{m.group(1)}{int(int(m.group(2).replace(',', ''))*(1 - (1 - k)**3)):,}{m.group(3)}" if m else big
        fb = self.fit(d, re.sub(r"\d", "8", big), "light", nc["size"]*W, maxw)   # sized on the widest digits so the count-up never grows past the rail
        self.shadow_text(bg, (x, y), val, fb, col, blur=12, alpha=120); y += int(fb.size*1.18)
        if sub:
            fs, lines = self.wrap_fit(ImageDraw.Draw(bg), sub, "light", nc["sub_size"]*W, maxw, 3)
            for ln in lines: self.shadow_text(bg, (x, y), ln, fs, col, blur=7, alpha=150); y += int(fs.size*1.28)
        return bg

    def split_shot(self, spec, p):
        a, b, *labs = spec.split("|"); W, H = self.W, self.H; bg = Image.new("RGB", (W, H), (255, 255, 255))
        bg.paste(self.kenburns(self.still(a), p).crop((W//4, 0, W//4 + W//2, H)), (0, 0))
        bg.paste(self.kenburns(self.still(b), p).crop((W//4, 0, W//4 + W//2, H)), (W//2 + 3, 0))
        if labs:
            f = self.st.font("heavy", self.st.d["name_card"]["size"]*W); d = ImageDraw.Draw(bg); cap = d.textbbox((0, 0), "H", font=f); ch = cap[3] - cap[1]
            half = (self.RAIL - self.LEFT)/2
            for txt, cx in zip(labs[:2], (self.LEFT + half/2, self.LEFT + 1.5*half)):
                tw = d.textlength(txt, font=f); x = cx - tw/2; y = int(self.TOP + 0.015*H); box = (x - 24, y, x + tw + 24, y + ch + 30)
                d.rounded_rectangle(box, radius=15, fill=self.st.color("pill_bg")); d.text((x, y + 15 - cap[1]), txt, font=f, fill=self.st.color("pill_ink"))
                self.BOXES.append(("pill", box))
        return bg

    # ---------- overlays
    def caption(self, bg, tt, where, scrim):
        live = [c for c in self.caps if c[0] <= tt < c[1]]
        if not live: return
        cfg = self.st.d["caption"]; W, H = self.W, self.H
        d = ImageDraw.Draw(bg); f, lines = self.wrap_fit(d, live[-1][2], "bold", cfg["size"]*W, self.TEXT_W*0.94, cfg["lines"]); lh = int(f.size*1.22)
        if where == "high": y = int(self.TOP + 0.13*H)
        elif where == "bottom": y = int(self.BOT - 0.012*H - len(lines)*lh)
        else: y = int(self.CAP_Y - len(lines)*lh)
        if scrim:
            y0, y1 = max(0, y - int(0.03*H)), min(H, y + len(lines)*lh + int(0.03*H))
            band = Image.blend(bg.crop((0, y0, W, y1)).filter(ImageFilter.GaussianBlur(14)), Image.new("RGB", (W, y1 - y0), self.st.color("scrim")), 0.45)
            m = Image.new("L", band.size, 0); md = ImageDraw.Draw(m)
            for yy in range(band.height): md.line([(0, yy), (W, yy)], fill=int(255*min(1, yy/(0.025*H), (band.height - yy)/(0.025*H))))
            bg.paste(band, (0, y0), m)
        for ln in lines:
            x = int(self.TEXT_CX - d.textlength(ln, font=f)/2)
            self.shadow_text(bg, (x, y), ln, f, self.st.color("caption"), blur=8, alpha=190, stroke=cfg["stroke"], stroke_fill=self.st.color("caption_stroke"))
            y += lh

    def label_at(self, tt):
        cur = ""
        for t0, v in self.labels:
            if t0 <= tt: cur = v
        return cur

    def draw_label(self, bg, text):
        if not text: return
        lc = self.st.d["label"]; text = text.upper() if lc.get("uppercase") else text
        f, lines = self.wrap_fit(ImageDraw.Draw(bg), text, "heavy", lc["size"]*self.W, self.TEXT_W*0.90, 2)
        self.pills(bg, lines, f, int(self.TOP + 0.015*self.H), pad=tuple(lc["pad"]), r=lc["radius"])

    def draw_hook(self, bg, text):
        hc = self.st.d["hook"]; f, lines = self.wrap_fit(ImageDraw.Draw(bg), text, "heavy", hc["size"]*self.W, self.TEXT_W*0.92, hc["lines"])
        self.pills(bg, lines, f, int(self.TOP + 0.08*self.H))

    def name_on(self, tt):
        return self.name_t is not None and self.name_t - 0.2 <= tt <= self.name_t + self.st.d["name_card"]["seconds"]

    def draw_name(self, bg):
        nc = self.st.d["name_card"]; W = self.W
        y = self.pills(bg, [self.name_card.get("name", "")], self.st.font("heavy", nc["size"]*W), int(self.TOP + 0.015*self.H), pad=(26, 16), r=16)
        if self.name_card.get("title"): self.pills(bg, [self.name_card["title"]], self.st.font("bold", nc["sub_size"]*W), y, pad=(20, 12), r=12)

    def draw_source(self, bg, txt):
        if not txt: return
        d = ImageDraw.Draw(bg, "RGBA"); f = self.st.font("regular", 0.026*self.W); tw = d.textlength(txt, font=f)
        right = self.st.d["presenter"]["side"] != "right" or not self.sl.d.get("presenter")     # the side away from the presenter
        x = int(self.RAIL - tw - 0.03*self.W) if right else int(self.LEFT + 0.03*self.W); y = int(self.BOT - 0.012*self.H - f.size*1.6); box = (x - 10, y - 6, x + tw + 10, y + f.size*1.3)
        d.rectangle(box, fill=self.st.color("source_bg") + (150,)); d.text((x, y), txt, font=f, fill=self.st.color("source_ink"))
        self.BOXES.append(("text", box))

    # ---------- presenter
    def open_presenter(self):
        src = self.sl.d.get("presenter"); self.pres = None
        if not src: return
        path = self.sl.p(src, self.fmt); pw, ph = ffsize(path); self.PW0, self.PH0 = pw, ph
        dec = ["-c:v", "libvpx-vp9"] if path.suffix.lower() == ".webm" else []   # the native vp9 decoder keeps the alpha plane
        self.pres = subprocess.Popen(["ffmpeg", "-v", "error", *dec, "-i", str(path), "-vf", f"setpts=PTS/{self.speed},fps={FPS}",
                                      "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        pc = self.st.d["presenter"]; W, H = self.W, self.H
        es, eb = [int(v*pw/1080) for v in pc["edge_feather"]]
        edge = Image.new("L", (pw, ph), 255); ed = ImageDraw.Draw(edge)
        for i in range(es):
            v = int(255*i/max(1, es)); ed.line([(i, 0), (i, ph)], fill=v); ed.line([(pw - 1 - i, 0), (pw - 1 - i, ph)], fill=v)
        for i in range(eb):
            v = int(255*i/max(1, eb)); ed.line([(0, ph - 1 - i), (pw, ph - 1 - i)], fill=v)
        self.edge = edge; self.JW = int(W*pc["width"][self.fmt]); self.JH = int(self.JW*ph/pw)
        self.JX = int(0.01*W) if pc["side"] == "left" else int(self.RAIL - self.JW)
        self.JY = int(pc["bottom"][self.fmt]*H - self.JH*0.97); self.plast = None

    def presenter_frame(self):
        if not self.pres: return None
        raw = self.pres.stdout.read(self.PW0*self.PH0*4)
        if len(raw) == self.PW0*self.PH0*4:                                # read every frame, shown or not, so picture and voice stay locked
            im = Image.frombytes("RGBA", (self.PW0, self.PH0), raw); im.putalpha(ImageChops.multiply(im.getchannel("A"), self.edge))
            self.plast = im.resize((self.JW, self.JH), Image.BILINEAR)
        return self.plast

    # ---------- sound
    def mix(self, tmp):
        a = self.st.d["audio"]; dur = self.dur
        if self.sl.d.get("bed"): bed = self.sl.p(self.sl.d["bed"])
        elif a.get("bed"): bed = self.st.path(a["bed"])
        else: bed = None
        vo = tmp/"voice_sped.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(self.voice), "-af", f"atempo={self.speed},apad=pad_dur={dur - self.vdur + 0.5:.2f}",
                        "-ar", "48000", str(vo)], check=True)
        eq = a["voice_eq"] or "anull"
        if bed and pathlib.Path(bed).exists():
            af = (f"[0:a]{eq},aformat=channel_layouts=stereo,asplit=2[v][vk];"
                  f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{dur:.2f},aformat=channel_layouts=stereo,volume={a['bed_db']}dB,"
                  f"volume='if(gte(t,{self.end_t:.2f}),{a['bed_end_lift']},1)':eval=frame[m0];"
                  f"[m0][vk]sidechaincompress=threshold=0.02:ratio=5:attack=15:release=350[m1];[m1]afade=t=out:st={max(0, dur - 1.0):.2f}:d=1.0[m];"
                  f"[v][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=false,atrim=0:{dur:.2f}[a]")
            ins = ["-i", str(vo), "-stream_loop", "-1", "-i", str(bed)]
        else:
            if bed: print(f"  note: bed {bed} not found, voice only")
            af = f"[0:a]{eq},aformat=channel_layouts=stereo,alimiter=limit=0.95:level=false,atrim=0:{dur:.2f}[a]"; ins = ["-i", str(vo)]
        pre = tmp/"mix_pre.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", af, "-map", "[a]", "-ar", "48000", str(pre)], check=True)
        tgt, tp = a["lufs"], a["true_peak"]                                # measured two-pass loudnorm, linear = one static gain
        m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pre), "-af", f"loudnorm=I={tgt}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        js = json.loads(m[m.rindex("{"):m.rindex("}") + 1]); out = tmp/"mix.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-af",
                        f"loudnorm=I={tgt}:TP={tp}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:"
                        f"measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true", "-ar", "48000", str(out)], check=True)
        return out

    # ---------- frame loop
    def run(self):
        self.plan(); W, H = self.W, self.H; st = self.st; sl = self.sl
        self.open_presenter(); self.CAP_Y = (self.JY - 0.03*H) if self.pres else (self.BOT - 0.05*H)
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="compose_")); vid = tmp/"video.mp4"; ex = st.d["export"]
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-preset", "medium", "-crf", str(ex["crf"]), "-maxrate", ex["maxrate"], "-bufsize", ex["bufsize"],
                                "-pix_fmt", "yuv420p", str(vid)], stdin=subprocess.PIPE)
        readers = {}; si = 0; viol = []; qa = []; grain = st.d["grade"]["grain"]; hook = sl.d.get("hook", ""); motion = sl.d.get("motion", {})
        for n in range(self.N):
            tt = n/FPS; self.BOXES = []
            while si < len(self.SHOTS) - 1 and tt >= self.SHOTS[si][1]:
                if si in readers: readers.pop(si).close()
                si += 1
            t0, t1, T = self.SHOTS[si]; k, ref = T["kind"], T["ref"]; p = min(1, max(0, (tt - t0)/max(0.01, t1 - t0)))
            label_ok = True; src = ""; photo = False; show_p = not T["hide"]; cap_where = T["cap"] or "default"; scrim = False
            nf = max(1, int(round((t1 - t0)*FPS))); j0 = int(round(t0*FPS))
            if k == "END":
                r = readers.setdefault(si, Clip(sl.p(sl.d["close"]["file"], self.fmt), W, H)); bg = r.at(int((tt - t0)*FPS)); label_ok = show_p = False
            elif k == "i":
                name, ins = sl.insert(ref); path = sl.p(ins["file"], self.fmt); fit = ins.get("fit", "cut"); rng = ref.split(":")[1] if ":" in ref else None
                if fit == "rate":                                           # rate-fit into the span, clamped so it never looks sped or slowed
                    if si not in readers: readers[si] = Clip(path, W, H); self.cache[f"rate{si}"] = min(1.3, max(0.8, ffdur(path)/max(0.1, t1 - t0)))
                    bg = readers[si].at(int((tt - t0)*self.cache[f"rate{si}"]*FPS))
                else:                                                       # real time; a short slot shows the END of the range, not cut-off typing
                    d0, d1 = (map(float, rng.split("-")) if rng else (0.0, ffdur(path)))
                    d0 = d0 if fit == "full" else max(d0, d1 - (t1 - t0))
                    r = readers.setdefault(si, Clip(path, W, H, start=d0)); bg = r.at(int(min(d1 - d0, tt - t0)*FPS))
                label_ok = False; show_p = show_p and bool(ins.get("presenter", False)); cap_where = T["cap"] or ins.get("captions", "bottom"); scrim = True
            elif k == "s" and ref in motion:
                mo = motion[ref]; fr = self.frames_of(sl.p(mo["clip"]), mo.get("trim", 0), min(mo.get("use", 3.0), nf/FPS), nf)
                bg = fr[min(len(fr) - 1, n - j0)].copy(); photo = True
            elif k == "s": bg = self.kenburns(self.still(ref), p); photo = True
            elif k == "v":
                name, span = ref.rsplit(":", 1); a_, b_ = map(float, span.split("-"))
                fr = self.frames_of(sl.clip_path(name), a_, b_ - a_, nf); bg = fr[min(len(fr) - 1, n - j0)].copy(); photo = True
            elif k == "c": bg, src = self.card(ref, p); label_ok = False; scrim = True
            elif k == "n": bg = self.numscreen(ref, p, si); label_ok = False
            elif k == "x": bg = self.split_shot(ref, p); label_ok = False; photo = True
            if photo and grain:                                              # fine moving grain on photos and footage, never on type or UI
                a_ = np.asarray(bg, dtype=np.int16); g_ = np.random.default_rng(n).normal(0, grain, a_.shape[:2])[..., None]
                bg = Image.fromarray(np.clip(a_ + g_, 0, 255).astype(np.uint8))
            pim = self.presenter_frame(); pbox = None
            if pim is not None and show_p:
                bg.paste(pim, (self.JX, self.JY), pim)
                bb = pim.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
                if bb: pbox = (self.JX + bb[0], self.JY + bb[1], self.JX + bb[2], self.JY + bb[3])
            if hook and tt < self.starts[1] and k != "END": self.draw_hook(bg, hook)
            elif label_ok and not self.name_on(tt): self.draw_label(bg, self.label_at(tt))
            if k != "END":
                if self.name_on(tt) and label_ok and not (hook and tt < self.starts[1]): self.draw_name(bg)   # never over a card, number or insert
                self.draw_source(bg, src)
                if k != "n": self.caption(bg, tt, cap_where, scrim)
            for i_, (ka, A) in enumerate(self.BOXES):                         # two overlays drawn on top of each other
                for kb, B in self.BOXES[i_+1:]:
                    if A[0] < B[2] and A[2] > B[0] and A[1] < B[3] and A[3] > B[1]:
                        viol.append((round(tt, 2), T["raw"], "text over text", *[int(v) for v in B]))
            for why, bb in self.zone.check(self.BOXES, pbox):
                viol.append((round(tt, 2), T["raw"], why, *[int(v) for v in bb]))
            if self.qa and n % int(FPS*1.3) == 0: qa.append(bg.copy())
            enc.stdin.write(bg.tobytes())
        enc.stdin.close(); enc.wait()
        for r in readers.values(): r.close()
        if self.pres: self.pres.kill()
        mix = self.mix(tmp)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "160k", "-t", f"{self.dur:.2f}", "-movflags", "+faststart", str(self.out)], check=True)
        if self.qa: print("qa sheet", zone_sheet(qa, self.zone, self.out.with_name(self.out.stem + "_qa.png")))
        print(f"wrote {self.out} ({self.dur:.1f}s)"); print("safe-zone violations:", len(viol), viol[:6])
        if viol:
            bad = self.out.with_name(self.out.stem + "_SAFEZONE-FAIL.mp4"); self.out.rename(bad)
            json.dump(viol, open(bad.with_suffix(".json"), "w"), indent=0)
            print(f"FAIL: renamed to {bad.name}; every violation is listed in {bad.with_suffix('.json').name}"); return 2
        return 0


def cmd_segments(a):
    segs, _ = load_words(a.words)
    for i, s in enumerate(segs): print(f"{i:>3}  {s['start']:6.2f}-{s['end']:6.2f}  {s['text'].strip()}")
    return 0


def cmd_check(a):
    try: sl = ShotList(a.shots); need = [(f, x) for f in ("9x16", "4x5") for x in sl.assets(f)]
    except ValueError as e: print("check:", e); return 1
    bad = 0
    for fmt, (lab, p) in need:
        if p is None or not p.exists(): print(f"MISSING [{fmt}] {lab}: {p}"); bad += 1
    segs, _ = load_words(sl.p(sl.d["words"]))
    extra = [i for i in sl.shots if i >= len(segs)]
    if extra: print(f"the shot list names phrases {extra} but the voice has {len(segs)} (0-{len(segs) - 1})"); bad += 1
    print("check:", "ok" if not bad else f"{bad} problem(s)"); return 1 if bad else 0


def cmd_render(a):
    if cmd_check(a): return 1
    sl = ShotList(a.shots); st = Style.load(a.brand_json); print("style:", st.source)
    out_dir = a.out_dir or (sl.base/"out"); rc = 0
    for fmt in (["9x16", "4x5"] if a.ratio == "both" else [a.ratio]): rc = max(rc, Render(sl, st, fmt, out_dir, a.qa).run())
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("segments", help="print the numbered phrases of a Whisper word json"); s.add_argument("words")
    s = sp.add_parser("check", help="validate a shot list without rendering"); s.add_argument("shots")
    s = sp.add_parser("render", help="render one or both ratios")
    s.add_argument("shots"); s.add_argument("--ratio", default="both", choices=["9x16", "4x5", "both"])
    s.add_argument("--out-dir"); s.add_argument("--qa", action="store_true", help="also write a contact sheet with the forbidden areas shaded")
    s.add_argument("--brand-json", help="brand.json to style from instead of the active brand")
    a = ap.parse_args()
    sys.exit({"segments": cmd_segments, "check": cmd_check, "render": cmd_render}[a.cmd](a))


if __name__ == "__main__":
    main()
