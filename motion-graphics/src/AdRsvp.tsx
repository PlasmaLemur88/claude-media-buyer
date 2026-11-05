import React from "react";
import {
  AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { BRAND, DARK, FONTS, RSVP } from "./brand.mjs";
import { useFonts } from "./fill";

/**
 * RSVP subtitles. One word at a time, held at a FIXED point on near-black,
 * with the recognition letters carried in the accent colour.
 *
 * NOTHING BRAND-SPECIFIC LIVES IN THIS FILE. Colours, copy, type sizes and the
 * anchor all come from the active brand (brands/<slug>/brand.json, read through
 * src/brand.mjs). You should not need to open this one to rebrand.
 *
 * This is RSVP (rapid serial visual presentation), the Spritz technique — NOT
 * Bionic Reading, which is a different thing: bold-weighted word openings in
 * running text, where the mechanism is guiding your saccades along a line.
 * With a single word on screen there is no line to travel, so that mechanism
 * does nothing.
 *
 * THE WHOLE TRICK IS THE FIXED ANCHOR. The recognition letter sits at the same
 * x on every single word, and the word is laid out around it, so the eye never
 * moves and never re-hunts. An earlier build centred each word instead, which
 * slid the anchor left and right with word length and reintroduced exactly the
 * cost RSVP exists to remove. If you touch this file, keep the anchor fixed.
 *
 * Deliberately NOT silent. There is a voiceover, and the word on screen is the
 * word being spoken, cut from Whisper timings.
 */

export const FPS = 30;

export type Word = { w: string; s: number; e: number };

export type RsvpConfig = {
  /** Path under public/, e.g. "audio/vo_431.wav" */
  vo: string;
  /** Path under public/, e.g. "audio/bed_phrygian.wav" */
  bed: string;
  /** Where speech stops. The end card runs from here. timings.py prints it. */
  voEnd: number;
  /** "free" skips the offer entirely. One component serves both offers, so a
   *  change to the body lands once. */
  offer?: "free" | "paid";
  /** Paid only: where the body ends and the shared offer outro begins. */
  bodyEnd?: number;
  /** Optional background override, for a one-off look. */
  bg?: string;
};

export const durationOf = (c: RsvpConfig) =>
  c.voEnd + (c.offer === "paid" ? RSVP.paidEndCard : RSVP.freeEndCard);

/**
 * Whisper splits "12,000" into "12" + ",000" and "100%" into "100" + "%",
 * and leaves bare punctuation as its own token. Glue those back on to the word
 * before them — a lone ",000" flashed as a standalone word is the single
 * ugliest thing this format can do.
 */
function glue(words: Word[]): Word[] {
  const out: Word[] = [];
  for (const w of words) {
    const joinable = /^[,.]\d/.test(w.w) || /^[%.,!?;:]+$/.test(w.w);
    if (joinable && out.length) {
      const p = out[out.length - 1];
      out[out.length - 1] = { w: p.w + w.w, s: p.s, e: w.e };
    } else {
      out.push({ ...w });
    }
  }
  return out;
}

/**
 * Optimal Recognition Point — which character the eye should land on. Spritz's
 * table, keyed on letter count rather than string length so a trailing comma
 * does not shift the anchor within a word.
 */
function orpIndex(word: string): number {
  const letters = word.replace(/[^A-Za-z0-9']/g, "").length;
  let nth: number;
  if (letters <= 1) nth = 1;
  else if (letters <= 5) nth = 2;
  else if (letters <= 9) nth = 3;
  else if (letters <= 13) nth = 4;
  else nth = 5;

  let seen = 0;
  for (let i = 0; i < word.length; i++) {
    if (/[A-Za-z0-9']/.test(word[i])) {
      seen++;
      if (seen === nth) return i;
    }
  }
  return 0;
}

/** Type size by word length, from the brand config's bucket table. */
function sizeFor(word: string): number {
  const n = word.length;
  for (const [maxChars, px] of RSVP.sizes) if (n <= maxChars) return px;
  return RSVP.sizes[RSVP.sizes.length - 1][1];
}

/**
 * The word, laid out around a fixed anchor.
 *
 * Only the recognition letter sits in normal flow, so the wrapper's width is
 * that glyph's width and translateX(-50%) centres IT — not the word — on the
 * anchor. Head and tail hang off it absolutely and are free to be any length.
 */
const RsvpWord: React.FC<{ word: string; th: typeof DARK; width: number }> = ({
  word, th, width,
}) => {
  const i = orpIndex(word);
  const head = word.slice(0, i);
  const orp = word[i] ?? "";
  /**
   * Two coloured letters was the original ask, but on a three-letter word two
   * is most of the word and the accent stops reading as a fixation point at
   * all. Short words get none. "you" and "one" are a large share of this copy,
   * so this is not an edge case. Tunable in brand.json (rsvp).
   */
  const letters = word.replace(/[^A-Za-z0-9']/g, "").length;
  const accentRun = letters <= RSVP.shortWordMax ? 0 : RSVP.accentRun;
  const tailAccent = word.slice(i + 1, i + 1 + accentRun);
  const tail = word.slice(i + 1 + accentRun);
  const size = sizeFor(word);

  const type: React.CSSProperties = {
    fontFamily: BRAND.sans,
    fontWeight: 800,
    fontSize: size,
    lineHeight: 1,
    letterSpacing: "-0.02em",
    whiteSpace: "nowrap",
  };

  return (
    <div style={{
      position: "absolute", left: width * RSVP.anchor, top: "50%",
      transform: "translate(-50%, -50%)",
    }}>
      <span style={{
        ...type, position: "relative", display: "inline-block", color: th.accent,
      }}>
        <span style={{
          ...type, position: "absolute", right: "100%", top: 0, color: th.ink,
        }}>{head}</span>
        {orp}
        <span style={{ ...type, position: "absolute", left: "100%", top: 0 }}>
          <span style={{ color: th.accent }}>{tailAccent}</span>
          <span style={{ color: th.ink }}>{tail}</span>
        </span>
      </span>
    </div>
  );
};

export const AdRsvp: React.FC<{ words: Word[]; c: RsvpConfig }> = ({ words, c }) => {
  useFonts(FONTS);
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const th = DARK;
  const bg = c.bg ?? RSVP.bg;
  const paid = c.offer === "paid";

  const ws = React.useMemo(() => glue(words), [words]);

  const bed = (
    <>
      <Audio src={staticFile(c.vo)} />
      {/* Looped because a bed is often shorter than the read plus the end card.
          These are sustained drones with no percussion, so the wrap is not a
          downbeat and the loop point is inaudible. */}
      <Audio loop src={staticFile(c.bed)} volume={(f) => {
        const tt = f / FPS;
        return tt < c.voEnd
          ? RSVP.bedUnderVoice
          : Math.min(
              RSVP.bedUnderCard,
              RSVP.bedUnderVoice +
                ((tt - c.voEnd) / 0.6) * (RSVP.bedUnderCard - RSVP.bedUnderVoice)
            );
      }} />
    </>
  );

  if (t < c.voEnd) {
    // Hold the last spoken word through any gap rather than blanking the frame.
    // A black hole mid-read looks like a dropped render, not a pause.
    let i = ws.findIndex((w) => t >= w.s && t < w.e);
    if (i === -1) {
      for (let j = ws.length - 1; j >= 0; j--) if (t >= ws[j].s) { i = j; break; }
    }
    const cur = i === -1 ? null : ws[i];

    return (
      <AbsoluteFill style={{ backgroundColor: bg }}>
        {bed}
        {/* Marks where the body ends and the offer begins. Most of Meta plays
            muted, so the free/paid boundary has to survive with the sound off. */}
        {paid && c.bodyEnd !== undefined && t >= c.bodyEnd && BRAND.offerEyebrow && (
          <div style={{
            position: "absolute", top: height * 0.3, width: "100%",
            textAlign: "center", fontFamily: BRAND.sans, fontSize: 26,
            letterSpacing: "0.22em", textTransform: "uppercase", color: th.accent,
          }}>{BRAND.offerEyebrow}</div>
        )}
        {cur && <RsvpWord word={cur.w} th={th} width={width} />}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{
      backgroundColor: bg, justifyContent: "center", alignItems: "center",
      flexDirection: "column", gap: 18,
    }}>
      {bed}
      {BRAND.avatar && (
        <Img src={staticFile(BRAND.avatar)} style={{
          width: 230, height: 230, borderRadius: 115,
          border: `6px solid ${th.accent}`, objectFit: "cover", marginBottom: 12,
        }} />
      )}
      <div style={{ fontFamily: BRAND.serif, fontWeight: 700, fontSize: 98, color: th.ink }}>
        {BRAND.name}
      </div>
      <div style={{ fontFamily: BRAND.serif, fontSize: 38, color: th.muted }}>
        {paid ? BRAND.paidSubline : BRAND.freeSubline}
      </div>
      <div style={{
        marginTop: 26, background: th.accent, borderRadius: 14,
        padding: "26px 76px", fontFamily: BRAND.serif, fontWeight: 700,
        fontSize: 54, color: bg,
      }}>{BRAND.cta}</div>
      {paid && BRAND.paidFollowOn && (
        <div style={{ marginTop: 16, fontFamily: BRAND.serif, fontSize: 38, color: th.ink }}>
          {BRAND.paidFollowOn}
          {BRAND.paidFollowOnAccent && (
            <>{" "}<span style={{ color: th.accent, fontWeight: 700 }}>{BRAND.paidFollowOnAccent}</span></>
          )}
        </div>
      )}
      {BRAND.platformLabel && th.wordmark && (
        <div style={{
          marginTop: 34, display: "flex", flexDirection: "column",
          alignItems: "center", gap: 12,
        }}>
          <div style={{
            fontFamily: BRAND.sans, fontSize: 24, letterSpacing: "0.18em",
            textTransform: "uppercase", color: th.muted,
          }}>{BRAND.platformLabel}</div>
          <Img src={staticFile(th.wordmark)} style={{ width: 330 }} />
        </div>
      )}
    </AbsoluteFill>
  );
};
