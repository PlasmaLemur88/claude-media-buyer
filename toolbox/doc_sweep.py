#!/usr/bin/env python3
"""Sweep through a document as a video: pages in a simple viewer, the camera travelling page to page and zooming
onto the lines that matter while a marker highlight draws across them. Works on any page images: the output of
redact.py, pdftoppm pages, or a full-page web capture from capture_page.py (a tall page scrolls instead of fitting).

  python3 toolbox/doc_sweep.py --pages red/ [--words red/words.json] [--highlight "76%" --highlight "2,984 sq ft"]
         [--order 3,4,6] [--title "Report.pdf"] [--hold 1.2] [--ratio 9x16|4x5|both] [--out sweep] [--brand-json F]

Always redact first (redact.py) when a document carries anything about a real person or property. Highlights are
found in words.json (written by redact.py); a highlight that is not found stops the run. The result is an insert
for compose_shots.py (fit "rate": it is time-fitted into the span it is given, 0.8x-1.3x)."""
import argparse, json, math, pathlib, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style

FPS = 30
def ease(p): p = min(1, max(0, p)); return 1 - (1 - p)**3
def eio(p): p = min(1, max(0, p)); return 0.5 - 0.5*math.cos(math.pi*p)


def find_box(words, phrase):
    q = [re.sub(r"[^\w%$.,]", "", x.lower()) for x in phrase.split()]
    ws = words; tk = [re.sub(r"[^\w%$.,]", "", w[4].lower()) for w in ws]
    for i in range(len(tk) - len(q) + 1):
        if all(tk[i+k].strip(".,") == q[k].strip(".,") for k in range(len(q))):
            sel = ws[i:i+len(q)]; return (min(w[0] for w in sel), min(w[1] for w in sel), max(w[2] for w in sel), max(w[3] for w in sel))
    return None


def render(a, st, fmt):
    FW, FH = (1080, 1920) if fmt == "9x16" else (1080, 1350)
    ztop, zbot, zl, zr = st.zone(FW, FH)
    pdir = pathlib.Path(a.pages); files = sorted(p for p in pdir.glob("*.png") if not p.name.endswith("_qa.png"))
    words = {x["file"]: x for x in json.load(open(a.words))} if a.words else {}
    if words: files = [pdir/f for f in words]                            # the order redact.py wrote them in
    order = [int(x) - 1 for x in a.order.split(",")] if a.order else list(range(len(files)))
    PAGES = [Image.open(files[i]).convert("RGB") for i in order]; NP = len(PAGES)
    TB = int(0.085*FW); VY0 = int(ztop + TB); PW = int(zr - zl); XC = (zl + zr)/2 - FW/2; GAP = int(0.03*FW)
    PH = [int(PW*p.height/p.width) for p in PAGES]; TOPS = [sum(PH[:j]) + j*GAP for j in range(NP)]
    PRE = 1.9; PS = [p.resize((int(PW*PRE), int(h*PRE)), Image.LANCZOS) for p, h in zip(PAGES, PH)]
    view_h = FH - VY0; SCY = (VY0 + zbot)/2
    def P(j, fx, fy): return (fx*PW, TOPS[j] + fy*PH[j])
    # highlights: (page j, box as share of page, t0, t1)
    HL = []; KF = []; t = 0.0
    for j in range(NP):
        tall = PH[j] > view_h*1.4; fitz = 1.0 if tall else min(1.0, (zbot - VY0)/PH[j]*0.98)
        if j == 0: KF.append((t, j, .5, (view_h/2)/PH[j] if tall else .5, fitz)); t += 0.4
        else: t += 0.8; KF.append((t, j, .5, (view_h/2)/PH[j] if tall else .5, fitz))
        t += a.hold; KF.append((t, j, .5, (view_h/2)/PH[j] if tall else .5, fitz))
        src_name = files[order[j]].name; ws = words.get(src_name, {}).get("words", [])
        for h in a.highlight or []:
            b = find_box(ws, h) if ws else None
            if not b: continue
            pw_, ph_ = PAGES[j].width, PAGES[j].height; fb = (b[0]/pw_, b[1]/ph_, b[2]/pw_, b[3]/ph_)
            z = min(1.9, max(1.1, 0.62/max(0.05, fb[2] - fb[0])))
            cx, cy = (fb[0] + fb[2])/2, (fb[1] + fb[3])/2
            t += 0.7; KF.append((t, j, cx, cy, z)); HL.append((j, fb, t - 0.2, t + 1.3, h)); t += 1.4; KF.append((t, j, cx, cy, z))
        if tall:
            t += max(1.0, a.hold); KF.append((t, j, .5, 1 - (view_h/2)/PH[j], fitz))
    found = {h[4] for h in HL}
    for h in a.highlight or []:
        if h not in found: sys.exit(f"highlight {h!r} not found in words.json on the chosen pages")
    t += 0.4; KF.append((t, KF[-1][1], KF[-1][2], KF[-1][3], KF[-1][4])); DUR = t; N = int(DUR*FPS)
    def cam(tt):
        for a_, b_ in zip(KF, KF[1:]):
            if a_[0] <= tt <= b_[0]:
                p = eio((tt - a_[0])/max(0.01, b_[0] - a_[0])); A = P(a_[1], a_[2], a_[3]); B = P(b_[1], b_[2], b_[3]); z = a_[4] + (b_[4] - a_[4])*p
                if a_[1] != b_[1]: z -= 0.04*math.sin(math.pi*p)       # pull back a little while travelling between pages
                return A[0] + (B[0] - A[0])*p, A[1] + (B[1] - A[1])*p, z, (a_[1] if p < 0.5 else b_[1])
        k = KF[-1]; x, y = P(k[1], k[2], k[3]); return x, y, k[4], k[1]
    hic = st.color("highlight")
    def page_img(j, tt):
        live = [h for h in HL if h[0] == j and h[2] - 0.05 < tt < h[3] + 0.6]
        if not live: return PS[j]
        im = PS[j].copy(); W_, H_ = im.size
        for _, fb, t0, t1, _ in live:
            p = ease((tt - t0)/0.40); al = 1 - ease((tt - t1)/0.5)
            x0, y0, x1, y1 = fb[0]*W_, fb[1]*H_, fb[2]*W_, fb[3]*H_; h = y1 - y0; y0 += h*0.08
            bx = (int(x0 - 10), int(y0), int(x0 - 10 + (x1 - x0 + 20)*p), int(y1))
            if bx[2] - bx[0] < 4: continue
            reg = im.crop(bx); mk = Image.new("RGB", reg.size, (255, 255, 255))
            ImageDraw.Draw(mk).rounded_rectangle([0, 0, reg.width - 1, reg.height - 1], radius=int(reg.height*0.45), fill=hic)
            im.paste(Image.blend(reg, ImageChops.multiply(reg, mk), al), bx[:2])
        return im
    BG, BAR, TXT = st.color("viewer_bg"), st.color("viewer_bar"), st.color("viewer_ink"); fT = st.font("regular", 0.036*FW); fS = st.font("regular", 0.030*FW)
    out = pathlib.Path(f"{a.out}_{fmt}.mp4"); out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{FW}x{FH}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for n in range(N):
        tt = n/FPS; cx, cy, z, cur = cam(tt); fr = Image.new("RGB", (FW, FH), BG)
        dw, dh = FW/z, view_h/z; wx0, wy0 = cx - dw/2, cy - (SCY - VY0)/z
        for j in range(NP):
            top = TOPS[j]
            if top > wy0 + dh or top + PH[j] < wy0: continue
            ix0, iy0 = max(wx0, 0), max(wy0, top); ix1, iy1 = min(wx0 + dw, PW), min(wy0 + dh, top + PH[j])
            if ix1 <= ix0 or iy1 <= iy0: continue
            src = page_img(j, tt); crop = src.crop((int(ix0*PRE), int((iy0 - top)*PRE), int(ix1*PRE), int((iy1 - top)*PRE)))
            ox, oy = (ix0 - wx0)*z + XC, VY0 + (iy0 - wy0)*z; tw_, th_ = max(1, int((ix1 - ix0)*z)), max(1, int((iy1 - iy0)*z))
            sh = Image.new("RGBA", (tw_ + 60, th_ + 60), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle([30, 36, tw_ + 30, th_ + 36], fill=(0, 0, 0, 120))
            sh = sh.filter(ImageFilter.GaussianBlur(14)); fr.paste(sh, (int(ox - 30), int(oy - 30)), sh); fr.paste(crop.resize((tw_, th_), Image.BILINEAR), (int(ox), int(oy)))
        d = ImageDraw.Draw(fr); d.rectangle([0, 0, FW, VY0], fill=BAR); d.line([(0, VY0), (FW, VY0)], fill=tuple(min(255, c + 14) for c in BAR), width=2)
        y = int(ztop + TB*0.22); x = int(zl) + 10
        d.line([(x + 14, y + 10), (x, y + 26), (x + 14, y + 42)], fill=TXT, width=5)
        ix = x + 50; d.rounded_rectangle([ix, y + 2, ix + 34, y + 48], radius=4, outline=TXT, width=3)
        d.text((ix + 52, y + 4), a.title, font=fT, fill=TXT)
        pg = f"{order[cur] + 1} of {len(files)}"; d.text((zr - d.textlength(pg, font=fS), y + 10), pg, font=fS, fill=tuple(int(c*0.7) for c in TXT))
        enc.stdin.write(fr.tobytes())
    enc.stdin.close(); enc.wait(); print(f"wrote {out} ({DUR:.1f}s, {NP} pages, {len(HL)} highlights)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", required=True, help="folder of page PNGs"); ap.add_argument("--words", help="words.json from redact.py")
    ap.add_argument("--highlight", action="append", help="exact phrase to zoom onto and mark; repeat for more")
    ap.add_argument("--order", help="1-based page numbers to show, in order, e.g. 3,4,6"); ap.add_argument("--title", default="Document.pdf")
    ap.add_argument("--hold", type=float, default=1.2, help="seconds each page holds at fit"); ap.add_argument("--ratio", default="both", choices=["9x16", "4x5", "both"])
    ap.add_argument("--out", default="sweep", help="output stem; _9x16.mp4 / _4x5.mp4 are added"); ap.add_argument("--brand-json")
    a = ap.parse_args(); st = Style.load(a.brand_json)
    if a.highlight and not a.words: sys.exit("--highlight needs --words (words.json from redact.py)")
    for fmt in (["9x16", "4x5"] if a.ratio == "both" else [a.ratio]): render(a, st, fmt)


if __name__ == "__main__":
    main()
