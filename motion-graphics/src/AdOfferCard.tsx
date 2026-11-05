import React from "react";
import { AbsoluteFill, Audio, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { BRAND, OFFER, OFFER_CARD } from "./brand.mjs";
import { centsPerDay, fill, useFont } from "./fill";
import { Word } from "./AdRsvp";

/**
 * OfferCard: a static offer card, animated by the voiceover.
 *
 * Same layout as the static: byline (avatar or mark), headline, one line of two
 * benefits, the community card with its rows, the price button. Everything is on
 * screen from frame 0 so a muted scroll still reads the ad. The voiceover then
 * drives the motion: a shine crosses the headline, each benefit pops as it is
 * said, each card row grows while it is said, and the button pulses on the price.
 * Timings come from the Whisper word file, so a new voice needs only a new
 * words file.
 *
 * `captions` adds the spoken words, a short phrase at a time with the current
 * word in the caption accent. On 4:5 they sit under the button and the layout
 * moves up; on 9:16 they sit near the top and the layout moves down.
 *
 * No brand string, number, colour or logo path lives in this file: they are in
 * offer_card, offer_numbers and end_card in the brand's brand.json, or in the
 * ad's config.
 */

type Seg = { b: string; t: string };

export type OfferCardConfig = {
  offer?: "free" | "paid";
  vo: string;
  bed: string;
  bedVolume?: number;
  bg: string;            // card background colour; each version on its own colour
  dark: boolean;         // true = light text on a dark bg
  btnBg: string;
  brand: "person" | "logo";
  headline: string;
  lineA: Seg; lineB: Seg;   // b = bold part, t = the rest
  /** One row per spoken benefit. `cue` = the word that lights it. `logos` = a tile row under it. */
  rows: { pre?: string; bold?: string; post?: string; cue: string; logos?: { src: string; name: string }[] }[];
  cues: { lineA: string; lineB: string; price: string };
  voEnd: number;
  hold: number;
  captions?: boolean;
  eyebrow?: string;      // persona callout above the byline, on screen from frame 0
  perDay?: boolean;      // the per-day line under the button (OFFER_CARD.perDay)
  /** Default offer_numbers in brand.json. Verify before use. */
  readers?: string;
  price?: number;
  button?: string;       // default OFFER_CARD.button
};

export const durationOf = (c: OfferCardConfig) => c.voEnd + c.hold;

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
const cueAt = (words: Word[], key: string, after = 0, fallback = 0) =>
  words.find((w) => w.s >= after && norm(w.w).includes(norm(key)))?.s ?? fallback;

// Whisper splits "$1,250" into "$1" + ",250"; glue any token that starts with punctuation back on.
const glue = (words: Word[]) =>
  words.reduce<Word[]>((out, w) => {
    const last = out[out.length - 1];
    if (last && /^[,.%]/.test(w.w)) out[out.length - 1] = { w: last.w + w.w, s: last.s, e: w.e };
    else out.push({ ...w });
    return out;
  }, []);

// Caption phrases: split at punctuation into clauses, fold one- and two-word clauses into the next,
// then cut long clauses into even pieces of about five words. A piece never ends on a small word and
// never leaves one word alone, so no line hangs mid-thought.
const SMALL = /^(a|an|and|the|of|to|for|with|that|can|be|you|your|our|gives|plus)$/i;
const phrases = (words: Word[]) => {
  const clauses: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    if (/[,.?:!]$/.test(w.w)) { clauses.push(cur); cur = []; }
  }
  if (cur.length) clauses.push(cur);
  const merged: Word[][] = [];
  for (const c of clauses) {
    const last = merged[merged.length - 1];
    if (last && last.length <= 2 && last.length + c.length <= 6) merged[merged.length - 1] = [...last, ...c];
    else merged.push(c);
  }
  const out: Word[][] = [];
  for (const c of merged) {
    const size = Math.ceil(c.length / Math.ceil(c.length / 5));
    for (let i = 0; i < c.length; ) {
      let j = Math.min(c.length, i + size);
      while (j < c.length - 1 && SMALL.test(c[j - 1].w)) j++;
      if (c.length - j === 1) j = c.length;
      out.push(c.slice(i, j)); i = j;
    }
  }
  return out;
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const pop = (t: number, at: number) => interpolate(t, [at - 0.05, at + 0.15, at + 0.5], [1, 1.08, 1], clamp);

const fixWord = (w: string) =>
  OFFER_CARD.captionFixes.reduce((s, [re, flags, to]) => s.replace(new RegExp(re, flags), to), w);

const Captions: React.FC<{ words: Word[]; t: number; end: number; top: number; font: string }> = ({ words, t, end, top, font }) => {
  const ps = phrases(glue(words));
  const i = ps.findIndex((p, k) => t >= p[0].s && t < (k + 1 < ps.length ? ps[k + 1][0].s : end));
  if (i < 0) return null;
  const p = ps[i];
  const up = interpolate(t, [p[0].s, p[0].s + 0.12], [0.92, 1], clamp);
  return (
    <div style={{ position: "absolute", top, left: 0, right: 0, display: "flex", justifyContent: "center", padding: "0 60px" }}>
      <div style={{
        background: "rgba(17,17,17,.9)", borderRadius: 22, padding: "16px 30px", transform: `scale(${up})`,
        fontFamily: font, fontWeight: 800, fontSize: 56, lineHeight: 1.15,
        color: "#fff", textAlign: "center", letterSpacing: -0.5,
      }}>
        {p.map((w, k) => (
          <span key={k} style={{ color: t >= w.s && t < (p[k + 1]?.s ?? w.e + 0.25) ? OFFER_CARD.captionAccent : "#fff" }}>
            {fixWord(w.w)}{k < p.length - 1 ? " " : ""}
          </span>
        ))}
      </div>
    </div>
  );
};

export const AdOfferCard: React.FC<{ words: Word[]; c: OfferCardConfig; cover?: boolean }> = ({ words, c, cover }) => {
  useFont(OFFER_CARD.font);
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;
  const tall = height > 1600;
  const font = `${OFFER_CARD.font.family}, Helvetica, Arial, sans-serif`;
  const accent = OFFER_CARD.accent;

  const price = c.price ?? OFFER.price, readers = c.readers ?? OFFER.readers;
  const vars = { price, cents: centsPerDay(price), readers };
  const person = c.brand === "person" && !!BRAND.avatar;

  const ink = c.dark ? "#FFFFFF" : "#111111";
  const body = c.dark ? "rgba(255,255,255,.84)" : "#2B2B2B";
  const sub = c.dark ? "rgba(255,255,255,.74)" : "#3D3D3D";
  const shineColor = c.dark ? OFFER_CARD.shine.dark : OFFER_CARD.shine.light;

  const aAt = cueAt(words, c.cues.lineA, 0, 3);
  const bAt = cueAt(words, c.cues.lineB, aAt, 5);
  const rowAt = c.rows.map((r, i) => cueAt(words, r.cue, bAt, 7 + i * 2));
  const priceAt = cueAt(words, c.cues.price, rowAt[rowAt.length - 1], c.voEnd - 2);
  // the headline shine lands when the first spoken sentence ends
  const firstStop = words.findIndex((w) => /[.?!]$/.test(w.w));
  const headEnd = words.length ? words[firstStop >= 0 ? firstStop : Math.min(words.length - 1, 9)].e : 2.5;

  // shine: one pass as the ad opens, one as the headline is finished being said
  const shineA = interpolate(t, [0.25, 1.15], [130, -30], clamp);
  const shineB = interpolate(t, [headEnd, headEnd + 0.9], [130, -30], clamp);
  const shinePos = t < headEnd ? shineA : shineB;

  const intro = interpolate(t, [0, 0.35], [0.95, 1], clamp);
  const rowActive = (i: number) => t >= rowAt[i] && t < (i + 1 < rowAt.length ? rowAt[i + 1] : priceAt);
  const pulse = t >= priceAt ? 1 + 0.07 * Math.max(0, Math.sin(((t - priceAt) / 0.55) * Math.PI)) * (t < priceAt + 1.65 ? 1 : 0) : 1;
  const bedVol = (f: number) => {
    const tt = f / fps;
    const base = c.bedVolume ?? 0.12;
    return tt < c.voEnd ? base : Math.min(0.4, base + ((tt - c.voEnd) / 0.8) * (0.4 - base));
  };

  // with captions, 4:5 pushes the layout up to free the bottom band; 9:16 pushes it down to free the top
  const shift = c.captions && !cover ? (tall ? { paddingTop: 260 } : { paddingBottom: 190 }) : {};

  const check = (
    <svg viewBox="0 0 24 24" width={34} height={34} style={{ flex: "none" }}>
      <circle cx="12" cy="12" r="12" fill={accent} />
      <path d="M6.5 12.5l3.5 3.5 7.5-8" fill="none" stroke="#fff" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );

  return (
    <AbsoluteFill style={{ backgroundColor: c.bg, fontFamily: font, color: ink }}>
      <Audio src={staticFile(c.vo)} />
      <Audio loop src={staticFile(c.bed)} volume={bedVol} />
      <AbsoluteFill style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 80px", ...shift, transform: `scale(${intro * (c.captions && !cover && !tall ? 0.88 : 1)})` }}>
        {c.eyebrow ? (
          <div style={{ marginBottom: 26, background: accent, color: "#fff", fontWeight: 800, fontSize: 34, letterSpacing: 2,
            textTransform: "uppercase", padding: "10px 28px", borderRadius: 999 }}>{c.eyebrow}</div>
        ) : null}
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          {person ? (
            <Img src={staticFile(BRAND.avatar)} style={{ width: 150, height: 150, borderRadius: 75, border: `4px solid ${accent}`, objectFit: "cover" }} />
          ) : (
            <Img src={staticFile(OFFER_CARD.mark)} style={{ width: 150, height: 150, borderRadius: 75, boxShadow: "0 6px 20px rgba(0,0,0,.18)" }} />
          )}
          <div>
            <div style={{ fontWeight: 700, fontSize: 38 }}>{person ? OFFER_CARD.personName : BRAND.name}</div>
            <div style={{ fontSize: 27, color: sub }}>{fill(person ? OFFER_CARD.bylinePerson : OFFER_CARD.bylineLogo, vars)}</div>
          </div>
        </div>

        <h1 style={{
          marginTop: 40, textAlign: "center", fontWeight: 700, fontSize: 66, lineHeight: 1.1, letterSpacing: -1,
          maxWidth: 930, color: "transparent", textWrap: "balance" as any,
          backgroundImage: `linear-gradient(105deg, ${ink} 40%, ${shineColor} 50%, ${ink} 60%)`,
          backgroundSize: "300% 100%", backgroundPosition: `${shinePos}% 0`,
          WebkitBackgroundClip: "text", backgroundClip: "text",
        }}>{c.headline}</h1>

        <div style={{ marginTop: 26, textAlign: "center", fontSize: 31, color: body, whiteSpace: "nowrap" }}>
          <span style={{ display: "inline-block", transform: `scale(${pop(t, aAt)})` }}>
            <b style={{ color: ink, fontWeight: 600 }}>{c.lineA.b}</b>{c.lineA.t}
          </span><span style={{ display: "inline-block", width: 14 }} />
          <span style={{ display: "inline-block", transform: `scale(${pop(t, bAt)})` }}>
            <b style={{ color: ink, fontWeight: 600 }}>{c.lineB.b}</b>{c.lineB.t}
          </span>
        </div>

        <div style={{
          marginTop: 40, width: 800, background: "#fff", borderRadius: 14, boxShadow: "0 6px 24px rgba(0,0,0,.25)",
          transform: `scale(${pop(t, bAt) * 0.25 + 0.75})`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "22px 34px", borderBottom: "1.5px solid #ececec", font: "700 31px Helvetica, Arial, sans-serif", color: "#111" }}>
            <Img src={staticFile(OFFER_CARD.communityLogo)} style={{ width: 42, height: 42, borderRadius: 10 }} />
            {OFFER_CARD.cardTitle}
          </div>
          {c.rows.map((r, i) => {
            const on = rowActive(i);
            const grow = on ? interpolate(t, [rowAt[i], rowAt[i] + 0.18], [1, 1.04], clamp) : 1;
            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 16, padding: "19px 34px",
                borderBottom: i < c.rows.length - 1 ? "1.5px solid #f0f0f0" : "none",
                font: "400 31px Helvetica, Arial, sans-serif", color: "#222",
                background: on ? OFFER_CARD.rowHighlight : "#fff", transform: `scale(${grow})`, transformOrigin: "center center",
                borderRadius: on ? 10 : 0, boxShadow: on ? `inset 6px 0 0 ${accent}, 0 8px 22px rgba(0,0,0,.18)` : "none", position: "relative", zIndex: on ? 2 : 1,
              }}>
                {check}
                <div>
                  <span>{r.pre}{r.bold ? <b>{r.bold}</b> : null}{r.post}</span>
                  {r.logos ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 10, font: "600 26px Helvetica, Arial, sans-serif", color: "#333" }}>
                      {r.logos.map((l) => (
                        <span key={l.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Img src={staticFile(l.src)} style={{ width: 32, height: 32, borderRadius: 7, objectFit: "contain" }} />{l.name}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{
          marginTop: 40, background: c.btnBg, color: "#fff", fontWeight: 650, fontSize: 36,
          padding: "22px 60px", borderRadius: 999, transform: `scale(${pulse})`,
          boxShadow: t >= priceAt ? `0 0 0 8px ${accent}2e` : "none",
        }}>{c.button ?? fill(OFFER_CARD.button, vars)}</div>
        {c.perDay ? (
          <div style={{ marginTop: 16, fontSize: 30, fontWeight: 600, color: sub, opacity: t >= priceAt || cover ? 1 : 0.85 }}>{fill(OFFER_CARD.perDay, vars)}</div>
        ) : null}
      </AbsoluteFill>
      {c.captions && !cover ? <Captions words={words} t={t} end={c.voEnd} top={tall ? 300 : 1165} font={font} /> : null}
    </AbsoluteFill>
  );
};
