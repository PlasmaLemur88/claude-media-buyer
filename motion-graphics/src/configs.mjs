/**
 * The ad list. Each brand keeps its own in brands/<slug>/configs.mjs; `python3
 * scripts/brand.py use <slug>` copies it to src/configs.active.mjs (gitignored)
 * and build.sh refreshes that copy before every run. EDIT THE BRAND'S FILE,
 * never configs.active.mjs.
 *
 * Inside a brand's configs.mjs, imports are relative to motion-graphics/src/
 * (e.g. `import { FEATURED } from "./brand.mjs"`) and asset paths are public/
 * paths: "brand-active/..." is the active brand's assets/ folder;
 * "aerial/..." and "audio/bed_phrygian.wav" are shared samples.
 *
 * The fields drive both the composition id and the output path, so a config
 * entry and a render command cannot drift apart:
 *
 *   <outputRoot>/<personaDir>/<number>-<format-lowercase>-<conceptSlug>/
 *     <PREFIX>_<number>_<Persona>_<Format>_<Concept>_<HookStyle>_<OFFER>_<Ratio>.mp4
 *
 * PREFIX is brand.file_prefix in brand.json. The convention in
 * docs/80-naming-and-delivery.md is canonical; if it disagrees, it wins.
 *
 * number      the creative concept. 101, 102, ...
 * persona     who the ad talks to, one CamelCase token (the brand's personas).
 * personaDir  delivery folder for that persona, e.g. 01-beginners.
 * format      OneWord | Cards | AerialKinetic | OfferCard (see Root.tsx).
 * concept     CamelCase, no spaces. The idea, not the wording.
 * conceptSlug lowercase-hyphenated form, for the folder.
 * hookStyle   HOW THE AD OPENS: Ask (a question), Tell (direct address),
 *             About (third person). It replaced a V1/V2 counter, which told
 *             you two files differed but never what differed.
 * words       optional stem of the word-timings file in the brand's
 *             assets/words/. Default: <number> or <number>_paid.
 *
 * config.offer   "free" | "paid". Never omit it.
 * config.voEnd   end time of the last word. scripts/timings.py prints it.
 *                DO NOT GUESS IT.
 * config.bodyEnd (paid only) where the body stops and the offer outro begins.
 *
 * A DEFECT FIX IS NOT A TEST ARM. A broken cut leaves the delivery tree
 * entirely. A FORMAT TEST REUSES THE VOICEOVER FILE OF THE AD IT TESTS
 * AGAINST, so the format is the only variable that moved.
 */
export { ADS } from "./configs.active.mjs";
