#!/usr/bin/env python3
"""Word-level timings for a VO file -> the brand's assets/words/NNN.json

    python3 scripts/timings.py brands/<slug>/assets/audio/vo_101.mp3 brands/<slug>/assets/words/101.json

The visuals need a start and end for every word, because a caption or an RSVP
word must never gap. ALWAYS READ THE PRINTED TRANSCRIPT before rendering:
Whisper mishears brand names (check yours), splits "12,000" into "12" and
",000", and splits "100%" into "100" and "%". The composition glues the splits
back together, but a genuinely misheard word has to be caught here.

The last line prints voEnd. That number goes straight into configs.mjs.
"""
import json
import pathlib
import sys

import whisper


def main(src: pathlib.Path, out: pathlib.Path) -> None:
    m = whisper.load_model("small")
    r = m.transcribe(str(src), word_timestamps=True, language="en")

    words = []
    for seg in r["segments"]:
        for w in seg.get("words", []):
            words.append({
                "w": w["word"].strip(),
                "s": round(float(w["start"]), 3),
                "e": round(float(w["end"]), 3),
            })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, indent=1))
    print(" ".join(x["w"] for x in words))
    print(f"\n{len(words)} words · wrote {out}")
    print(f"voEnd: {words[-1]['e']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: timings.py <vo.wav> <out.json>")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
