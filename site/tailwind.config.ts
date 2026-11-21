import type { Config } from "tailwindcss";

// «Forensic noir»: a dark audit lab, thermal-receipt paper and one red stamp.
export const palette = {
  void: "#05060A",     // page background
  ink: "#0B0D13",      // panels
  panel: "#10131B",    // raised panels
  line: "#1D2231",     // hairlines
  line2: "#2A3145",    // borders on hover
  mute: "#8B93A7",     // secondary text (AA on void)
  soft: "#B9C0D0",
  text: "#ECEAE4",     // main text
  paper: "#F4EFE3",    // receipts
  paperInk: "#1A1712",
  stamp: "#FF4D3D",    // stamp red, FP, errors
  ember: "#FF8A5B",
  blue: "#5B8CFF",     // twins, information
  sky: "#9DB8FF",
  ok: "#3DDC97",       // TP, pass
  gold: "#FFC34D",
} as const;

export default {
  content: { relative: true, files: ["./index.html", "./src/**/*.{ts,tsx}"] },
  theme: {
    colors: { transparent: "transparent", current: "currentColor", black: "#000", white: "#fff", ...palette },
    fontFamily: {
      display: ['"PT Serif"', "Georgia", "serif"],
      sans: ['"Manrope Variable"', "system-ui", "sans-serif"],
      mono: ['"JetBrains Mono Variable"', "ui-monospace", "Consolas", "monospace"],
    },
    borderRadius: { none: "0", sm: "2px", DEFAULT: "4px", md: "5px", lg: "6px", xl: "8px", "2xl": "10px", "3xl": "12px", full: "9999px" },
    extend: {
      boxShadow: {
        glow: "0 0 0 1px rgba(255,77,61,.35), 0 0 40px -8px rgba(255,77,61,.55)",
        glowb: "0 0 0 1px rgba(91,140,255,.35), 0 0 40px -8px rgba(91,140,255,.5)",
        card: "0 30px 80px -30px rgba(0,0,0,.8)",
      },
    },
  },
  plugins: [],
} satisfies Config;
