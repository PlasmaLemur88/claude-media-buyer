#!/usr/bin/env python3
"""Brand styling for the presenter-news format. Every font, colour, size and position the presenter tools draw
comes from here, so no tool holds a brand string.

Lookup order for each value:
  1. the `presenter` section of the active brand's brand.json (brands/<slug>/brand.json, slug in .current_brand),
     or of the file passed with --brand-json
  2. a few generic brand fields (fonts.files, palettes.dark.accent) when the presenter section leaves a gap
  3. the neutral defaults in DEFAULTS below

    python3 presenter/brandstyle.py            # print the resolved style for the active brand
    python3 presenter/brandstyle.py --brand-json brands/acme/brand.json

In code:
    from brandstyle import Style
    st = Style.load()                 # or Style.load("path/to/brand.json")
    f = st.font("heavy", 64)          # PIL font
    st.color("pill_bg")               # (r, g, b)
"""
import argparse, copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent          # the engine root

DEFAULTS = {
    # font files (TTF/OTF), paths relative to the brand folder (assets/fonts/x.ttf) or absolute. "" = system fallback.
    "fonts": {"heavy": "", "bold": "", "regular": "", "light": ""},
    "colors": {
        "pill_bg": "#FFFFFF", "pill_ink": "#000000",          # hook, section labels and the name card
        "caption": "#FFFFFF", "caption_stroke": "#000000",    # spoken captions
        "number": "#FFFFFF",                                  # count-up number screens
        "shade": "#0A1628",                                   # top shade behind number-screen text
        "scrim": "#191614",                                   # blurred band behind captions on busy shots
        "source_bg": "#000000", "source_ink": "#FFFFFF",      # "Outlet · date" pill on article cards
        "highlight": "#FFDE5C",                               # marker highlight in the document sweep
        "endcard_box": "#FFFFFF", "endcard_ink": "#111111", "endcard_check": "#FFFFFF",
        "viewer_bar": "#38383C", "viewer_bg": "#262629", "viewer_ink": "#ECECEE",
    },
    "presenter": {
        "side": "left",                                       # lower corner the cutout lives in: left | right
        "width": {"9x16": 0.40, "4x5": 0.34},                 # share of frame width, one size for the whole ad
        "bottom": {"9x16": 0.78, "4x5": 0.90},                # where the cutout's bottom edge sits, share of height
        "edge_feather": [70, 90],                             # px (at 1080) faded at the cutout's sides / bottom
    },
    # text must stay inside this box (share of frame). 9x16 defaults follow RULES.md (y 290-1240, x 60-940 on 1080x1920).
    "safe_zone": {"9x16": {"top": 0.151, "bottom": 0.646, "left": 0.056, "right": 0.870},
                  "4x5": {"top": 0.06, "bottom": 0.90, "left": 0.04, "right": 0.92}},
    "caption": {"size": 0.056, "stroke": 3, "max_words": 7, "max_chars": 40, "hard_max_words": 10, "lines": 2,
                "replace": {}, "weak_words": ["a", "an", "the", "your", "my", "our", "to", "of", "and", "or", "in", "on", "for",
                                              "with", "that", "if", "at", "from", "but", "so", "is", "are", "you", "it", "can"]},
    "label": {"size": 0.060, "radius": 15, "pad": [24, 15], "uppercase": False},
    "hook": {"size": 0.074, "lines": 3},
    "name_card": {"size": 0.064, "sub_size": 0.034, "seconds": 3.0},
    "number": {"size": 0.27, "label_size": 0.034, "sub_size": 0.056, "count_up": 0.35},
    "grade": {"contrast": 1.05, "saturation": 0.93, "lift": 10, "warm": 0.025, "grain": 5.5},
    "audio": {"speed": 1.0, "voice_eq": "equalizer=f=250:t=q:w=1.0:g=-4,equalizer=f=4000:t=q:w=1.0:g=3",
              "bed": "", "bed_db": -17, "bed_end_lift": 1.9, "lufs": -14, "true_peak": -1.0, "sfx": False},
    "export": {"crf": 21, "maxrate": "4000k", "bufsize": "8000k"},
}

SYSTEM_FONTS = [                                                # tried in order when the brand names no file
    ("/System/Library/Fonts/SFNS.ttf", "variable"),
    ("/System/Library/Fonts/Helvetica.ttc", "helvetica"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "plain"),
    ("C:/Windows/Fonts/arialbd.ttf", "plain"),
]
VAR_NAME = {"heavy": "Heavy", "bold": "Bold", "semibold": "Semibold", "regular": "Regular", "light": "Light"}
HELV_INDEX = {"heavy": 1, "bold": 1, "semibold": 1, "regular": 0, "light": 4}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k.startswith("_"): continue
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = _merge(out[k], v)
        elif v not in ("", None, [], {}) or k not in out: out[k] = v       # empty template values keep the default
    return out


def active_brand_file():
    cur = ROOT / ".current_brand"
    if cur.exists():
        slug = cur.read_text().strip()
        f = ROOT / "brands" / slug / "brand.json"
        if slug and f.exists(): return f
    return None


def hex_rgb(h):
    h = str(h).strip().lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class Style:
    def __init__(self, data, brand_dir=None, source="defaults"):
        self.d = data; self.dir = brand_dir; self.source = source; self._fc = {}

    @classmethod
    def load(cls, path=None):
        f = pathlib.Path(path) if path else active_brand_file()
        if not f or not f.exists():
            return cls(copy.deepcopy(DEFAULTS))
        b = json.loads(f.read_text())
        data = _merge(DEFAULTS, b.get("presenter", {}))
        # gaps filled from generic brand fields
        files = [x.get("file", "") for x in (b.get("fonts", {}) or {}).get("files", []) if str(x.get("file", "")).lower().endswith((".ttf", ".otf", ".ttc"))]
        if files:
            for w in data["fonts"]:
                if not data["fonts"][w]: data["fonts"][w] = files[0]
        acc = ((b.get("palettes") or {}).get("dark") or {}).get("accent")
        if acc and not (b.get("presenter", {}).get("colors", {}) or {}).get("highlight") and str(acc).startswith("#"):
            data["colors"]["highlight"] = acc
        return cls(data, f.parent, str(f))

    def get(self, dotted, default=None):
        v = self.d
        for k in dotted.split("."):
            if not isinstance(v, dict) or k not in v: return default
            v = v[k]
        return v

    def color(self, name):
        return hex_rgb(self.d["colors"][name])

    def path(self, p):
        if not p: return None
        q = pathlib.Path(p)
        if not q.is_absolute() and self.dir: q = self.dir / q
        return q

    def font(self, weight, size):
        from PIL import ImageFont
        size = max(8, int(size)); key = (weight, size)
        if key in self._fc: return self._fc[key]
        f = None; p = self.path(self.d["fonts"].get(weight) or self.d["fonts"].get("regular"))
        if p and p.exists():
            f = ImageFont.truetype(str(p), size)
            try: f.set_variation_by_name(VAR_NAME.get(weight, "Regular"))
            except Exception:
                try:
                    axes = f.get_variation_axes()
                    if axes: f.set_variation_by_axes([{"heavy": 850, "bold": 700, "regular": 400, "light": 300}.get(weight, 400)] + [a.get("default", 0) for a in axes[1:]])
                except Exception: pass
        else:
            for fp, kind in SYSTEM_FONTS:
                if not pathlib.Path(fp).exists(): continue
                if kind == "variable":
                    f = ImageFont.truetype(fp, size)
                    try: f.set_variation_by_name(VAR_NAME.get(weight, "Regular"))
                    except Exception: pass
                elif kind == "helvetica": f = ImageFont.truetype(fp, size, index=HELV_INDEX.get(weight, 0))
                else: f = ImageFont.truetype(fp, size)
                break
            if f is None: f = ImageFont.load_default(size=size)
        self._fc[key] = f; return f

    def zone(self, W, H):
        """(top, bottom, left, right) in px for this frame size"""
        z = self.d["safe_zone"]["9x16" if H / W > 1.6 else "4x5"]
        return z["top"]*H, z["bottom"]*H, z["left"]*W, z["right"]*W


def main():
    ap = argparse.ArgumentParser(description="Print the resolved presenter style (brand.json presenter section over neutral defaults).")
    ap.add_argument("--brand-json", help="brand.json to read instead of the active brand")
    a = ap.parse_args()
    st = Style.load(a.brand_json)
    print("source:", st.source)
    print(json.dumps(st.d, indent=1))


if __name__ == "__main__":
    main()
