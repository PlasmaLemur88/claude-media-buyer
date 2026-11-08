#!/bin/bash
# One-time setup. Claude runs this for the operator - they should not need a
# terminal. Safe to run twice; everything here is idempotent.
set -u
cd "$(dirname "$0")"
echo "engine setup"
echo

fail=0

# --- python packages -------------------------------------------------------
echo "1/5  python packages"
if python3 -c "import numpy, scipy, PIL, whisper, librosa, cv2, playwright" 2>/dev/null; then
  echo "     already installed"
else
  echo "     installing (whisper is large, this can take a few minutes)"
  python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt \
    && echo "     done" \
    || { echo "     FAILED. Try: python3 -m pip install -r requirements.txt"; fail=1; }
fi
# the widow check drives a headless Chromium; a no-op once installed
python3 -m playwright install chromium >/dev/null 2>&1 \
  && echo "     headless browser for the widow check ready" \
  || echo "     note: python3 -m playwright install chromium failed; widows.py will not run until it does"

# --- ffmpeg ----------------------------------------------------------------
echo
echo "2/5  ffmpeg"
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  echo "     found: $(ffmpeg -version 2>/dev/null | head -1 | cut -c1-48)"
else
  echo "     NOT FOUND."
  case "$(uname -s)" in
    Darwin)
      echo "     This one needs your Mac password, so Claude cannot install it for you."
      echo "     Open Terminal (Cmd+Space, type Terminal) and run:"
      echo "       /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
      echo "       brew install ffmpeg"
      echo "     Then say so and setup continues." ;;
    Linux) echo "     sudo apt install ffmpeg   (or your distro's package manager)" ;;
    *)     echo "     Install ffmpeg from https://ffmpeg.org/download.html" ;;
  esac
  fail=1
fi

# --- keys ------------------------------------------------------------------
echo
echo "3/5  keys"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "     created .env from the example"
fi
for k in REPLICATE_API_TOKEN FAL_KEY; do
  if grep -q "^$k=.\+" .env 2>/dev/null; then
    echo "     $k present"
  else
    echo "     $k empty: fine. Only needed for one kind of new video; ask when a job needs it."
  fi
done
grep -q "^GEMINI_API_KEY=.\+" .env 2>/dev/null \
  && echo "     GEMINI_API_KEY present" \
  || echo "     GEMINI_API_KEY empty (optional: Gemini voices, watching videos, images)"

# --- motion graphics ---------------------------------------------------------
echo
echo "4/5  motion graphics (Node + Remotion)"
if ! command -v node >/dev/null; then
  echo "     Node.js NOT FOUND. Install the LTS version from https://nodejs.org"
  echo "     (a normal Mac installer), then run ./setup.sh again."
  fail=1
elif [ -d motion-graphics/node_modules/remotion ]; then
  echo "     already installed"
else
  echo "     installing packages (a minute or two)"
  (cd motion-graphics && npm install --no-audit --no-fund --loglevel=error) \
    && echo "     done" \
    || { echo "     FAILED. Try: cd motion-graphics && npm install"; fail=1; }
fi

# --- folders the scripts write into ----------------------------------------
echo
echo "5/5  working folders"
mkdir -p projects audio tests/_tmp
rm -rf tests/_tmp
if [ -s motion-graphics/public/audio/bed_phrygian.wav ]; then
  echo "     music bed present"
else
  python3 scripts/bed.py >/dev/null 2>&1 && echo "     music bed composed (scripts/bed.py)" \
    || { echo "     FAILED to compose the music bed: python3 scripts/bed.py"; fail=1; }
fi
echo "     ready"

echo
if [ "$fail" -eq 0 ]; then
  echo "Setup complete. Running the self-check."
  echo
  python3 scripts/doctor.py
else
  echo "Setup is not finished. Fix what is listed above, then run ./setup.sh again."
  exit 1
fi
