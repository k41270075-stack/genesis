// One playback clock for every visualisation: the picture and the terminal are
// pure functions of the time `t` (ms), so they stay in sync, can be scrubbed,
// and a recorder that controls requestAnimationFrame gets identical frames.
import { useCallback, useEffect, useRef, useState } from "react";

/** Time source: a screen recorder may set `window.__videoNow` to step time frame by frame. */
const now = (): number => {
  const f = (window as unknown as { __videoNow?: () => number }).__videoNow;
  return typeof f === "function" ? f() : performance.now();
};

export interface Playback {
  t: number;
  p: number;
  duration: number;
  playing: boolean;
  speed: number;
  play: () => void;
  pause: () => void;
  restart: () => void;
  seek: (ms: number) => void;
  setSpeed: (s: number) => void;
}

export function usePlayback(duration: number, autoplay = true, onEnd?: () => void): Playback {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(autoplay);
  const [speed, setSpeed] = useState(1);
  const tRef = useRef(0);
  const endRef = useRef(onEnd);
  endRef.current = onEnd;

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = now();
    const tick = () => {
      const n = now();
      const next = Math.min(duration, tRef.current + (n - last) * speed);
      last = n;
      tRef.current = next;
      setT(next);
      if (next >= duration) {
        setPlaying(false);
        endRef.current?.();
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration, speed]);

  const seek = useCallback((ms: number) => {
    tRef.current = Math.max(0, Math.min(duration, ms));
    setT(tRef.current);
  }, [duration]);
  const restart = useCallback(() => { tRef.current = 0; setT(0); setPlaying(true); }, []);
  const play = useCallback(() => {
    if (tRef.current >= duration) { tRef.current = 0; setT(0); }
    setPlaying(true);
  }, [duration]);
  const pause = useCallback(() => setPlaying(false), []);

  return { t, p: duration ? t / duration : 1, duration, playing, speed, play, pause, restart, seek, setSpeed };
}

/** Free-running time since mount (ms), for ambient motion. */
export function useTime(active = true): number {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    const start = now();
    const tick = () => { setT(now() - start); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active]);
  return t;
}

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
/** Local progress of a window [a, b] of the global progress. */
export const seg = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
export const easeInOut = (x: number) => { const v = clamp01(x); return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2; };
export const backOut = (x: number) => { const v = clamp01(x), c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(v - 1, 3) + c1 * Math.pow(v - 1, 2); };
export const lerp = (a: number, b: number, x: number) => a + (b - a) * x;

/** Deterministic pseudo-random in [0, 1) from an integer. */
export const hash01 = (i: number) => {
  let x = (i | 0) * 374761393 + 668265263;
  x = (x ^ (x >>> 13)) * 1274126177;
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
};

export function useInView<T extends Element>(threshold = 0.35): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver(([e]) => { if (e?.isIntersecting) { setSeen(true); io.disconnect(); } }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [seen, threshold]);
  return [ref, seen];
}
