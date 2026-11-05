#!/bin/bash
# Render every ad of the ACTIVE brand, both ratios, named to convention.
#
#   ./build.sh          # all of them
#   ./build.sh 101      # one
#
# The active brand is set with `python3 scripts/brand.py use <slug>`. Its ads
# are brands/<slug>/configs.mjs; this script re-syncs the brand folder and
# checks it before rendering anything.
#
# Paths and filenames are built from the same fields the compositions are, so a
# render can never land in a folder that disagrees with its config. The
# convention is in docs/80-naming-and-delivery.md:
#
#   <outputRoot>/<personaDir>/<number>-<format-lowercase>-<conceptSlug>/
#     <PREFIX>_<number>_<Persona>_<Format>_<Concept>_<HookStyle>_<OFFER>_<Ratio>.mp4
#
# PREFIX is brand.file_prefix and outputRoot brand.output_root (default
# out/<slug>) in the brand's brand.json.
#
# There is NO version counter. HookStyle (Ask/Tell/About) replaced it, because a
# counter told you two files differed but never what differed.
set -e
cd "$(dirname "$0")"

WANT="${1:-}"

# The active brand: fail loudly before anything renders.
if [ ! -s ../.current_brand ]; then
  echo "no active brand: run python3 scripts/brand.py use <slug>" >&2
  exit 1
fi
SLUG="$(tr -d '[:space:]' < ../.current_brand)"
python3 ../scripts/brand.py use "$SLUG" --quiet   # pick up edits to the brand folder
python3 ../scripts/brand.py check "$SLUG" || {
  echo "brand $SLUG has problems (listed above). Fix them before rendering." >&2
  exit 1
}
echo "brand: $SLUG"
# the shared music bed is generated, not stored
[ -s public/audio/bed_phrygian.wav ] || python3 ../scripts/bed.py >/dev/null

# Read the ad list from the brand's configs rather than duplicating it here. A second
# copy of the list is a second place to forget to update. This is why that file
# is plain JavaScript: node imports it as-is, with nothing installed.
node --input-type=module -e '
import { ADS } from "./src/configs.mjs";
for (const a of ADS) {
  const offer = (a.config.offer ?? "free").toUpperCase();
  console.log([a.number, a.persona, a.personaDir, a.format, a.concept,
               a.conceptSlug, a.hookStyle, offer].join("|"));
}' > .ads.tmp

# Where finished ads land: brand.output_root in brand.json (default
# out/<slug>). It may be a path outside this folder, so the tool and the work
# can live apart.
# OUTROOT=<dir> ./build.sh overrides it for one run.
OUTROOT="${OUTROOT:-$(node --input-type=module -e '
import { BRAND } from "./src/brand.mjs";
console.log(BRAND.outputRoot ?? "out");')}"
OUTROOT="${OUTROOT/#\~/$HOME}"          # expand a leading ~
PREFIX="$(node --input-type=module -e '
import { BRAND } from "./src/brand.mjs";
console.log(BRAND.filePrefix);')"
mkdir -p "$OUTROOT"
echo "output: $OUTROOT"

while IFS='|' read -r num persona pdir format concept slug hookstyle offer; do
  [ -n "$WANT" ] && [ "$WANT" != "$num" ] && continue

  fmt_lc=$(printf '%s' "$format" | tr '[:upper:]' '[:lower:]')
  dir="${OUTROOT}/${pdir}/${num}-${fmt_lc}-${slug}"
  mkdir -p "$dir"
  base="${PREFIX}_${num}_${persona}_${format}_${concept}_${hookstyle}_${offer}"
  echo "--- $num $persona $format $hookstyle $offer ---"

  npx remotion render "${format}${num}-${hookstyle}-${offer}-9x16" \
    "${dir}/${base}_9x16.mp4" --log=error
  npx remotion render "${format}${num}-${hookstyle}-${offer}-4x5" \
    "${dir}/${base}_4x5.mp4" --log=error
done < .ads.tmp
rm -f .ads.tmp

echo
# Report REAL durations and sizes. Never report a length you did not measure.
#
# ffprobe: prefer the system one, fall back to the copy Remotion already ships
# in its compositor package. That fallback is the reason the two ready formats
# need nothing but Node — no Homebrew, no separate ffmpeg install. The bundled
# binary needs its own dylibs on the library path, hence DYLD_LIBRARY_PATH.
COMP=$(ls -d node_modules/@remotion/compositor-* 2>/dev/null | head -1)
if command -v ffprobe >/dev/null 2>&1; then
  probe() { ffprobe "$@"; }
elif [ -n "$COMP" ] && [ -x "$COMP/ffprobe" ]; then
  probe() { DYLD_LIBRARY_PATH="$COMP" "$COMP/ffprobe" "$@"; }
else
  probe() { echo ""; }
  echo "(no ffprobe found — durations not measured)"
fi
find "$OUTROOT" -name '*.mp4' | sort | while read -r f; do
  printf "%-76s %ss %s\n" "$(basename "$f")" \
    "$(probe -v error -show_entries format=duration -of csv=p=0 "$f")" \
    "$(du -h "$f" | cut -f1)"
done
