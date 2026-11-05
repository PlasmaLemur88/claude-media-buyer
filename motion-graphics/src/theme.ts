/**
 * Kept as a stable import path for components. THE PALETTE ITSELF LIVES IN
 * src/brand.mjs — edit it there. Two files holding colours is how a rebrand
 * ends up half-applied.
 */
export { DARK, PAPER } from "./brand.mjs";

export type Theme = {
  bg: string;
  ink: string;
  accent: string;
  muted: string;
  dim: string;
  captionBg: string;
  wordmark: string;
  scrimTo: string;
  readOnLarge: string;
};
