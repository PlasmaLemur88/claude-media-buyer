#!/usr/bin/env python3
"""Record a website interaction keystroke by keystroke, then build it into a smooth video.

Screen recordings of a live site stutter and drop frames. This takes one full-resolution screenshot per keystroke
and per step (with a hold time each), records where any private element was on every shot, and assembles the
shots at 30 fps with a gentle push-in. Use it for a product demo: typing into a search or form, picking a
suggestion, the result appearing.

  shoot:  python3 toolbox/record_interaction.py shoot <url-or-file> --steps steps.json --dir demo/ [--mobile "iPhone 14 Pro"]
            [--private "input" --private "[role=option]"]
  build:  python3 toolbox/record_interaction.py build --dir demo/ [--ratio 9x16|4x5|both] [--blur] [--cover x0,y0,x1,y1] [--focus-y 0.30]

steps.json is a list; each step is one of:
  {"shot": "home", "hold": 0.6}                         screenshot and hold it
  {"click": "css selector", "hold": 0.25}               click, then screenshot
  {"type": "text to type", "into": "css", "hold": 0.066} one screenshot per character
  {"pick": "visible text", "among": "li, [role=option]", "hold": 0.3}   click the suggestion containing the text
  {"hover": "css", "hold": 0.2}
  {"wait_text": "visible text", "timeout": 15000}       wait (no screenshot)
  {"wait": 500}                                         wait ms (no screenshot)

--private selectors are measured on every shot; `build --blur` blurs them (typed street numbers, other people's
addresses in an autocomplete list, account names). Blurring is off by default; turn it on whenever real people's
data could be on screen. `--cover` paints a fixed region with its own edge colour (e.g. a chat bubble)."""
import argparse, asyncio, json, math, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brandstyle import Style
from PIL import Image, ImageFilter


def target_url(t):
    p = pathlib.Path(t)
    return p.resolve().as_uri() if p.exists() else t


async def shoot(a):
    from playwright.async_api import async_playwright
    steps = json.load(open(a.steps)); O = pathlib.Path(a.dir); (O/"shots").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(**pw.devices[a.mobile]) if a.mobile else await b.new_context(viewport={"width": a.width, "height": a.height}, device_scale_factor=a.dpr)
        pg = await ctx.new_page()
        await pg.goto(target_url(a.target), wait_until="networkidle", timeout=60000); await pg.wait_for_timeout(a.wait)
        dpr = await pg.evaluate("devicePixelRatio"); seq = []

        async def private_boxes():
            out = []
            for sel in a.private or []:
                loc = pg.locator(sel)
                for i in range(await loc.count()):
                    try:
                        bb = await loc.nth(i).bounding_box()
                        if bb and await loc.nth(i).is_visible(): out.append([bb["x"]*dpr, bb["y"]*dpr, (bb["x"] + bb["width"])*dpr, (bb["y"] + bb["height"])*dpr])
                    except Exception: pass
            return out

        async def shot(tag, hold):
            f = O/"shots"/f"s{len(seq):04d}.png"; await pg.screenshot(path=str(f))
            seq.append({"f": f.name, "tag": tag, "hold": hold, "private": await private_boxes()})

        for s in steps:
            if "shot" in s: await shot(s["shot"], s.get("hold", 0.5))
            elif "click" in s:
                await pg.locator(s["click"]).first.click(); await pg.wait_for_timeout(s.get("settle", 250)); await shot("click", s.get("hold", 0.25))
            elif "type" in s:
                inp = pg.locator(s.get("into", "input")).first
                for ch in s["type"]:
                    await inp.press_sequentially(ch); await pg.wait_for_timeout(s.get("settle", 30)); await shot("type", s.get("hold", 0.066))
            elif "pick" in s:
                opt = pg.locator(s.get("among", "li, [role=option]")).filter(has_text=s["pick"]).first
                await opt.wait_for(state="visible", timeout=s.get("timeout", 15000)); await pg.wait_for_timeout(300)
                await shot("suggest", s.get("hold_before", 0.9)); await opt.click(); await pg.wait_for_timeout(s.get("settle", 150))
                await shot("picked", s.get("hold", 0.3))
            elif "hover" in s:
                await pg.locator(s["hover"]).first.hover(); await pg.wait_for_timeout(120); await shot("hover", s.get("hold", 0.2))
            elif "wait_text" in s: await pg.get_by_text(s["wait_text"]).first.wait_for(state="visible", timeout=s.get("timeout", 15000))
            elif "wait" in s: await pg.wait_for_timeout(s["wait"])
            else: sys.exit(f"unknown step {s}")
        json.dump({"seq": seq, "dpr": dpr}, open(O/"seq.json", "w"), indent=1)
        print(f"shots {len(seq)}, {sum(x['hold'] for x in seq):.1f}s of demo, private boxes on {sum(1 for x in seq if x['private'])} shots -> {O/'seq.json'}")
        await b.close()


def build(a):
    O = pathlib.Path(a.dir); J = json.load(open(O/"seq.json")); seq = J["seq"]
    covers = [tuple(map(int, c.split(","))) for c in (a.cover or [])]
    fmts = ["9x16", "4x5"] if a.ratio == "both" else [a.ratio]
    for fmt in fmts:
        W, H = (1080, 1920) if fmt == "9x16" else (1080, 1350); cache = {}
        zt, _, zl, zr = Style.load(a.brand_json).zone(W, H); top = int(a.top*H) if a.top is not None else int(zt)
        def frame(item):
            k = item["f"]
            if k not in cache:
                im = Image.open(O/"shots"/k).convert("RGB")
                for x0, y0, x1, y1 in covers:
                    im.paste(im.getpixel((max(0, x0 - 4), (y0 + y1)//2)), (x0, y0, x1, y1))
                if a.blur:
                    for x0, y0, x1, y1 in item["private"]:
                        bx = (max(0, int(x0)), max(0, int(y0)), min(im.width, int(x1)), min(im.height, int(y1)))
                        if bx[2] > bx[0] and bx[3] > bx[1]: im.paste(im.crop(bx).filter(ImageFilter.GaussianBlur(a.blur_radius)), bx[:2])
                sw = W if a.bleed else int(zr - zl); sc = sw/im.width; im = im.resize((sw, int(im.height*sc)), Image.LANCZOS)
                fr = Image.new("RGB", (W, H), im.getpixel((10, im.height - 10))); fr.paste(im.getpixel((10, 4)), (0, 0, W, top))
                fr.paste(im, (0 if a.bleed else int(zl), top)); cache[k] = fr                      # the screen starts below the platform's top UI
            return cache[k]
        total = sum(s["hold"] for s in seq); N = int(round(total*30)); bounds = []; t = 0.0
        for s in seq: bounds.append((t, t + s["hold"], s)); t += s["hold"]
        out = O/f"{a.name}_{fmt}.mp4"
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
                                "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
        for n in range(N):
            tt = n/30; s = next((b[2] for b in bounds if b[0] <= tt < b[1]), seq[-1]); fr = frame(s)
            z = 1 + a.push*(0.5 - 0.5*math.cos(math.pi*min(1, tt/total))); cx, cy = W/2, H*a.focus_y; cw, ch = W/z, H/z
            y0 = max(0, min(H - ch, cy - ch*a.focus_y)) if a.push else 0
            enc.stdin.write(fr.crop((int(cx - cw/2), int(y0), int(cx + cw/2), int(y0 + ch))).resize((W, H), Image.BICUBIC).tobytes())
        enc.stdin.close(); enc.wait(); print("wrote", out, f"{total:.2f}s", "(private data blurred)" if a.blur else "(no blur)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("shoot", help="take the screenshots"); s.add_argument("target"); s.add_argument("--steps", required=True); s.add_argument("--dir", required=True)
    s.add_argument("--mobile", help='Playwright device, e.g. "iPhone 14 Pro"'); s.add_argument("--width", type=int, default=1200)
    s.add_argument("--height", type=int, default=1500); s.add_argument("--dpr", type=float, default=2); s.add_argument("--wait", type=int, default=1500)
    s.add_argument("--private", action="append", help="CSS selector measured on every shot so build --blur can hide it")
    s = sp.add_parser("build", help="assemble the shots into a video"); s.add_argument("--dir", required=True)
    s.add_argument("--ratio", default="both", choices=["9x16", "4x5", "both"]); s.add_argument("--name", default="interaction")
    s.add_argument("--blur", action="store_true", help="blur every --private element recorded at shoot time")
    s.add_argument("--blur-radius", type=int, default=14); s.add_argument("--cover", action="append", help="x0,y0,x1,y1 in screenshot px, painted over")
    s.add_argument("--focus-y", type=float, default=0.30, help="where the push-in aims, share of height"); s.add_argument("--push", type=float, default=0.10)
    s.add_argument("--top", type=float, help="where the screen's top edge sits, share of height (default: the safe-zone top)"); s.add_argument("--brand-json")
    s.add_argument("--bleed", action="store_true", help="screen fills the full width (default: it fits between the safe-zone edges)")
    a = ap.parse_args()
    if a.cmd == "shoot": asyncio.run(shoot(a))
    else: build(a)


if __name__ == "__main__":
    main()
