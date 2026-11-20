import type { Config } from "tailwindcss";

// The 16-colour palette of the game (tokens; used as bg-*, text-*, border-*).
export const palette = {
  night: "#120F1C",   // background
  deep: "#1E1A30",    // panels
  slate: "#2F2A4A",   // panel borders, tiles
  dusk: "#4B4475",    // inactive
  fog: "#9A93C0",     // muted text (AA on night)
  paper: "#EFE9D6",   // main text, receipts
  white: "#FFF8E6",
  stamp: "#D9473A",   // stamp red / FP
  ember: "#FF7A5C",   // explosions
  carbon: "#4E79E8",  // carbon blue / info
  sky: "#8FB2FF",
  leaf: "#3FAE5A",    // TP
  lime: "#A8E37A",
  gold: "#F4C64E",    // stars, coins
  amber: "#E8892E",
  wood: "#7B4B2D",
} as const;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    colors: { transparent: "transparent", current: "currentColor", ...palette },
    fontFamily: {
      // Press Start 2P: titles, buttons, big numbers (full Cyrillic; PT Mono covers the minus sign)
      arcade: ['"Press Start 2P"', '"PT Mono"', "monospace"],
      // PT Mono: every running text, table and label (clear Cyrillic)
      mono: ['"PT Mono"', "ui-monospace", "monospace"],
    },
    extend: {
      boxShadow: {
        px: "4px 4px 0 0 #000",
        pxs: "2px 2px 0 0 #000",
        inset: "inset 0 -4px 0 0 rgba(0,0,0,.35)",
      },
    },
  },
  plugins: [],
} satisfies Config;
