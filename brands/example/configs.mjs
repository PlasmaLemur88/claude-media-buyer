/**
 * EXAMPLE ADS for the invented brand Glazeberry Clay Club: one working ad in
 * every format, so build.sh proves the engine renders on a fresh copy. They
 * are samples, never for upload. The voiceovers are the free macOS voice
 * Samantha; the numbers are invented.
 *
 * `python3 scripts/brand.py use example` copies this file to
 * motion-graphics/src/configs.active.mjs, so imports are relative to
 * motion-graphics/src/ and asset paths are public/ paths: "brand-active/x" is
 * brands/example/assets/x; "aerial/..." and "audio/bed_phrygian.wav" are the
 * engine's shared samples. Field reference: motion-graphics/src/configs.mjs.
 *
 * Every time below is read from the word files in assets/words/ (made with
 * scripts/timings.py). voEnd = last word's end + padding.
 */
import { FEATURED } from "./brand.mjs";

const BED = "audio/bed_phrygian.wav";   // composed by scripts/bed.py, no licence exposure

// Cards scenes shared by the free and paid cut: the same voiceover body.
const scenes = (end) => [
  // wide on the whole poster while the problem is named
  { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.0, focusY: 0.5, from: 1.2, to: 6.06 },
  // punch in on the fix being said: "Wrap the rim..."
  { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.5, focusX: 1, focusY: 0.57, from: 6.06, to: 8.12 },
  // "...flip the mug and let the base catch up."
  { img: "brand-active/img/why-mugs-crack.jpg", zoom: 1.5, focusX: 1, focusY: 0.84, from: 8.12, to: 10.3 },
  { img: "brand-active/img/drying-order.jpg", zoom: 1.0, focusY: 0.5, from: 10.3, to: end },
];

export const ADS = [
  // EXAMPLE 101 OneWord, FREE. Last word ends 15.06.
  {
    number: "101", persona: "Beginner", personaDir: "01-beginners",
    format: "OneWord", concept: "CrackedMugs", conceptSlug: "cracked-mugs", hookStyle: "Tell",
    config: { offer: "free", vo: "brand-active/audio/vo_example_free.mp3", bed: BED, voEnd: 15.26 },
  },
  // EXAMPLE 101 OneWord, PAID: same body, offer outro from 10.4 ("The newsletter is free.").
  {
    number: "101", persona: "Beginner", personaDir: "01-beginners",
    format: "OneWord", concept: "CrackedMugs", conceptSlug: "cracked-mugs", hookStyle: "Tell",
    config: { offer: "paid", vo: "brand-active/audio/vo_example_paid.mp3", bed: BED, bodyEnd: 10.3, voEnd: 22.02 },
  },

  // EXAMPLE 102 Cards, FREE. Reuses 101's voiceover exactly (a format test).
  {
    number: "102", persona: "Beginner", personaDir: "01-beginners",
    format: "Cards", concept: "CrackedMugs", conceptSlug: "cracked-mugs", hookStyle: "Tell",
    words: "101",
    config: {
      offer: "free", theme: "dark",
      vo: "brand-active/audio/vo_example_free.mp3", bed: BED,
      hookEnd: 1.2, hookLead: 0.1, hookAccent: "cracking", hookAccentFlags: "i", hookSize: 108,
      voEnd: 15.26, endCard: "compact",   // the long name overflows the "large" card
      scenes: scenes(15.26),
    },
  },
  // EXAMPLE 102 Cards, PAID: the ledger runs from bodyEnd to voEnd.
  {
    number: "102", persona: "Beginner", personaDir: "01-beginners",
    format: "Cards", concept: "CrackedMugs", conceptSlug: "cracked-mugs", hookStyle: "Tell",
    words: "101_paid",
    config: {
      offer: "paid", theme: "dark",
      vo: "brand-active/audio/vo_example_paid.mp3", bed: BED,
      hookEnd: 1.2, hookLead: 0.1, hookAccent: "cracking", hookAccentFlags: "i", hookSize: 108,
      bodyEnd: 10.3, voEnd: 22.02, endCard: "compact",
      scenes: scenes(10.3),
    },
  },

  // EXAMPLE 103 AerialKinetic, PAID. Seven beats, one shared aerial clip each.
  // Last word ends 30.5.
  {
    number: "103", persona: "Beginner", personaDir: "01-beginners",
    format: "AerialKinetic", concept: "OneWorkshop", conceptSlug: "one-workshop", hookStyle: "About",
    config: {
      offer: "paid",
      vo: "brand-active/audio/vo_example_aerial.mp3", bed: BED, bedVolume: 0.1,
      shots: [
        { src: "aerial/aerial_coast.mp4", from: 0 },         // hook
        { src: "aerial/aerial_land_b.mp4", from: 0 },    // bridge
        { src: "aerial/aerial_land_a.mp4", from: 0 },           // identity
        { src: "aerial/aerial_land_c.mp4", from: 0 },        // platform
        { src: "aerial/aerial_coast.mp4", from: 3 },         // community
        { src: "aerial/aerial_land_b.mp4", from: 3 },    // deals
        { src: "aerial/aerial_land_a.mp4", from: 3 },           // close
      ],
      brand: "logo",
      eyebrow: "For new potters",
      headline: "Three live pottery workshops a week, $180 a year.",
      featured: FEATURED,
      voEnd: 30.85,
      hold: 2.2,
    },
  },

  // EXAMPLE 104 OfferCard, PAID. Last word ends 16.6.
  {
    number: "104", persona: "Beginner", personaDir: "01-beginners",
    format: "OfferCard", concept: "InsideTheStudio", conceptSlug: "inside-the-studio", hookStyle: "Tell",
    config: {
      offer: "paid",
      vo: "brand-active/audio/vo_example_card.mp3", bed: BED, bedVolume: 0.1,
      bg: "#2A1F24", dark: true, btnBg: "#B8365F",
      brand: "logo",
      headline: "Pottery is easier with people around you.",
      lineA: { b: "Glaze Notes", t: " is free." },
      lineB: { b: "Live workshops", t: " in the studio." },
      rows: [
        { pre: "Wheel basics and glazing workshops", cue: "basics" },
        { pre: "Open studio hours", cue: "open" },
        { bold: "$420", post: " of supplier discounts", cue: "supplier",
          logos: FEATURED.filter((f) => ["Kilnwise", "Oxbell Clay", "Tidewheel"].includes(f.name)) },
      ],
      cues: { lineA: "notes", lineB: "studio", price: "join" },
      captions: true,
      eyebrow: "For new potters",
      perDay: true,
      voEnd: 16.95,
      hold: 2.2,
    },
  },
];
