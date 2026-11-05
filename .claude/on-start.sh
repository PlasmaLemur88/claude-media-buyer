#!/bin/bash
# Fires at session start. Cheap checks only: this runs on every session open,
# so it must not render anything.
cd "$(dirname "$0")/.."
echo "CLAUDE-MEDIA-BUYER - first steps for this session:"
echo "(A scheduled run follows its task prompt and skips steps 0 to 2 below.)"
echo
_missing=""
command -v ffmpeg >/dev/null 2>&1 || _missing="$_missing ffmpeg"
command -v node >/dev/null 2>&1 || _missing="$_missing node"
python3 -c "import numpy,scipy,PIL,whisper" >/dev/null 2>&1 || _missing="$_missing python-packages"
[ -d motion-graphics/node_modules/remotion ] || _missing="$_missing remotion-packages"
for k in REPLICATE_API_TOKEN FAL_KEY; do
  grep -q "^$k=.\+" .env 2>/dev/null || _missing="$_missing $k"
done
if [ -n "$_missing" ]; then
  echo "0. NOT READY:$_missing (fal and Replicate keys are only needed for new videos)"
  echo "   Run: bash setup.sh   (do it yourself - the operator should not need a terminal; never in a scheduled run)"
  echo "   Full check: python3 scripts/doctor.py"
  echo
fi
echo "1. Read RULES.md in full. Then the active brand: python3 scripts/brand.py show,"
echo "   and read its BRAND-GUIDE.md. No brand yet, or a new one: run the brand-guide skill."
echo
echo "2. Motion graphics: motion-graphics/ and docs/. Acted scene: read CINEMATIC.md,"
echo "   then lib/director.md IN FULL, and follow its stage gates."
echo
if [ -f .current_project ]; then
  echo "3. An acted-scene project is open:"
  python3 scripts/session.py status 2>&1 | sed 's/^/   /'
  echo
fi
echo "Running Meta ads from here: read ads/WORKFLOW.md when the operator says \"run my ads\"."
echo "Before ANY generation spend, state the cost and get an explicit yes (autopilot excepted: see the end of RULES.md)."
echo "A green check means 'no rule broken', never 'this is good'."
