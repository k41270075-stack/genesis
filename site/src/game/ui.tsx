// Pixel UI primitives: buttons, panels, typewriter dialog, bars, stamps.
import { motion } from "framer-motion";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { loadEpisode, type EpisodeData } from "../lib/episode";
import { fx } from "./fx";
import { play, type Sfx } from "./sound";
import { useGame } from "./store";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "gold" | "red" | "blue" | "green" | "ghost"; sfx?: Sfx };
export function PxButton({ tone = "gold", sfx = "blip", className = "", onClick, ...rest }: BtnProps) {
  const cls = { gold: "", red: "px-btn--red", blue: "px-btn--blue", green: "px-btn--green", ghost: "px-btn--ghost" }[tone];
  return (
    <button type="button" {...rest} className={`px-btn ${cls} ${className}`}
      onClick={(e) => { play(sfx); onClick?.(e); }} />
  );
}

export function Panel({ children, className = "", paper = false }: { children: ReactNode; className?: string; paper?: boolean }) {
  return <div className={`${paper ? "px-paper" : "px-panel"} p-4 ${className}`}>{children}</div>;
}

/** Dialog text that types itself; click or any key shows it whole; calm mode = instant. */
export function Typewriter({ text, speed = 22, className = "", onDone }: { text: string; speed?: number; className?: string; onDone?: () => void }) {
  const { calm } = useGame();
  const [n, setN] = useState(calm ? text.length : 0);
  const done = useRef(onDone);
  done.current = onDone;
  const fired = useRef(false);
  useEffect(() => { setN(calm ? text.length : 0); fired.current = false; }, [text, calm]);
  useEffect(() => {
    if (n >= text.length) {
      if (!fired.current) { fired.current = true; done.current?.(); }
      return;
    }
    const id = window.setTimeout(() => { setN((v) => Math.min(text.length, v + 2)); if (n % 6 === 0) play("type"); }, speed);
    return () => window.clearTimeout(id);
  }, [n, text, speed]);
  return (
    <p className={className} onClick={() => setN(text.length)} aria-label={text}>
      <span aria-hidden="true">{text.slice(0, n)}{n < text.length && <span className="blink">▌</span>}</span>
    </p>
  );
}

/** Speech box with a pixel tail, for tutorial tips and the boss. */
export function Say({ who, children, tone = "paper" }: { who?: string; children: ReactNode; tone?: "paper" | "red" }) {
  return (
    <div className={`${tone === "red" ? "bg-stamp text-white" : "bg-paper text-night"} relative px-4 py-3 shadow-px`}>
      {who && <div className="font-arcade text-[14px] uppercase mb-1 opacity-80">{who}</div>}
      <div className="text-[17px] leading-snug">{children}</div>
    </div>
  );
}

/** Segmented pixel bar (energy, HP). */
export function Bar({ value, max, cells = 20, color = "bg-leaf", label, mark }: {
  value: number; max: number; cells?: number; color?: string; label?: string; mark?: number;
}) {
  const on = Math.ceil((Math.max(0, value) / max) * cells - 1e-9);
  return (
    <div className="flex items-center gap-2" role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
      <div className="relative flex gap-[2px] bg-black p-[3px]">
        {Array.from({ length: cells }, (_, i) => (
          <span key={i} className={`block h-3 w-[6px] sm:w-2 ${i < on ? color : "bg-slate"}`} />
        ))}
        {mark !== undefined && (
          <span className="absolute -top-1 -bottom-1 w-[3px] bg-white" style={{ left: `${3 + (mark / max) * (cells * 8)}px` }} />
        )}
      </div>
    </div>
  );
}

/** A stamp that slams down: shake + sound. */
export function Stamp({ text, tone = "red", rotate = -8, big = false }: { text: string; tone?: "red" | "blue" | "green"; rotate?: number; big?: boolean }) {
  const { calm } = useGame();
  const color = { red: "text-stamp border-stamp", blue: "text-sky border-sky", green: "text-lime border-lime" }[tone];
  useEffect(() => { play("stamp"); fx.shake(); }, []);
  return (
    <motion.div
      initial={calm ? false : { scale: 2.4, opacity: 0, rotate: rotate - 10 }}
      animate={{ scale: 1, opacity: 0.95, rotate }}
      transition={{ type: "spring", stiffness: 520, damping: 18 }}
      className={`inline-block border-4 border-double ${color} font-arcade uppercase ${big ? "text-base sm:text-xl px-4 py-3" : "text-[14px] sm:text-[14px] px-3 py-2"} pointer-events-none mix-blend-normal`}
      role="status"
    >
      {text}
    </motion.div>
  );
}

/** Loads the demo episode lazily (public tables + demo truth). */
export function useEpisode(): EpisodeData | null {
  const [ep, setEp] = useState<EpisodeData | null>(null);
  useEffect(() => { let live = true; void loadEpisode().then((e) => { if (live) setEp(e); }); return () => { live = false; }; }, []);
  return ep;
}

export function Loading() {
  return <div className="font-arcade text-[14px] text-fog p-8">ЗАГРУЗКА<span className="blink">…</span></div>;
}

export function Cmd({ children }: { children: string }) {
  return (
    <code className="block font-mono text-[14px] bg-black/60 text-lime px-3 py-2 overflow-x-auto whitespace-pre scroll-thin">
      <span className="text-fog select-none">$ </span>{children}
    </code>
  );
}

/** A number taken from data, with where it came from on hover/focus. */
export function Num({ children, src, className = "" }: { children: ReactNode; src: string; className?: string }) {
  return <span className={`font-arcade ${className}`} title={`источник: ${src}`}>{children}</span>;
}

export const HONEST = "В демо эталон лежит в браузере, в среде он за стеной процесса.";
