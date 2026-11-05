#!/usr/bin/env python3
"""Type text, character by character with a caret, into any UI element (a search box, an address bar, a chat
input, a form field) laid over a background clip or still. Optional check-marked lines and small print under it.

  python3 toolbox/type_overlay.py --bg clip.mp4 --phrases "First phrase|Second phrase|Final phrase" \
         [--element box.png --text-box 0.08,0.22,0.92,0.78] [--lines "One|Two|Three"] [--fine "Small print."] \
         [--duration 7.5] [--shown 5.5] [--rate 19] [--bg-start 0 --bg-len 3.7] [--yanchor 0.02] [--pad-top 0]
         [--ratio 9x16|4x5|both] [--out typed] [--brand-json F]

--element is any PNG with transparency, e.g. a real UI element captured with
  capture_page.py <page> --selector "form input" --transparent --out box.png
Without it a plain rounded box is drawn in the brand's end-card colours. --text-box is where the typing sits
inside the element, as shares of the element's width and height.

Timing rule: the final phrase must be completely typed while the clip is still on screen. --shown is how many
seconds the viewer will actually see (a later cut may use only part of the clip); the tool speeds the typing up
until the final phrase is done 0.9 s before --shown, and stops with an error if that needs more than --max-rate.
The last phrase then holds with a blinking caret. Every text box is checked against the safe zone (exit 2)."""
import argparse, math, pathlib, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style
from safezone import Zone

FPS = 30
def ease(p): p = min(1, max(0, p)); return 1 - (1 - p)**3


def schedule(phrases, rate, hold, gap, del_rate, start):
    """-> list of (t, text) keyframes and the time the last phrase finishes typing"""
    ev = []; t = start
    for k, ph in enumerate(phrases):
        for i in range(len(ph) + 1): ev.append((t + i/rate, ph[:i]))
        t += len(ph)/rate; done = t
        if k == len(phrases) - 1: break
        t += hold
        for i in range(len(ph), -1, -1): ev.append((t + (len(ph) - i)/del_rate, ph[:i]))
        t += len(ph)/del_rate + gap
    return ev, done


def text_at(ev, t):
    cur = ""
    for tt, s in ev:
        if tt <= t: cur = s
        else: break
    return cur


def load_bg(a, W, H, N):
    src = pathlib.Path(a.bg); sc = max(W/1080, H/1920)*1.24; BW, BH = int(1080*sc) + 1, int(1920*sc) + 1
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        im = Image.open(src).convert("RGB"); s2 = max(BW/im.width, BH/im.height); im = im.resize((int(im.width*s2) + 1, int(im.height*s2) + 1), Image.LANCZOS)
        return [im.crop((0, 0, BW, BH))]*1, BW, BH
    ln = a.bg_len or float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]).decode()) - a.bg_start
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a.bg_start), "-t", str(ln), "-i", str(src), "-vf",
                          f"setpts={a.duration/ln:.4f}*PTS,fps={FPS},scale={BW}:{BH}:force_original_aspect_ratio=increase,crop={BW}:{BH}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    fr = [Image.frombytes("RGB", (BW, BH), raw[i*BW*BH*3:(i+1)*BW*BH*3]) for i in range(len(raw)//(BW*BH*3))]
    return fr or [Image.new("RGB", (BW, BH))], BW, BH


def render(a, st, fmt):
    W, H = (1080, 1920) if fmt == "9x16" else (1080, 1350); zone = Zone.for_frame(W, H, st); N = int(a.duration*FPS)
    phrases = [p for p in a.phrases.split("|") if p]; rate = a.rate; shown = a.shown or a.duration
    while True:
        ev, done = schedule(phrases, rate, a.hold, a.gap, rate*3, a.start)
        if done <= shown - 0.9: break
        rate *= 1.05
        if rate > a.max_rate:
            sys.exit(f"the final phrase cannot finish typing inside {shown:.1f}s shown even at {a.max_rate} chars/s: "
                     f"cut a phrase, shorten one, or show the clip longer")
    print(f"{fmt}: typing at {rate:.1f} chars/s, final phrase done at {done:.2f}s (shown {shown:.1f}s)")
    FR, BW, BH = load_bg(a, W, H, N)
    if a.pad_top:
        def pad(im):
            top = im.crop((0, 0, BW, 60)).resize((BW, a.pad_top + 60), Image.BILINEAR).filter(ImageFilter.GaussianBlur(18))
            c = Image.new("RGB", (BW, BH + a.pad_top)); c.paste(top, (0, 0)); c.paste(im, (0, a.pad_top)); return c.crop((0, 0, BW, BH))
        FR = [pad(f) for f in FR]
    shade = Image.new("L", (1, H))
    for y in range(H): shade.putpixel((0, y), int(a.shade*max(0, 1 - y/(0.66*H))**1.1))
    shade = shade.resize((W, H)); shade_col = st.color("shade")
    # the element
    if a.element:
        el = Image.open(a.element).convert("RGBA"); bb = el.getchannel("A").getbbox() or (0, 0, el.width, el.height); el = el.crop(bb)
        s = min(0.84*W/el.width, 1e9); el = el.resize((int(el.width*s), int(el.height*s)), Image.LANCZOS)
    else:
        ew, eh = int(0.80*W), int(0.085*H if fmt == "9x16" else 0.10*H); el = Image.new("RGBA", (ew, eh), (0, 0, 0, 0))
        ImageDraw.Draw(el).rounded_rectangle([0, 0, ew - 1, eh - 1], radius=eh//2, fill=st.color("endcard_box") + (255,))
    tb = [float(v) for v in a.text_box.split(",")]; tx0, ty0, tx1, ty1 = tb[0]*el.width, tb[1]*el.height, tb[2]*el.width, tb[3]*el.height
    ft = st.font("regular", (ty1 - ty0)*0.62); ink = st.color("endcard_ink")
    ex = (W - el.width)//2; cy = a.pos_y*H if a.pos_y else zone.top + (0.155 if fmt == "9x16" else 0.20)*H; ey = int(cy - el.height/2)
    lines = [x for x in (a.lines or "").split("|") if x]; fl = st.font("regular", 0.040*W); ff = st.font("regular", 0.027*W)
    out = pathlib.Path(f"{a.out}_{fmt}.mp4"); out.parent.mkdir(parents=True, exist_ok=True); viol = []
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for n in range(N):
        t = n/FPS; im = FR[min(len(FR) - 1, n)]; z = 1 + 0.03*n/N; cw, ch = int(W/z), int(H/z)
        x = (BW - cw)//2; y = int((BH - ch)*a.yanchor); bg = im.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)
        bg.paste(Image.new("RGB", (W, H), shade_col), (0, 0), shade); bg = bg.convert("RGBA"); boxes = []
        k = ease(t/0.45); rise = int(40*(1 - k)); e = el.copy()
        if k < 1: e.putalpha(e.getchannel("A").point(lambda v, k=k: int(v*k)))
        sh = Image.new("RGBA", e.size, (0, 0, 0, 0)); sh.putalpha(e.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v*0.55)))
        bg.alpha_composite(sh, (ex, ey + rise + 4)); bg.alpha_composite(e, (ex, ey + rise))
        d = ImageDraw.Draw(bg); s = text_at(ev, t); blink = t < done or (n//16) % 2 == 0
        while s and d.textlength(s, font=ft) > tx1 - tx0: s = s[1:]            # long text scrolls left like a real field
        bx, by = ex + tx0, ey + rise + ty0 + (ty1 - ty0 - ft.size)/2
        d.text((bx, by), s, font=ft, fill=ink + (int(255*k),))
        if s: boxes.append(("text", d.textbbox((bx, by), s, font=ft)))
        if blink and k >= 1:
            cx_ = bx + d.textlength(s, font=ft) + 3; d.line([(cx_, by + ft.size*0.05), (cx_, by + ft.size*1.05)], fill=ink + (255,), width=max(2, int(ft.size*0.07)))
        ly = ey + el.height + int(0.03*H)
        if lines:
            colw = max(d.textlength(it, font=fl) for it in lines) + 0.075*W; lx = int((W - colw)/2)
            for i, it in enumerate(lines):
                p = ease((t - 0.9 - 0.22*i)/0.35)
                if p <= 0: continue
                yy = ly + i*int(fl.size*1.55); r = int(fl.size*0.46); ccx, ccy = lx + r, yy + fl.size*0.60
                L = Image.new("RGBA", bg.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(L); kk = min(1, p*1.3)
                a0 = (ccx - r*0.55, ccy + r*0.02); b0 = (ccx - r*0.10, ccy + r*0.40); c0 = (ccx + r*0.60, ccy - r*0.40)
                seg = [a0, (a0[0] + (b0[0] - a0[0])*min(1, kk*2), a0[1] + (b0[1] - a0[1])*min(1, kk*2))]
                if kk > 0.5: seg += [(b0[0] + (c0[0] - b0[0])*(kk - 0.5)*2, b0[1] + (c0[1] - b0[1])*(kk - 0.5)*2)]
                ld.line(seg, fill=st.color("endcard_check") + (int(255*p),), width=max(4, int(r*0.30)), joint="curve"); bg.alpha_composite(L)
                tpos = (lx + 2*r + 0.025*W, yy + 10*(1 - p)); d = ImageDraw.Draw(bg)
                d.text(tpos, it, font=fl, fill=(255, 255, 255, int(255*p)), stroke_width=1, stroke_fill=(0, 0, 0, int(120*p)))
                boxes.append(("text", d.textbbox(tpos, it, font=fl)))
            ly += len(lines)*int(fl.size*1.55) + int(0.014*H)
        if a.fine:
            q = ease((t - 1.8)/0.5)
            if q > 0:
                d = ImageDraw.Draw(bg); words = a.fine.split(); rows = [""]
                for w_ in words:
                    if d.textlength((rows[-1] + " " + w_).strip(), font=ff) <= 0.70*W: rows[-1] = (rows[-1] + " " + w_).strip()
                    else: rows.append(w_)
                for j, row in enumerate(rows):
                    pos = ((W - d.textlength(row, font=ff))/2, ly + j*ff.size*1.4)
                    d.text(pos, row, font=ff, fill=(255, 255, 255, int(215*q))); boxes.append(("text", d.textbbox(pos, row, font=ff)))
        for why, bb in zone.check(boxes): viol.append((round(t, 2), why, [int(v) for v in bb]))
        enc.stdin.write(bg.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()
    print(f"wrote {out} ({a.duration:.1f}s); safe-zone violations: {len(viol)} {viol[:4]}")
    return 2 if viol else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bg", required=True, help="background clip or still"); ap.add_argument("--phrases", required=True, help='"one|two|three": typed, held, deleted; the last one stays')
    ap.add_argument("--element", help="PNG of the UI element (transparent background)"); ap.add_argument("--text-box", default="0.08,0.22,0.92,0.78")
    ap.add_argument("--lines", help='"a|b|c" lines with drawn-on check marks under the element'); ap.add_argument("--fine", help="small print under everything")
    ap.add_argument("--duration", type=float, default=7.5); ap.add_argument("--shown", type=float, help="seconds the viewer will actually see (default: --duration)")
    ap.add_argument("--rate", type=float, default=19.0, help="characters per second to start from"); ap.add_argument("--max-rate", type=float, default=30.0)
    ap.add_argument("--hold", type=float, default=1.3); ap.add_argument("--gap", type=float, default=0.6); ap.add_argument("--start", type=float, default=0.5)
    ap.add_argument("--bg-start", type=float, default=0.0); ap.add_argument("--bg-len", type=float, help="seconds of the clip stretched over --duration")
    ap.add_argument("--yanchor", type=float, default=0.02, help="vertical crop anchor of the background, 0 top .. 1 bottom")
    ap.add_argument("--pad-top", type=int, default=0, help="px of blurred sky added above the background, to push the subject down")
    ap.add_argument("--pos-y", type=float, help="element centre as share of height (default: just inside the safe zone top)")
    ap.add_argument("--shade", type=int, default=205, help="strength 0-255 of the top shade that keeps white type readable")
    ap.add_argument("--ratio", default="both", choices=["9x16", "4x5", "both"]); ap.add_argument("--out", default="typed"); ap.add_argument("--brand-json")
    a = ap.parse_args(); st = Style.load(a.brand_json); rc = 0
    for fmt in (["9x16", "4x5"] if a.ratio == "both" else [a.ratio]): rc = max(rc, render(a, st, fmt))
    sys.exit(rc)


if __name__ == "__main__":
    main()
