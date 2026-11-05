#!/usr/bin/env python3
"""Manage brands: one folder per brand in brands/<slug>/, one of them active.

    python3 scripts/brand.py list              every brand, the active one starred
    python3 scripts/brand.py new <slug>        copy brands/_template to brands/<slug>
    python3 scripts/brand.py use <slug>        make <slug> the active brand
    python3 scripts/brand.py show              print the active brand and its voice flags
    python3 scripts/brand.py check [<slug>]    validate a brand (default: the active one)

A brand folder holds brand.json (the data renderers and scripts read),
BRAND-GUIDE.md (the human guide), configs.mjs (its ads) and assets/ (logos,
fonts, photos, sample audio, word timings). Every field of brand.json is
documented in brands/_template/brand.json.

`use` writes, all gitignored and all overwritten on the next `use`:
  .current_brand                              the active slug
  motion-graphics/src/brand.active.json       brand.json with "assets/x" -> "brand-active/x"
  motion-graphics/src/configs.active.mjs      a copy of the brand's configs.mjs
  motion-graphics/public/brand-active/        a copy of the brand's assets/
  .say_as.active.json                         voice.say_as, for voice.py/readcheck.py --say-as

`check` exits with the number of problems (a blank required field, a missing
file, an invalid brand.json). Blank optional fields are listed, not counted.
Stdlib only.
"""
import argparse
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRANDS = ROOT / "brands"
MG = ROOT / "motion-graphics"
CURRENT = ROOT / ".current_brand"
ACTIVE_JSON = MG / "src" / "brand.active.json"
ACTIVE_CONFIGS = MG / "src" / "configs.active.mjs"
ACTIVE_ASSETS = MG / "public" / "brand-active"
SAY_AS = ROOT / ".say_as.active.json"

REQUIRED = [
    "brand.slug", "brand.name", "brand.file_prefix", "offer.free.cta",
    "palettes.dark.bg", "palettes.dark.ink", "palettes.dark.accent", "palettes.dark.muted", "palettes.dark.dim",
    "palettes.paper.bg", "palettes.paper.ink", "palettes.paper.accent", "palettes.paper.muted", "palettes.paper.dim",
    "fonts.serif", "fonts.sans",
]
BLANK = re.compile(r"^(|UNKNOWN|TODO|TBD|<[^>]*>)$", re.I)
NO_BRAND = "no active brand: run python3 scripts/brand.py use <slug>"


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def active():
    s = CURRENT.read_text().strip() if CURRENT.exists() else ""
    return s or None


def folder(slug):
    d = BRANDS / slug
    if not (d / "brand.json").exists():
        die(f"no brand '{slug}': brands/{slug}/brand.json not found. Brands: {', '.join(slugs()) or 'none'}")
    return d


def slugs():
    return sorted(p.parent.name for p in BRANDS.glob("*/brand.json"))


def load(d):
    return json.loads((d / "brand.json").read_text())


def get(data, dotted):
    for k in dotted.split("."):
        if not isinstance(data, dict) or k not in data:
            return None
        data = data[k]
    return data


def walk(data, path=""):
    """Yield (dotted path, leaf value), skipping keys that start with '_'."""
    if isinstance(data, dict):
        for k, v in data.items():
            if not k.startswith("_"):
                yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, data


def rewrite(data):
    if isinstance(data, dict):
        return {k: rewrite(v) for k, v in data.items()}
    if isinstance(data, list):
        return [rewrite(v) for v in data]
    if isinstance(data, str) and data.startswith("assets/"):
        return "brand-active/" + data[len("assets/"):]
    return data


def luminance(hexcol):
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", hexcol or "")
    if not m:
        return None
    rgb = [int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def cmd_list(_):
    cur = active()
    for s in slugs():
        name = get(load(BRANDS / s), "brand.name") or ""
        print(f"{'*' if s == cur else ' '} {s:<20} {name}")
    if not cur:
        print(f"\n({NO_BRAND})")


def cmd_new(a):
    slug = a.slug
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        die("slug: lowercase letters, digits and hyphens, e.g. acme-coffee")
    dst = BRANDS / slug
    if dst.exists():
        die(f"brands/{slug} already exists")
    shutil.copytree(BRANDS / "_template", dst)
    data = load(dst)
    data.setdefault("brand", {})["slug"] = slug
    (dst / "brand.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"made brands/{slug}/. Fill brand.json and BRAND-GUIDE.md, put logos and fonts in assets/,")
    print(f"then: python3 scripts/brand.py check {slug} && python3 scripts/brand.py use {slug}")


def cmd_use(a):
    d = folder(a.slug)
    data = load(d)
    CURRENT.write_text(a.slug + "\n")
    ACTIVE_JSON.write_text(json.dumps(rewrite(data), indent=2, ensure_ascii=False) + "\n")
    if ACTIVE_ASSETS.exists():
        shutil.rmtree(ACTIVE_ASSETS)
    if (d / "assets").exists():
        shutil.copytree(d / "assets", ACTIVE_ASSETS, ignore=shutil.ignore_patterns(".DS_Store"))
    else:
        ACTIVE_ASSETS.mkdir(parents=True)
    (ACTIVE_ASSETS / "words").mkdir(exist_ok=True)   # Root.tsx reads word timings from here
    cfg = d / "configs.mjs"
    ACTIVE_CONFIGS.write_text(cfg.read_text() if cfg.exists() else
                              f"// brands/{a.slug} has no configs.mjs yet.\nexport const ADS = [];\n")
    SAY_AS.write_text(json.dumps(get(data, "voice.say_as") or {}, indent=2, ensure_ascii=False) + "\n")
    n = sum(1 for p in ACTIVE_ASSETS.rglob("*") if p.is_file())
    if not a.quiet:
        print(f"active brand: {a.slug} ({get(data, 'brand.name')}). {n} asset files synced.")


def cmd_show(_):
    cur = active()
    if not cur:
        die(NO_BRAND)
    data = load(folder(cur))
    v = data.get("voice") or {}
    print(f"active brand   {cur}  ({get(data, 'brand.name')})")
    print(f"folder         brands/{cur}/  (brand.json, BRAND-GUIDE.md, configs.mjs, assets/)")
    print(f"file prefix    {get(data, 'brand.file_prefix')}")
    print(f"guide          brands/{cur}/BRAND-GUIDE.md  <- read it before writing a script")
    if v.get("engine"):
        flags = [v["engine"]]
        if v.get("voice"):
            flags += ["--voice", json.dumps(v["voice"])]
        if v.get("style"):
            flags += ["--style", json.dumps(v["style"])]
        if v.get("speed"):
            flags += ["--speed", str(v["speed"])]
        if v.get("say_as"):
            flags += ["--say-as", SAY_AS.name]
        print(f"voice          python3 scripts/voice.py {' '.join(flags)} --text-file <script.txt> --out <read.wav>")


def cmd_check(a):
    slug = a.slug or active()
    if not slug:
        die(NO_BRAND)
    d = BRANDS / slug
    problems, blanks, notes = [], [], []
    try:
        data = load(d)
    except FileNotFoundError:
        die(f"no brand '{slug}': brands/{slug}/brand.json not found", 1)
    except json.JSONDecodeError as e:
        print(f"brands/{slug}/brand.json is not valid JSON: {e}")
        sys.exit(1)

    for f in REQUIRED:
        v = get(data, f)
        if v is None or (isinstance(v, str) and BLANK.match(v.strip())):
            problems.append(f"required field blank: {f}")
    if get(data, "brand.slug") not in (None, "", slug):
        problems.append(f"brand.slug is '{get(data, 'brand.slug')}' but the folder is brands/{slug}")
    if not (d / "BRAND-GUIDE.md").exists():
        problems.append("BRAND-GUIDE.md missing")

    for path, v in walk(data):
        if isinstance(v, str):
            if v.startswith("assets/") and not (d / v).exists():
                problems.append(f"missing file: {path} = {v}")
            elif BLANK.match(v.strip()) and path not in REQUIRED:
                blanks.append(path)
        elif v is None and not path.startswith("rsvp.sizes"):
            blanks.append(path)

    # every public path a config names must exist
    cfg = d / "configs.mjs"
    if cfg.exists():
        code = "\n".join(ln for ln in cfg.read_text().splitlines()
                         if not ln.lstrip().startswith(("//", "*", "/*")))
        for m in sorted(set(re.findall(r'"((?:brand-active|aerial|audio|footage|img)/[^"]+)"', code))):
            real = d / "assets" / m[len("brand-active/"):] if m.startswith("brand-active/") else MG / "public" / m
            if not real.exists():
                problems.append(f"configs.mjs names a file that does not exist: {m}")
    else:
        notes.append("no configs.mjs: the brand has no ads yet")

    for pal in ("dark", "paper"):
        lb, li = luminance(get(data, f"palettes.{pal}.bg")), luminance(get(data, f"palettes.{pal}.ink"))
        if lb is not None and li is not None:
            ratio = (max(lb, li) + 0.05) / (min(lb, li) + 0.05)
            if ratio < 7:
                notes.append(f"palettes.{pal}: ink on bg is {ratio:.1f}:1, under the 7:1 these formats need")

    print(f"brand {slug}: {len(problems)} problem(s), {len(blanks)} blank field(s)")
    for p in problems:
        print(f"  PROBLEM  {p}")
    for n in notes:
        print(f"  note     {n}")
    if blanks:
        print("  still blank (fill or leave empty on purpose):")
        for b in blanks:
            print(f"           {b}")
    sys.exit(min(len(problems), 255))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("new"); p.add_argument("slug"); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("use"); p.add_argument("slug"); p.add_argument("--quiet", action="store_true"); p.set_defaults(fn=cmd_use)
    sub.add_parser("show").set_defaults(fn=cmd_show)
    p = sub.add_parser("check"); p.add_argument("slug", nargs="?"); p.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
