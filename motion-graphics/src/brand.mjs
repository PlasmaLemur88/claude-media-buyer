/**
 * THE ACTIVE BRAND. This file holds NO brand values, only code and
 * brand-neutral defaults.
 *
 * Every string, colour, logo and number a viewer sees comes from
 * src/brand.active.json, which `python3 scripts/brand.py use <slug>` writes as
 * a copy of brands/<slug>/brand.json with every "assets/..." path rewritten to
 * "brand-active/..." (the brand's assets are synced to public/brand-active/).
 * Both are gitignored: they are whichever brand is active on this machine.
 *
 * To change a brand, edit brands/<slug>/brand.json and run `brand.py use
 * <slug>` again (build.sh does that for you). Never edit brand.active.json:
 * the next `use` overwrites it.
 *
 * If brand.active.json is missing, nothing here can load. Run:
 *   python3 scripts/brand.py use <slug>
 *
 * The `with { type: "json" }` import works in both places this file runs:
 * Remotion's webpack bundle and plain node (build.sh). Tested with Node 22 and
 * Remotion 4.0.530.
 *
 * Every field is documented in brands/_template/brand.json.
 */
import B from "./brand.active.json" with { type: "json" };

const obj = (x) => (x && typeof x === "object" && !Array.isArray(x) ? x : {});
const str = (x, d = "") => (typeof x === "string" && x !== "" ? x : d);
/** Drop notes ("_" keys) and blank strings, so a blank field keeps the default. */
const clean = (x) => Object.fromEntries(Object.entries(obj(x))
  .filter(([k, v]) => !k.startsWith("_") && v !== "" && v !== null));

export const BRAND_SLUG = B.brand?.slug ?? "";

/**
 * The free close line split into its sentences with the brand name dropped.
 * "Acme. 12,000 readers. Free, forever." becomes ["12,000 readers",
 * "Free, forever"]. The end cards print the first as the paid subline and all
 * of them, joined with " · ", as the free subline, unless end_card sets them.
 */
const closeParts = (close, name) =>
  close.split(/\.\s+/).map((x) => x.replace(/\.$/, "").trim())
    .filter((x) => x && x !== name);
const NAME = str(B.brand?.name);
const CLOSE = closeParts(str(B.offer?.free?.close), NAME);

/**
 * Palettes. The two rules that matter for any brand:
 *   1. `bg` and `ink` need real contrast, at least 7:1. These formats are read
 *      at arm's length on a phone, often at half brightness.
 *   2. `accent` has ONE job: mark the thing the eye should land on. It must
 *      pop against BOTH bg and ink.
 * `dim` is for guides and inactive text, `muted` for secondary lines.
 * `readOnLarge` colours the small label on the large Cards end card; it
 * defaults to `muted`.
 */
const palette = (p) => {
  const x = obj(p);
  return {
    bg: x.bg, ink: x.ink, accent: x.accent, muted: x.muted, dim: x.dim,
    captionBg: str(x.captionBg, x.bg),
    wordmark: str(x.wordmark, ""),
    scrimTo: str(x.scrimTo, "none"),
    readOnLarge: str(x.readOnLarge, x.muted),
  };
};
export const DARK = palette(B.palettes?.dark);
export const PAPER = palette(B.palettes?.paper);

const F = obj(B.fonts);
/** Font files to load before a frame renders: [{family, file, weight}]. */
export const FONTS = Array.isArray(F.files) ? F.files : [];

const E = obj(B.end_card);
export const BRAND = {
  name: NAME,
  /** Prefix of every delivered filename, e.g. "ACME" -> ACME_431_..._9x16.mp4 */
  filePrefix: str(B.brand?.file_prefix, "AD"),
  /**
   * Where finished ads land. Default out/<slug>/ (git ignores out/). A path
   * outside this folder keeps the work apart from the tool.
   * OUTROOT=<dir> ./build.sh overrides it for one run.
   */
  outputRoot: str(B.brand?.output_root, `out/${BRAND_SLUG || "brand"}`),
  /** Round avatar on the end cards and the "person" byline. "" hides it. */
  avatar: str(E.avatar, ""),
  /** Small label above the platform wordmark. "" hides both. */
  platformLabel: str(E.platformLabel, ""),
  freeSubline: str(E.freeSubline, CLOSE.join(" · ")),
  paidSubline: str(E.paidSubline, CLOSE[0] ?? ""),
  /** The button. Defaults to offer.free.cta. */
  cta: str(E.cta, str(B.offer?.free?.cta)),
  /** Second line under the button, PAID cuts only. "" hides it. */
  paidFollowOn: str(E.paidFollowOn, ""),
  /** Printed straight after paidFollowOn in the accent colour. "" hides it. */
  paidFollowOnAccent: str(E.paidFollowOnAccent, ""),
  /** Full lines for writing voiceover scripts; no component draws them. */
  freeClose: str(B.offer?.free?.close),
  paidOutro: str(B.offer?.paid?.outro),
  /** Standing eyebrow that marks where the offer starts on PAID OneWord cuts. */
  offerEyebrow: str(E.offerEyebrow, ""),
  serif: str(F.serif, "Georgia, serif"),
  sans: str(F.sans, "Helvetica, Arial, sans-serif"),
  /** The Cards format's sans stack. Defaults to `sans`. */
  sansCards: str(F.sansCards, str(F.sans, "Helvetica, Arial, sans-serif")),
};

/** OneWord (RSVP) knobs. Defaults are the tested values; a brand may override. */
const R = clean(B.rsvp);
export const RSVP = {
  anchor: 0.4,
  sizes: [[5, 240], [8, 196], [11, 145], [Infinity, 108]],
  shortWordMax: 4,
  accentRun: 1,
  bg: DARK.bg,
  freeEndCard: 3.2,
  paidEndCard: 3.6,
  bedUnderVoice: 0.14,
  bedUnderCard: 0.5,
  ...R,
};
// JSON has no Infinity: a null bucket means "every longer word".
RSVP.sizes = RSVP.sizes.map(([n, px]) => [n === null ? Infinity : n, px]);

/** The offer numbers the paid formats print. A config can override any. */
export const OFFER = { readers: "", members: "", total: 0, tools: 0, price: 0, currency: "$", ...clean(B.offer_numbers) };

/** Logo tiles for the deals wall: [{name, src}]. */
export const FEATURED = Array.isArray(B.featured) ? B.featured : [];

/** The Cards format's PAID ledger. */
export const LEDGER = {
  freeLabel: "", freeRows: [], paidLabel: "", price: "", priceCues: [],
  worth: "", worthCue: "", tools: [], more: "", extras: [],
  ...obj(B.ledger),
};

const A = clean(B.aerial);
/** AerialKinetic. Copy strings are templates: {price} {cents} {total} {tools}
 *  {readers} {members} {unit} {units}. */
export const AERIAL = {
  font: { family: "InterVar", file: "", weight: "100 900" },
  markColor: DARK.accent,
  accent: DARK.accent,
  accentWord: DARK.accent,
  accentInk: "#fff",
  mark: "",
  personName: "",
  cobrandBy: "",
  platformWordmark: "",
  platformMark: "",
  communityLogo: "",
  hookLabel: "",
  wallThumbs: [],
  beats: [],
  keys: [],
  ...A,
  font: { family: "InterVar", file: "", weight: "100 900", ...clean(A.font) },
  copy: { rows: [], ...obj(A.copy) },
  cues: { wall: [], ...obj(A.cues) },
};

const O = clean(B.offer_card);
/** OfferCard. */
export const OFFER_CARD = {
  font: AERIAL.font,
  accent: DARK.accent,
  captionAccent: DARK.accent,
  rowHighlight: "#F4F4F4",
  mark: "",
  personName: "",
  communityLogo: "",
  cardTitle: "",
  bylinePerson: "",
  bylineLogo: "",
  button: "",
  perDay: "",
  captionFixes: [],
  ...O,
  font: { ...AERIAL.font, ...clean(O.font) },
  shine: { dark: "#FFFFFF", light: "#999999", ...clean(O.shine) },
};
