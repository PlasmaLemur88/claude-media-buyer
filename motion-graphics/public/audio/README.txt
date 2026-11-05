Shared audio, no brand. bed_phrygian.wav is a music bed composed by
scripts/bed.py (run from the engine root), so unlike a track you find somewhere
it carries no licensing exposure. Any brand's configs can use it as
"audio/bed_phrygian.wav". It is not kept in git: setup.sh and build.sh make it
when it is missing. Regenerate it any time with:

    python3 scripts/bed.py

A brand's own voiceovers and beds live in brands/<slug>/assets/audio/ and are
referred to from its configs.mjs as "brand-active/audio/<file>".
