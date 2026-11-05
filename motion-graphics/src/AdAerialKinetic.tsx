import React from "react";
import {
  AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate,
  staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { AERIAL, BRAND, FEATURED, OFFER } from "./brand.mjs";
import { centsPerDay, fill, useFont } from "./fill";
import { Word } from "./AdRsvp";

/**
 * AerialKinetic: aerial footage, one shot per beat, the
 * spoken words sliding in line by line as they are said and lighting up word
 * by word, and one graphic per beat sliding in on its cue word. The kinetic
 * words ARE the captions, so there is no separate caption band.
 *
 * Every timing comes from the Whisper word file, so a new voice only needs a
 * new words file. Which graphic a sentence gets is decided by the words in it
 * (aerial.beats in brand.json), not by its position, so a script can run more
 * sentences per beat without the graphics falling out of step.
 *
 * The seven beats, in the order a script usually runs them:
 *   hook      persona line; a crowd graphic (config.hook) or the default
 *             two-person graphic (the second person lights up with
 *             aerial.hookLabel)
 *   bridge    the "wall of videos" that scatters on the clearing word
 *   identity  the byline plus the readers and members pills
 *   platform  the free product card (newsletter, app, channel)
 *   community the paid product card with three rows, optionally after a clip
 *             of a real live session (config.classInsert)
 *   deals     the dollar total counting up, plus the logo wall
 *   close     byline, price button, per-day line, community line
 *
 * No brand string, number, colour or logo path lives in this file. They are in
 * aerial, offer_numbers and featured in the brand's brand.json, and any of them
 * can be overridden per ad in the brand's configs.mjs.
 */

type Rule = { beat: string; any?: string[]; starts?: string[] };
type Copy = typeof AERIAL.copy;

export type AerialKineticConfig = {
  offer?: "free" | "paid";
  vo: string;
  bed: string;
  bedVolume?: number;
  /** One per beat run, in order. `from` = seconds into the clip. A shot can repeat. */
  shots: { src: string; from: number }[];
  /** "person" leads the byline with BRAND.avatar + AERIAL.personName, "logo" with AERIAL.mark. */
  brand: "person" | "logo";
  eyebrow: string;       // persona callout, on screen from frame 0 and on the cover
  headline: string;      // cover headline
  voEnd: number;         // last word's end + padding. Measured, never guessed.
  hold: number;          // seconds after voEnd

  /** Offer numbers. Default offer_numbers / featured in brand.json. Verify before use. */
  price?: number;
  total?: number;
  tools?: number;
  readers?: string;
  members?: string;
  featured?: { src: string; name: string }[];

  /** Persona treatment: each persona must read as a different creative to Meta. */
  accent?: string;       // pills, price line, deals figure, button, clip ring
  accentWord?: string;   // lit key words in the spoken lines
  accentInk?: string;    // text on the accent (white, or ink on a light accent)
  align?: "center" | "left";
  weight?: number;       // 100-900, the spoken lines and the cover headline
  keys?: string[];       // extra lit words on top of AERIAL.keys
  button?: string;       // closing button text; default AERIAL.copy.button
  /** A row of `count` people that appears on `show`, goes dashed on `fade`,
   *  and the middle one (or all, with `all`) turns the accent on `light`.
   *  Unset keeps the default two-person graphic cued by AERIAL.cues. */
  hook?: { count: number; show: string; fade?: string; light: string; all?: boolean };

  /** A clip of a real live session, shown in the community beat before the card.
   *  strip = the attendee row, slide = the shared screen, host = the host's tile
   *  cropped alone. Attendee tiles are covered by `tiles` (swap real faces for
   *  consented or generated ones, and say so in `privacy`). The geometry is the
   *  crop of one recording; measure your own. Needs real footage: no sample. */
  classInsert?: {
    strip: string; slide: string; host: string; hostName: string;
    tiles: { src: string; name: string }[]; tag: string; privacy: string;
    stripW?: number; stripH?: number; tileX?: number[]; tileW?: number; tileH?: number; tileY?: number;
    slideAspect?: number;
  };

  /** A cut-out presenter (transparent webm) riding in a corner, big for the hook.
   *  `at` = where each clip starts on the timeline. Needs real footage: no sample.
   *  Never a generated or voice-cloned version of a real person without consent. */
  presenter?: { clips: { src: string; at: number; dur: number }[]; scale?: number; fadeFrom?: number };

  /** Per-ad overrides of the brand defaults in AERIAL. */
  copy?: Partial<Copy>;
  cues?: Partial<typeof AERIAL.cues>;
  beats?: Rule[];
};

export const durationOf = (c: AerialKineticConfig) => c.voEnd + c.hold;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.2, 0.9, 0.25, 1);
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9$]/g, "");

// Whisper splits "$1,250" into "$1" + ",250"; glue any token that starts with punctuation back on.
const glue = (words: Word[]) =>
  words.reduce<Word[]>((out, w) => {
    const last = out[out.length - 1];
    if (last && /^[,.%]/.test(w.w)) out[out.length - 1] = { w: last.w + w.w, s: last.s, e: w.e };
    else out.push({ ...w });
    return out;
  }, []);

const sentences = (words: Word[]) => {
  const out: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    if (/[.?!]$/.test(w.w)) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
};

// Line breaks for one sentence, at most `budget` characters a line. Dynamic programming over every
// break: even line lengths, a strong penalty for ending a line on a small word or leaving one word
// alone, a small reward for breaking after a comma. (A word-count cap overflowed the frame.)
const SMALL = /^(a|an|and|the|of|to|for|with|that|our|plus)$/i;
const len = (ws: Word[]) => ws.reduce((n, w) => n + w.w.length, 0) + Math.max(0, ws.length - 1);
const lines = (ws: Word[], budget: number) => {
  const n = ws.length;
  const best = Array(n + 1).fill(Infinity), prev = Array(n + 1).fill(0);
  best[0] = 0;
  for (let j = 1; j <= n; j++) {
    for (let i = 0; i < j; i++) {
      const l = len(ws.slice(i, j));
      if (l > budget && j - i > 1) continue;
      let cost = (budget - l) ** 2 * (j === n ? 0.3 : 1);
      if (j < n && SMALL.test(ws[j - 1].w)) cost += 2000;
      if (j - i === 1 && n > 1) cost += 800;
      if (j < n && /[,.?:!]$/.test(ws[j - 1].w)) cost -= 40;
      if (best[i] + cost < best[j]) { best[j] = best[i] + cost; prev[j] = i; }
    }
  }
  const out: Word[][] = [];
  for (let j = n; j > 0; j = prev[j]) out.unshift(ws.slice(prev[j], j));
  return out;
};

// slide up and fade in, landing just as the word is said
const enter = (t: number, at: number, dist = 40) => {
  const p = interpolate(t, [at - 0.12, at + 0.2], [0, 1], { ...clamp, easing: ease });
  return { opacity: p, transform: `translateY(${(1 - p) * dist}px)` };
};

const Person: React.FC<{ fill: string; dashed?: boolean; label?: string; size: number; ink?: string; font: string }> = ({ fill: f, dashed, label, size, ink = "#fff", font }) => (
  <svg viewBox="0 0 100 120" width={size} height={size * 1.2}>
    <circle cx="50" cy="32" r="24" fill={dashed ? "none" : f} stroke={dashed ? "#fff" : "none"} strokeWidth={4} strokeDasharray={dashed ? "9 7" : undefined} />
    <path d="M8 118 C8 80 26 64 50 64 C74 64 92 80 92 118 Z" fill={dashed ? "none" : f} stroke={dashed ? "#fff" : "none"} strokeWidth={4} strokeDasharray={dashed ? "9 7" : undefined} />
    {label ? <text x="50" y="40" textAnchor="middle" fontFamily={font} fontWeight={800} fontSize={22} fill={ink}>{label}</text> : null}
  </svg>
);

const Card: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <div style={{ background: "#fff", color: "#111", borderRadius: 26, boxShadow: "0 18px 50px rgba(0,0,0,.35)", ...style }}>{children}</div>
);

/** The byline. `cobrand`: the brand mark leads and the person rides on its corner at about half
 *  its size (operator call, 2026-09-13: brand bigger, the person's face subordinate). */
const Byline: React.FC<{ brand: "person" | "logo"; size: number; cobrand?: boolean }> = ({ brand, size, cobrand }) => {
  const name = BRAND.name, avatar = BRAND.avatar;
  const person = brand === "person" && !!avatar;
  if (person && cobrand) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: size * 0.5 }}>
        <div style={{ position: "relative", width: size, height: size, flex: "none" }}>
          <Img src={staticFile(AERIAL.mark)} style={{ width: size, height: size, borderRadius: size / 2, boxShadow: "0 10px 30px rgba(0,0,0,.35)" }} />
          <Img src={staticFile(avatar!)} style={{ position: "absolute", right: -size * 0.36, bottom: -size * 0.14, width: size * 0.72, height: size * 0.72,
            borderRadius: "50%", border: `4px solid ${AERIAL.markColor}`, objectFit: "cover", boxShadow: "0 6px 16px rgba(0,0,0,.35)" }} />
        </div>
        <div style={{ textAlign: "left" }}>
          <div style={{ fontSize: size * 0.44, fontWeight: 850, lineHeight: 1.05 }}>{name}</div>
          <div style={{ fontSize: size * 0.27, fontWeight: 600, opacity: 0.95, display: "flex", alignItems: "center", gap: size * 0.07 }}>
            {AERIAL.cobrandBy}
            {AERIAL.platformWordmark ? <Img src={staticFile(AERIAL.platformWordmark)} style={{ height: size * 0.2, marginTop: size * 0.03 }} /> : null}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: size * 0.17 }}>
      {person ? (
        <Img src={staticFile(avatar!)} style={{ width: size, height: size, borderRadius: size / 2, border: `5px solid ${AERIAL.markColor}`, objectFit: "cover", boxShadow: "0 10px 30px rgba(0,0,0,.35)" }} />
      ) : (
        <Img src={staticFile(AERIAL.mark)} style={{ width: size, height: size, borderRadius: size / 2, boxShadow: "0 10px 30px rgba(0,0,0,.35)" }} />
      )}
      <div style={{ textAlign: "left" }}>
        <div style={{ fontSize: size * 0.42, fontWeight: 800, lineHeight: 1.1 }}>{person ? AERIAL.personName : name}</div>
        {person ? <div style={{ fontSize: size * 0.26, fontWeight: 600, opacity: 0.85 }}>{name}</div> : null}
      </div>
    </div>
  );
};

// Default tile geometry: one recording cropped to a 1180x92 attendee strip, seven tiles, host first.
// Measure your own recording and pass stripW/tileX/... in classInsert.
const TILE_X = [7, 175, 343, 511, 679, 847, 1015];

/** The live session as it looked: the attendee strip over the shared screen. Every attendee tile
 *  is covered by a replacement tile with a first name; the host's tile gets a ring and a label. */
const ClassPanel: React.FC<{ ci: NonNullable<AerialKineticConfig["classInsert"]>; width: number; tall: boolean; accent: string; ink: string }> = ({ ci, width, tall, accent, ink }) => {
  const sw = ci.stripW ?? 1180, sh = ci.stripH ?? 92;
  const tx = ci.tileX ?? TILE_X, tw = ci.tileW ?? 158, th = ci.tileH ?? 86, ty = ci.tileY ?? 2;
  const s = width / sw;
  const label = (big = false): React.CSSProperties => ({
    position: "absolute", left: 5 * s, bottom: 4 * s, padding: `${2 * s}px ${6 * s}px`, borderRadius: 5 * s,
    background: big ? accent : "rgba(20,20,20,.85)", color: big ? ink : "#fff", fontWeight: 700,
    fontSize: (big ? 17 : 13) * s, lineHeight: 1.2, whiteSpace: "nowrap",
  });
  return (
    <div style={{ position: "relative", width, background: "#101010", borderRadius: 20, overflow: "hidden", boxShadow: "0 22px 60px rgba(0,0,0,.55)", paddingTop: 10 }}>
      <div style={{ position: "relative", width, height: sh * s }}>
        <OffthreadVideo src={staticFile(ci.strip)} muted style={{ width, height: sh * s, display: "block" }} />
        {ci.tiles.map((tl, i) => (
          <div key={tl.name} style={{ position: "absolute", left: tx[i + 1] * s, top: ty * s, width: tw * s, height: th * s, borderRadius: 7 * s, overflow: "hidden", background: "#222" }}>
            <OffthreadVideo src={staticFile(tl.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <div style={label()}>{tl.name}</div>
          </div>
        ))}
        <div style={{ position: "absolute", left: tx[0] * s, top: ty * s, width: tw * s, height: th * s }}>
          <div style={{ ...label(true), left: 4 * s, bottom: 3 * s, minWidth: 92 * s }}>{ci.hostName}</div>
        </div>
        <div style={{ position: "absolute", left: tx[0] * s - 4, top: ty * s - 4, width: tw * s + 8, height: th * s + 8,
          border: `4px solid ${accent}`, borderRadius: 7 * s + 4, boxShadow: `0 0 18px ${accent}b3` }} />
      </div>
      <div style={{ position: "relative" }}>
        <OffthreadVideo src={staticFile(ci.slide)} muted style={{ width, height: width / (ci.slideAspect ?? 1144 / 640), display: "block" }} />
        <div style={{ position: "absolute", right: 12, bottom: 10, fontSize: tall ? 22 : 19, fontWeight: 600, color: "#fff",
          background: "rgba(0,0,0,.6)", padding: "4px 12px", borderRadius: 8 }}>{ci.privacy}</div>
      </div>
    </div>
  );
};

export const AdAerialKinetic: React.FC<{ words: Word[]; c: AerialKineticConfig; cover?: boolean }> = ({ words: raw, c, cover }) => {
  useFont(AERIAL.font);
  const frame = useCurrentFrame();
  const { fps, height, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const tall = height > 1600;
  const k = tall ? 1.15 : 0.85;                     // graphic scale per ratio
  const font = `${AERIAL.font.family}, Helvetica, Arial, sans-serif`;

  // offer numbers and copy: brand defaults, then this ad's overrides
  const price = c.price ?? OFFER.price, total = c.total ?? OFFER.total, tools = c.tools ?? OFFER.tools;
  const readers = c.readers ?? OFFER.readers, members = c.members ?? OFFER.members;
  const featured = c.featured ?? FEATURED;
  const copy: Copy = { ...AERIAL.copy, ...(c.copy ?? {}) };
  const cues = { ...AERIAL.cues, ...(c.cues ?? {}) };
  const cents = centsPerDay(price);
  const vars = { price, cents, total: total.toLocaleString("en-US"), tools, readers, members, unit: copy.unit, units: copy.units };
  const tx = (s: string) => fill(s, vars);
  // tokens in beat and key lists: {price} -> "$180", {total} -> "$1250"
  const tok = (s: string) => norm(s.replace("{price}", `$${price}`).replace("{total}", `$${total}`));
  const priceWord = `$${price}`, totalWord = `$${total}`;
  const isTotal = (w: string) => w.startsWith("$") && norm(w) === totalWord;

  const words = glue(raw);
  const sents = sentences(words);
  const starts = sents.map((s, i) => (i === 0 ? 0 : s[0].s - 0.08));
  const at = (key: string, after = 0) => words.find((w) => w.s >= after && norm(w.w) === norm(key))?.s ?? 999;
  const si = Math.max(0, starts.filter((s) => t >= s).length - 1);
  const rules = (c.beats ?? AERIAL.beats).map((r) => ({ ...r, any: (r.any ?? []).map(tok), starts: (r.starts ?? []).map(tok) }));
  const beatOf = (s: Word[]) => {
    const ws = s.map((w) => norm(w.w));
    for (const r of rules) {
      if (r.any.some((a) => ws.includes(a))) return r.beat;
      if (r.starts.length && r.starts.every((a, i) => ws[i] === a)) return r.beat;
    }
    return "hook";
  };
  const beats = sents.map(beatOf);
  const beat = beats[si] ?? "hook";
  // one aerial shot per run of same-beat sentences
  const segs: { beat: string; from: number; to: number }[] = [];
  beats.forEach((b, i) => { if (segs.length && segs[segs.length - 1].beat === b) segs[segs.length - 1].to = i; else segs.push({ beat: b, from: i, to: i }); });
  const segStart = (b: string) => { const g = segs.find((x) => x.beat === b); return g ? starts[g.from] : 999; };
  const accent = c.accent ?? AERIAL.accent, accentWord = c.accentWord ?? AERIAL.accentWord, ink = c.accentInk ?? AERIAL.accentInk;
  const align = c.align ?? "center", weight = c.weight ?? 800;
  const keySet = new Set([...AERIAL.keys, ...(c.keys ?? [])].map(tok));
  const isKey = (w: string) => keySet.has(w);

  const bedVol = (f: number) => {
    const tt = f / fps, base = c.bedVolume ?? 0.12;
    return tt < c.voEnd ? base : Math.min(0.4, base + ((tt - c.voEnd) / 0.8) * (0.4 - base));
  };

  // cue times
  const tTwo = at(cues.hookShow), tAfford = at(cues.hookFade), tAI = at(cues.hookLight);
  const tWall = Math.min(...cues.wall.map((w) => at(w)));                  // the video-tile wall
  const tOneClass = tWall < 999 ? at(cues.wallClear, tWall) : 999;          // the clearing word
  const tId = segStart("identity"), tReaders = at(cues.readers, tId), tMembers = at(cues.members, tId);
  const tSubSeg = segStart("platform"), tSub = at(cues.platform, tSubSeg < 999 ? tSubSeg : 0), tFree = at(cues.free, tSub);
  const tCommSeg = segStart("community"), tComm = at(cues.community, tCommSeg < 999 ? tCommSeg : 0), tThree = at(cues.cadence, tComm);
  const rows = copy.rows.map(([label, sub, cue]) => ({ label, sub: tx(sub), at: at(cue, tComm) }));
  const tRow1 = rows[0]?.at ?? 999, tRowLast = rows[rows.length - 1]?.at ?? 999;
  const tDealsSeg = segStart("deals"), tPlus = at(cues.deals, tDealsSeg < 999 ? tDealsSeg : 0);
  const tDeals = tPlus < 999 ? tPlus : tDealsSeg;
  const tMoney = words.find((w) => w.s >= tDeals && w.w.startsWith("$"))?.s ?? tDeals;
  // the closing beat starts on the first sentence of the close run; the join word and the price cue inside it
  const closeIdx = beats.indexOf("close");
  const tClose = closeIdx >= 0 ? starts[closeIdx] : starts[starts.length - 1];
  const tJoinSaid = at(cues.join, tClose), tJoin = tJoinSaid < 999 ? tJoinSaid : tClose;
  const tPriceSaid = at(priceWord, tClose), tPrice = tPriceSaid < 999 ? tPriceSaid : tClose + 0.4;
  const tCentsSaid = at(String(cents), tPrice), tCents = tCentsSaid < 999 ? tCentsSaid : tPrice + 0.5;

  // the class clip holds the community sentence until the first row, then hands over to the card
  const ci = c.classInsert;
  const panelStart = tCommSeg < 999 ? tCommSeg : 0;
  const panelEnd = ci && tCommSeg < 999 && tRow1 < 999 ? tRow1 - 0.15 : -1;

  const count = Math.round(total * interpolate(t, [tMoney, tMoney + 0.9], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) }));
  const money = `$${count.toLocaleString("en-US")}`;

  const textTop = tall ? 300 : 110;
  // with a presenter on screen the graphics ride higher so the corner stays clear of the cards
  const gfxTop = c.presenter ? (tall ? 700 : 470) : tall ? 960 : 650;
  const fontSize = tall ? 70 : 56;
  const eyebrow = (
    <div style={{ background: accent, color: ink, fontWeight: 800, fontSize: tall ? 40 : 34, letterSpacing: 2,
      textTransform: "uppercase", padding: "10px 30px", borderRadius: 999, boxShadow: "0 8px 24px rgba(0,0,0,.3)" }}>{c.eyebrow}</div>
  );
  const communityLine = (size: number, style: React.CSSProperties = {}) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: size, fontWeight: 600, opacity: 0.95, textShadow: "0 3px 14px rgba(0,0,0,.5)", ...style }}>
      <Img src={staticFile(AERIAL.communityLogo)} style={{ width: size * 1.22, height: size * 1.22, borderRadius: 9 }} />
      {tx(copy.communityLine)}
    </div>
  );
  const byline = (size: number) => <Byline brand={c.brand} size={size} cobrand />;

  // The cover: a still poster for Ads Manager's thumbnail, calling out the persona before anyone presses play.
  if (cover) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#000", fontFamily: font, color: "#fff" }}>
        <OffthreadVideo src={staticFile(c.shots[0].src)} startFrom={Math.round((c.shots[0].from + 2) * fps)} muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,.35) 50%, rgba(0,0,0,.6) 100%)" }} />
        <AbsoluteFill style={{ display: "flex", flexDirection: "column", alignItems: align === "left" ? "flex-start" : "center", justifyContent: "center", gap: tall ? 56 : 38, padding: "0 70px", textAlign: align }}>
          {eyebrow}
          <div style={{ fontSize: tall ? 104 : 84, fontWeight: Math.min(900, weight + 50), lineHeight: 1.05, letterSpacing: -2, textWrap: "balance" as any, textShadow: "0 4px 24px rgba(0,0,0,.5)" }}>{c.headline}</div>
          {byline(tall ? 138 : 114)}
          <div style={{ background: "#fff", color: "#111", fontSize: tall ? 44 : 38, fontWeight: 800, padding: "18px 40px", borderRadius: 999 }}>
            {tx(copy.coverPrice)} <span style={{ color: accent }}>{tx(copy.coverPerDay)}</span>
          </div>
          {communityLine(tall ? 31 : 27, { marginTop: tall ? -34 : -22 })}
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }

  // the wall of course videos: appears on the wall cue, scatters on the clearing word, leaves one tile
  const Wall = () => {
    const n = 24, cols = 6, tw = 132, th = 78, gap = 8;
    const thumbs = AERIAL.wallThumbs;
    const gone = t >= tOneClass;
    const inCard = interpolate(t, [tWall - 0.1, tWall + 0.25], [0, 1], { ...clamp, easing: ease });
    const cardOut = gone ? interpolate(t, [tOneClass + 0.3, tOneClass + 0.6], [1, 0], clamp) : 1;
    const W = cols * (tw + gap) - gap, H = 4 * (th + gap) - gap;
    return (
      <div style={{ position: "relative", width: W + 36, height: H + 96 }}>
        <Card style={{ position: "absolute", inset: 0, padding: "16px 18px 16px", opacity: inCard * cardOut, transform: `translateY(${(1 - inCard) * 60}px)` }}>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#111", marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ background: "#111", color: "#fff", borderRadius: 999, padding: "4px 14px", fontSize: 25 }}>{copy.wallCount}</span>
            <span style={{ color: "#777", fontWeight: 600 }}>{copy.wallLength}</span>
          </div>
          <div style={{ position: "relative", width: W, height: H }}>
            {Array.from({ length: n }, (_, i) => {
              const r = Math.floor(i / cols), cc = i % cols;
              const inP = interpolate(t, [tWall + i * 0.015, tWall + 0.2 + i * 0.015], [0, 1], { ...clamp, easing: ease });
              const outP = gone ? interpolate(t, [tOneClass + (i % 7) * 0.02, tOneClass + 0.35 + (i % 7) * 0.02], [0, 1], { ...clamp, easing: ease }) : 0;
              const dx = ((cc - 2.5) * 260) * outP, dy = ((r - 1.5) * 220 - 40) * outP;
              return (
                <div key={i} style={{ position: "absolute", left: cc * (tw + gap), top: r * (th + gap), width: tw, height: th, borderRadius: 8, overflow: "hidden", background: "#ddd",
                  opacity: inP * (1 - outP), transform: `translate(${dx}px, ${dy}px) scale(${1 - 0.6 * outP})` }}>
                  {thumbs.length ? <Img src={staticFile(thumbs[(i * 5) % thumbs.length])} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} /> : null}
                  <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div style={{ width: 26, height: 26, borderRadius: 13, background: "rgba(0,0,0,.55)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg viewBox="0 0 24 24" width={16} height={16}><path d="M8 5v14l11-7z" fill="#fff" /></svg>
                    </div>
                  </div>
                  <div style={{ position: "absolute", right: 4, bottom: 3, fontSize: 11, fontWeight: 700, color: "#fff", background: "rgba(0,0,0,.7)", borderRadius: 3, padding: "0 4px" }}>{`${(i * 7) % 47 + 4}:${String((i * 13) % 60).padStart(2, "0")}`}</div>
                </div>
              );
            })}
          </div>
        </Card>
        {gone ? (
          <div style={{ position: "absolute", left: "50%", top: "50%", transform: `translate(-50%,-50%) scale(${interpolate(t, [tOneClass + 0.2, tOneClass + 0.5], [0.6, 1], { ...clamp, easing: ease })})`,
            opacity: interpolate(t, [tOneClass + 0.2, tOneClass + 0.45], [0, 1], clamp), background: accent, color: ink, borderRadius: 22, padding: "26px 44px",
            fontSize: 54, fontWeight: 850, whiteSpace: "nowrap", boxShadow: "0 18px 50px rgba(0,0,0,.4)", display: "flex", alignItems: "center", gap: 18 }}>
            <svg viewBox="0 0 24 24" width={54} height={54}><path d="M8 5v14l11-7z" fill={ink} /></svg>
            {tx(copy.wallAnswer)}
          </div>
        ) : null}
      </div>
    );
  };

  const wallShowing = tWall < 999 && t >= tWall - 0.12 && (beat === "hook" || beat === "bridge");
  const check = (size: number) => (
    <svg viewBox="0 0 24 24" width={size} height={size}><circle cx="12" cy="12" r="12" fill={accent} /><path d="M6.5 12.5l3.5 3.5 7.5-8" fill="none" stroke={ink} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" /></svg>
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", fontFamily: font, color: "#fff" }}>
      {segs.slice(0, c.shots.length).map((sg, i) => {
        const sh = c.shots[i];
        const from = Math.round(starts[sg.from] * fps);
        const to = i + 1 < segs.length && i + 1 < c.shots.length ? Math.round(starts[segs[i + 1].from] * fps) : durationInFrames;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)}>
            <AbsoluteFill style={{ transform: `scale(${interpolate(frame, [from, to], [1.0, 1.07], clamp)})` }}>
              <OffthreadVideo src={staticFile(sh.src)} startFrom={Math.round(sh.from * fps)} muted
                style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,.62) 0%, rgba(0,0,0,.38) 45%, rgba(0,0,0,.5) 100%)" }} />
      <Audio src={staticFile(c.vo)} />
      <Audio loop src={staticFile(c.bed)} volume={bedVol} />

      {/* the live session clip, with a speech-bubble tag pointing at the host's tile */}
      {ci && panelEnd > panelStart ? (
        <Sequence from={Math.round(panelStart * fps)} durationInFrames={Math.max(1, Math.round((panelEnd - panelStart) * fps))} layout="none">
          <div style={{ position: "absolute", top: tall ? 700 : 330, left: 0, right: 0, display: "flex", justifyContent: "center", ...enter(t, panelStart + 0.15, 60) }}>
            <div style={{ width: tall ? 900 : 860, display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 30, marginBottom: 16, width: "100%" }}>
                <div style={{ position: "relative", flex: "none", width: tall ? 300 : 290, height: ((tall ? 300 : 290) * (ci.tileH ?? 86)) / (ci.tileW ?? 158), borderRadius: 14,
                  overflow: "hidden", border: `5px solid ${accent}`, boxShadow: `0 0 28px ${accent}bf`,
                  transform: `scale(${interpolate(t, [panelStart + 0.1, panelStart + 0.35, panelStart + 0.6], [0.6, 1.06, 1], clamp)})`, transformOrigin: "left bottom" }}>
                  <OffthreadVideo src={staticFile(ci.host)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  {/* covers the recorded full-name label */}
                  <div style={{ position: "absolute", left: 6, bottom: 6, minWidth: (tall ? 300 : 290) * 0.5, background: accent, color: ink,
                    fontWeight: 800, fontSize: tall ? 28 : 24, padding: "4px 14px", borderRadius: 8 }}>{ci.hostName}</div>
                </div>
                <div style={{ position: "relative", flex: 1, background: accent, color: ink, fontWeight: 800,
                  fontSize: tall ? 40 : 34, lineHeight: 1.15, padding: "16px 24px", borderRadius: 20, boxShadow: "0 10px 30px rgba(0,0,0,.4)" }}>
                  {ci.tag}
                  <div style={{ position: "absolute", left: -19, top: "50%", marginTop: -16, width: 0, height: 0,
                    borderTop: "16px solid transparent", borderBottom: "16px solid transparent", borderRight: `20px solid ${accent}` }} />
                </div>
              </div>
              <ClassPanel ci={ci} width={tall ? 900 : 860} tall={tall} accent={accent} ink={ink} />
            </div>
          </div>
        </Sequence>
      ) : null}

      {/* persona callout, on screen from frame 0 */}
      <div style={{ position: "absolute", top: tall ? 180 : 28, left: 0, right: 0, display: "flex", justifyContent: "center" }}>{eyebrow}</div>

      {/* The spoken sentence, one line per phrase. A line slides in whole as its first word is said, so
          no line ever reflows, and each word lights from grey to white (or the accent) as it is spoken.
          Lines stack from the top, so lines already on screen never move. */}
      <div style={{ position: "absolute", top: textTop, left: 80, right: 80, display: "flex", flexDirection: "column", alignItems: align === "left" ? "flex-start" : "center", fontSize, fontWeight: weight, lineHeight: 1.14, letterSpacing: -1, textShadow: "0 3px 18px rgba(0,0,0,.45)" }}>
        {(sents[si] ? lines(sents[si], tall ? 24 : 30) : []).filter((ln) => t >= ln[0].s - 0.12).map((ln, li) => (
          <div key={`${si}-${li}`} style={{ textAlign: align, maxWidth: "100%", ...enter(t, ln[0].s, 34) }}>
            {ln.map((w, i) => {
              const said = t >= w.s - 0.04;
              const key = isKey(norm(w.w));
              return (
                <span key={i} style={{ color: said ? (key ? accentWord : "#fff") : "rgba(255,255,255,.42)" }}>
                  {isTotal(w.w) ? (
                    // the final figure reserves the width, so the count-up cannot shift the line
                    <span style={{ display: "inline-grid", fontVariantNumeric: "tabular-nums" }}>
                      <span style={{ gridArea: "1/1", visibility: "hidden" }}>{w.w}</span>
                      <span style={{ gridArea: "1/1", textAlign: "left" }}>{money}</span>
                    </span>
                  ) : w.w}
                  {i < ln.length - 1 ? " " : ""}
                </span>
              );
            })}
          </div>
        ))}
      </div>

      {/* one graphic per beat, each piece on its cue word */}
      <div style={{ position: "absolute", top: gfxTop, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
        <div style={{ transform: `scale(${k})`, transformOrigin: "top center" }}>
          {c.presenter && beat === "hook" && !wallShowing ? null : wallShowing ? (
            <Wall />
          ) : beat === "hook" && c.hook ? (
            (() => {
              const h = c.hook, tShow = at(h.show), tFade = h.fade ? at(h.fade) : 999, tLight = at(h.light, tShow < 999 ? tShow : 0);
              const mid = Math.floor(h.count / 2);
              return (
                <div style={{ display: "flex", gap: 44, alignItems: "flex-end" }}>
                  {Array.from({ length: h.count }, (_, i) => {
                    const lit = t >= tLight && (h.all || i === mid);
                    return (
                      <div key={i} style={enter(t, tShow + i * 0.06, 60)}>
                        {lit ? (
                          <div style={{ transform: `scale(${interpolate(t, [tLight + (h.all ? i * 0.02 : 0), tLight + 0.15, tLight + 0.45], [0.8, 1.12, 1], clamp)})` }}>
                            <Person fill={accent} ink={ink} label={AERIAL.hookLabel} size={150} font={AERIAL.font.family} />
                          </div>
                        ) : (
                          <div style={{ opacity: t >= tFade ? 0.55 : 1 }}><Person fill="#fff" dashed={t >= tFade} size={150} font={AERIAL.font.family} /></div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })()
          ) : beat === "hook" || beat === "bridge" ? (
            <div style={{ display: "flex", gap: 70, alignItems: "flex-end" }}>
              <div style={enter(t, tTwo, 60)}><Person fill="#fff" size={170} font={AERIAL.font.family} /></div>
              <div style={enter(t, tTwo + 0.12, 60)}>
                {t < tAI ? (
                  <div style={{ opacity: t >= tAfford ? 0.55 : 1 }}><Person fill="#fff" dashed={t >= tAfford} size={170} font={AERIAL.font.family} /></div>
                ) : (
                  <div style={{ transform: `scale(${interpolate(t, [tAI, tAI + 0.15, tAI + 0.45], [0.8, 1.12, 1], clamp)})` }}>
                    <Person fill={accent} ink={ink} label={AERIAL.hookLabel} size={170} font={AERIAL.font.family} />
                  </div>
                )}
              </div>
            </div>
          ) : beat === "identity" ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 30 }}>
              <div style={enter(t, tId + 0.1, 60)}>{byline(130)}</div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
                {([[AERIAL.platformMark, tx(copy.readersPill), tReaders, 22], [AERIAL.communityLogo, tx(copy.membersPill), tMembers, 14]] as [string, string, number, number][]).map(([src, label, cue, rad]) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", gap: 16, background: "#fff", color: "#111", borderRadius: 999, padding: "14px 30px 14px 16px",
                    fontSize: 40, fontWeight: 800, whiteSpace: "nowrap", boxShadow: "0 12px 34px rgba(0,0,0,.35)", ...enter(t, cue, 40) }}>
                    <Img src={staticFile(src)} style={{ width: 64, height: 64, borderRadius: rad }} />
                    {label}
                  </div>
                ))}
              </div>
            </div>
          ) : beat === "platform" ? (
            <Card style={{ display: "flex", alignItems: "center", gap: 28, padding: "30px 44px", ...enter(t, tSub, 80) }}>
              <Img src={staticFile(AERIAL.platformMark)} style={{ width: 110, height: 110, borderRadius: 22 }} />
              <div>
                <div style={{ fontSize: 50, fontWeight: 800 }}>{copy.newsletterTitle}</div>
                <div style={{ fontSize: 34, color: "#555" }}>{copy.newsletterSub}</div>
              </div>
              <div style={{ marginLeft: 16, background: accent, color: ink, fontWeight: 800, fontSize: 38, padding: "10px 22px", borderRadius: 999,
                ...enter(t, tFree, 30), transform: `${enter(t, tFree, 30).transform} scale(${interpolate(t, [tFree, tFree + 0.15, tFree + 0.4], [0.7, 1.15, 1], clamp)})` }}>{copy.freeBadge}</div>
            </Card>
          ) : beat === "community" ? (
            <Card style={{ width: 760, overflow: "hidden", ...enter(t, panelEnd > 0 ? panelEnd : tComm, 80) }}>
              <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "26px 36px 14px" }}>
                <Img src={staticFile(AERIAL.communityLogo)} style={{ width: 62, height: 62, borderRadius: 14 }} />
                <div style={{ fontSize: 44, fontWeight: 800, whiteSpace: "nowrap" }}>{copy.communityTitle}</div>
              </div>
              <div style={{ padding: "0 36px 22px", borderBottom: "2px solid #eee" }}>
                <span style={{ display: "inline-block", background: "#111", color: "#fff", fontSize: 30, fontWeight: 700, padding: "8px 20px", borderRadius: 999, ...enter(t, tThree, 20) }}>{tx(copy.cadence)}</span>
              </div>
              {rows.map((r) => (
                <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 36px", fontSize: 40, fontWeight: 600,
                  // rows sit faded until spoken, then light up (an invisible row left the card looking empty for ~3 s)
                  opacity: interpolate(t, [r.at - 0.1, r.at + 0.15], [0.28, 1], clamp),
                  transform: `scale(${interpolate(t, [r.at - 0.05, r.at + 0.15, r.at + 0.45], [1, 1.05, 1], clamp)})`, transformOrigin: "left center" }}>
                  {check(44)}
                  <span style={{ fontWeight: 800, minWidth: r.sub ? 110 : 0 }}>{r.label}</span>
                  {r.sub ? <span style={{ color: "#555", fontSize: 32 }}>{r.sub}</span> : null}
                </div>
              ))}
              {/* no identity beat in this script: the two counts ride under the rows instead */}
              {tId >= 999 && readers ? (
                <div style={{ display: "flex", gap: 14, padding: "6px 36px 22px", ...enter(t, tRowLast + 0.6, 16) }}>
                  {([[AERIAL.platformMark, tx(copy.readersChip), 8], [AERIAL.communityLogo, tx(copy.membersChip), 6]] as [string, string, number][]).map(([src, label, rad]) => (
                    <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, background: "#f1f1f1", borderRadius: 999, padding: "8px 18px 8px 10px", fontSize: 27, fontWeight: 700, color: "#222", whiteSpace: "nowrap" }}>
                      <Img src={staticFile(src)} style={{ width: 36, height: 36, borderRadius: rad }} />{label}
                    </div>
                  ))}
                </div>
              ) : null}
            </Card>
          ) : beat === "deals" ? (
            <Card style={{ padding: "34px 56px", textAlign: "center", ...enter(t, tDeals, 80) }}>
              <div style={{ fontSize: 110, fontWeight: 850, color: accent, letterSpacing: -3, fontVariantNumeric: "tabular-nums" }}>{money}</div>
              <div style={{ fontSize: 40, fontWeight: 600, ...enter(t, tMoney + 0.5, 20) }}>{tx(copy.dealsLine)}</div>
              {/* the live deals as a logo wall, so the total reads as a real bundle */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 118px)", justifyContent: "center", columnGap: 14, rowGap: 14, marginTop: 24 }}>
                {featured.map((f, i) => (
                  <div key={f.name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, ...enter(t, tMoney + 0.8 + i * 0.07, 24) }}>
                    <div style={{ width: 84, height: 84, borderRadius: 18, background: "#fff", border: "2px solid #eee", boxShadow: "0 3px 10px rgba(0,0,0,.10)",
                      display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                      <Img src={staticFile(f.src)} style={{ width: 64, height: 64, objectFit: "contain" }} />
                    </div>
                    <div style={{ fontSize: 19, fontWeight: 700, color: "#333", width: 118, textAlign: "center", lineHeight: 1.05 }}>{f.name}</div>
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 34 }}>
              <div style={enter(t, tClose, 60)}>{byline(120)}</div>
              <div style={{ background: accent, color: ink, fontSize: 54, fontWeight: 800, padding: "26px 64px", borderRadius: 999, boxShadow: "0 14px 40px rgba(0,0,0,.35)",
                ...enter(t, tClose + 0.15, 60),
                transform: `${enter(t, tClose + 0.15, 60).transform} scale(${t >= tPrice ? 1 + 0.07 * Math.max(0, Math.sin(((t - tPrice) / 0.55) * Math.PI)) * (t < tPrice + 1.65 ? 1 : 0) : 1})` }}>
                {c.button ?? tx(copy.button)}
              </div>
              <div style={{ fontSize: 40, fontWeight: 700, textShadow: "0 3px 14px rgba(0,0,0,.5)", ...enter(t, tCents, 20) }}>{tx(copy.perDay)}</div>
              {communityLine(34, enter(t, Math.max(tJoin, tCents + 0.4), 20))}
            </div>
          )}
        </div>
      </div>

      {c.presenter ? (() => {
        // Size per beat: big where the graphic is small, small behind the community and deals cards. In
        // 9x16 the presenter sits 200 px up so Meta's CTA over Reels and Stories never covers the face; in
        // 4x5 the feed CTA is under the video, so the presenter sits on the bottom edge.
        const W = 1080;
        const size: Record<string, number> = tall
          ? { hook: 1000, bridge: 580, identity: 600, platform: 720, community: 440, deals: 380, close: 700 }
          : { hook: 700, bridge: 400, identity: 420, platform: 480, community: 340, deals: 320, close: 460 };
        const side: Record<string, number> = { hook: 0.5, bridge: 1, identity: 0, platform: 1, community: 0, deals: 1, close: 0 };
        // the deals card runs down to ~1630 px, so there the presenter drops to the bottom edge
        const lift = (b: string) => (tall && b !== "hook" && b !== "deals" ? 200 : 0);
        const ks = c.presenter.scale ?? 1;
        const pose = (b: string) => { const w = (size[b] ?? size.community) * ks; return { w, x: side[b] === 0.5 ? (W - w) / 2 : side[b] ? W - w - 10 : 10, y: lift(b) }; };
        const gi = Math.max(0, segs.findIndex((g) => si >= g.from && si <= g.to));
        const from = pose(segs[Math.max(0, gi - 1)]?.beat ?? "hook"), to = pose(segs[gi]?.beat ?? "hook");
        const p = gi === 0 ? 1 : interpolate(t, [starts[segs[gi].from], starts[segs[gi].from] + 0.45], [0, 1], { ...clamp, easing: ease });
        const w = from.w + (to.w - from.w) * p, x = from.x + (to.x - from.x) * p, y = from.y + (to.y - from.y) * p;
        const show = interpolate(t, [c.voEnd + 0.1, c.voEnd + 0.5], [1, 0], clamp);
        return (
          <div style={{ position: "absolute", left: x, bottom: y, width: w, height: (w * 960) / 1080, opacity: show,
            // hands leave the source crop at the sides, and a lifted cutout ends in a line at the chest, so
            // the side edges always fade and the bottom fades once the presenter is off the bottom edge
            WebkitMaskImage: `linear-gradient(90deg, transparent 0%, #000 9%, #000 91%, transparent 100%), linear-gradient(180deg, #000 ${y > 0 ? (c.presenter.fadeFrom ?? 72) : 100}%, transparent 100%)`,
            WebkitMaskComposite: "source-in",
            filter: "drop-shadow(0 10px 30px rgba(0,0,0,.45))" }}>
            {c.presenter.clips.map((cl) => (
              <Sequence key={cl.src + cl.at} from={Math.round(cl.at * fps)} durationInFrames={Math.round(cl.dur * fps)} layout="none">
                <OffthreadVideo src={staticFile(cl.src)} transparent muted style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
              </Sequence>
            ))}
          </div>
        );
      })() : null}
    </AbsoluteFill>
  );
};
