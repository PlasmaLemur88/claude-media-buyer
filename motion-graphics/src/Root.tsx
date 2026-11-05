import React from "react";
import { Composition, Still } from "remotion";
import { AdRsvp, FPS, durationOf as oneWordDuration, Word } from "./AdRsvp";
import { AdCaptions, durationOf as cardsDuration } from "./AdCaptions";
import { AdAerialKinetic, durationOf as aerialKineticDuration } from "./AdAerialKinetic";
import { AdOfferCard, durationOf as offerCardDuration } from "./AdOfferCard";
import { ADS } from "./configs.mjs";   // the active brand's ads

/**
 * Compositions are GENERATED from configs.mjs. Nothing here is hand-written per
 * ad, so a config entry and a render command cannot drift apart.
 *
 * Composition id:  <Format><number>-<HookStyle>-<OFFER>-<ratio>
 *                  e.g. OneWord101-Tell-FREE-9x16
 *                       Cards102-Tell-PAID-4x5
 *
 * build.sh builds the same string from the same fields.
 *
 * WHY HOOKSTYLE IS IN THE ID. Two arms of one concept can share a number, an
 * offer and a format and differ only in how they open — 401 Ask against 401
 * Tell. Without the hook style in the id they collide and one silently
 * overwrites the other. This is the same reason the delivery filename carries
 * it, and it is what replaced a bare V1/V2 counter that told you two files
 * differed but never what differed.
 */

/**
 * One entry per format. The `format` field in configs.mjs picks the component,
 * lands in the composition id, and lands in the output filename, so the three
 * cannot disagree. Adding a format is one line here plus its component file:
 * the ADS list, build.sh and the naming convention all need no change.
 *
 * Each component brings its own durationOf, because the end-card hold differs
 * per format. Both read FPS from AdRsvp, so the account is 30fps by
 * construction rather than by convention.
 *
 * Keys are the PLAIN-ENGLISH format names the delivery tree uses:
 *   OneWord  one word at a time, voiceover-synced  (RSVP, the Spritz technique)
 *   Cards    your graphics in sequence, voiceover  (captions over artwork)
 *   Aerial   plane footage, text block, silent     (scripts/render_aerial.py,
 *                                                  not Remotion: docs/40)
 *   AerialKinetic  aerial footage, kinetic spoken words, one graphic per beat
 *   OfferCard      an offer card animated by the voiceover
 *
 * `cover: true` also registers a still, <id>-cover, for the Ads Manager
 * thumbnail. Render it with `npx remotion still <id>-cover out/x.png`.
 */
const FORMATS: Record<
  string,
  { component: React.FC<any>; durationOf: (c: any) => number; cover?: boolean }
> = {
  OneWord: { component: AdRsvp, durationOf: oneWordDuration },
  Cards: { component: AdCaptions, durationOf: cardsDuration },
  AerialKinetic: { component: AdAerialKinetic, durationOf: aerialKineticDuration, cover: true },
  OfferCard: { component: AdOfferCard, durationOf: offerCardDuration, cover: true },
};

const RATIOS = [
  { name: "9x16", width: 1080, height: 1920 },
  { name: "4x5", width: 1080, height: 1350 },
];

export const RemotionRoot: React.FC = () => (
  <>
    {ADS.flatMap((ad) => {
      const fmt = FORMATS[ad.format];
      // Fail loudly rather than rendering the wrong format silently.
      if (!fmt) {
        throw new Error(
          `${ad.number}: unknown format "${ad.format}". ` +
          `Known: ${Object.keys(FORMATS).join(", ")}`
        );
      }
      const offer = (ad.config.offer ?? "free").toUpperCase();
      /**
       * The timings file defaults to the ad's own number, which is all a
       * one-voiceover-per-ad wave ever needs. Two arms of one number with
       * DIFFERENT voiceovers (an Ask cut and a Tell cut) have different
       * timings, and deriving the path from the number alone would silently
       * feed one arm the other's words. `words` overrides the stem for exactly
       * that case.
       *
       * `.json` stays OUTSIDE the template literal so webpack's context module
       * keeps its /\.json$/ filter and does not try to bundle the README that
       * sits in that folder.
       */
      const stem = ad.words ?? `${ad.number}${offer === "PAID" ? "_paid" : ""}`;
      const words: Word[] = require(`../public/brand-active/words/${stem}.json`);
      const hook = ad.hookStyle ?? "Tell";
      return RATIOS.flatMap((r) => {
        const id = `${ad.format}${ad.number}-${hook}-${offer}-${r.name}`;
        const comps = [
          <Composition
            key={id}
            id={id}
            component={fmt.component}
            durationInFrames={Math.round(fmt.durationOf(ad.config) * FPS)}
            fps={FPS}
            width={r.width}
            height={r.height}
            defaultProps={{ words, c: ad.config }}
          />,
        ];
        if (fmt.cover) {
          comps.push(
            <Still
              key={`${id}-cover`}
              id={`${id}-cover`}
              component={fmt.component}
              width={r.width}
              height={r.height}
              defaultProps={{ words, c: ad.config, cover: true }}
            />
          );
        }
        return comps;
      });
    })}
  </>
);
