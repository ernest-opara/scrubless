/**
 * Brand tokens — kept in sync with scrubby/scrubless.css. Change once here
 * and every scene picks it up.
 */
export const theme = {
  // Surfaces
  bg: "#f2efe8", // warm cream
  bgCard: "#faf8f3",
  bgSoft: "#ebe7dd",
  bgDark: "#15161a",

  // Text
  fg: "#15161a",
  fgMuted: "#6c6a64",
  fgFaint: "#9c9a92",
  fgInverse: "#faf8f3",

  // Accent
  accent: "#4f46e5", // indigo — matches the landing
  accentSoft: "#ece9ff",
  accentInk: "#ffffff",

  // Lines & shadows
  line: "rgba(20, 18, 14, 0.10)",
  lineSoft: "rgba(20, 18, 14, 0.06)",
  shadowSm: "0 1px 2px rgba(20, 18, 14, 0.05)",
  shadowMd: "0 12px 36px rgba(20, 18, 14, 0.08)",

  // Typography
  fontDisplay:
    '"Instrument Serif", "Iowan Old Style", Georgia, serif',
  fontBody:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif',
  fontMono:
    'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};

export const FPS = 30;

/** Each scene's duration in frames, totalling 2250 (75s @ 30fps). */
export const SCENES = {
  PAIN: 120, //   4s — three scrubbing macros
  BRIDGE: 120, // 4s — cut to black, italic line
  REVEAL: 180, // 6s — landing fades up
  DEMO_SINGLE: 300, // 10s — type query, results, jump
  DEMO_LIBRARY: 300, // 10s — folder search
  DEMO_ASK: 300, // 10s — question + citation
  USE_CASES: 240, //  8s — four cutaways
  HEADLINE: 240, //  8s — "Search what was said..."
  CTA: 240, //  8s — Stop scrubbing. Start searching.
  STAMP: 210, //  7s — end card
} as const;

export const TOTAL_FRAMES = Object.values(SCENES).reduce((a, b) => a + b, 0);
