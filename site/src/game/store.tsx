// Global game state: stars per level, calm mode (reduced motion), sound.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fx } from "./fx";
import { sound } from "./sound";

interface GameState {
  stars: Record<string, number>;
  award: (level: string, n: number) => void;
  calm: boolean;
  setCalm: (v: boolean) => void;
  soundOn: boolean;
  setSound: (v: boolean) => void;
}

const Ctx = createContext<GameState | null>(null);

function load(): Record<string, number> {
  try { return JSON.parse(localStorage.getItem("vouchai-stars") ?? "{}") as Record<string, number>; } catch { return {}; }
}

export function GameProvider({ children }: { children: ReactNode }) {
  const systemCalm = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [calm, setCalmState] = useState<boolean>(() => {
    try { const v = localStorage.getItem("vouchai-calm"); if (v) return v === "on"; } catch { /* storage off */ }
    return Boolean(systemCalm);
  });
  const [stars, setStars] = useState<Record<string, number>>(load);
  const [soundOn, setSoundOn] = useState(sound.on);

  useEffect(() => sound.subscribe(setSoundOn), []);
  useEffect(() => {
    fx.setCalm(calm);
    document.documentElement.classList.toggle("motion-off", calm);
  }, [calm]);

  const award = useCallback((level: string, n: number) => {
    setStars((s) => {
      const next = { ...s, [level]: Math.max(s[level] ?? 0, n) };
      try { localStorage.setItem("vouchai-stars", JSON.stringify(next)); } catch { /* storage off */ }
      return next;
    });
  }, []);
  const setCalm = useCallback((v: boolean) => {
    setCalmState(v);
    try { localStorage.setItem("vouchai-calm", v ? "on" : "off"); } catch { /* storage off */ }
  }, []);
  const setSound = useCallback((v: boolean) => sound.set(v), []);

  const value = useMemo(() => ({ stars, award, calm, setCalm, soundOn, setSound }), [stars, award, calm, setCalm, soundOn, setSound]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useGame(): GameState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useGame outside GameProvider");
  return v;
}
