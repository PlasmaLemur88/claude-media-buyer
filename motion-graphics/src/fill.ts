import React from "react";
import { continueRender, delayRender, staticFile } from "remotion";

/**
 * Fill a brand copy template. "{price}" becomes the value of vars.price, and a
 * key that is not in vars is left as written, so a missing value shows up on
 * screen as "{members}" instead of silently printing nothing.
 */
export const fill = (s: string, vars: Record<string, string | number | undefined>) =>
  s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] === undefined ? m : String(vars[k])));

/** Yearly price in dollars to whole cents a day: 200 -> 55. */
export const centsPerDay = (price: number) => Math.round((price / 365) * 100);

/** Load a variable font once and hold the render until it is ready. */
export const useFont = (font: { family: string; file: string; weight: string }) => {
  const [handle] = React.useState(() => delayRender(font.family));
  React.useEffect(() => {
    if (!font.file) { continueRender(handle); return; }
    const f = new FontFace(font.family, `url(${staticFile(font.file)})`, { weight: font.weight });
    f.load().then((ff) => { document.fonts.add(ff); continueRender(handle); }).catch(() => continueRender(handle));
  }, [handle]);
};

/** Load every font file the brand lists (brand.json fonts.files) once, and
 *  hold the render until they are ready. A brand on system stacks lists none. */
export const useFonts = (fonts: { family: string; file: string; weight: string }[]) => {
  const [handle] = React.useState(() => (fonts.length ? delayRender("brand fonts") : null));
  React.useEffect(() => {
    if (handle === null) return;
    Promise.all(fonts.map((font) =>
      new FontFace(font.family, `url(${staticFile(font.file)})`, { weight: font.weight })
        .load().then((ff) => { document.fonts.add(ff); }).catch(() => undefined)))
      .then(() => continueRender(handle));
  }, [handle]);
};
