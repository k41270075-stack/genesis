// A terminal pane that replays a real recording as a function of progress p.
import { useLayoutEffect, useRef, type ReactNode } from "react";
import { clamp01 } from "../engine/clock";
import { terminal, type Run } from "../terminal";

export const TYPE_END = 0.08;
const OUT_A = 0.1, OUT_B = 0.9;
/** Fast commands (a few seconds) are paced line by line: their timings carry no story. */
const FAST_MS = 3000;
const at = (run: Run, i: number): number => {
  const n = run.lines.length;
  if (run.ms < FAST_MS) return (i + 1) / n;
  // a quarter real time (the long silence while a command works stays visible), three quarters line order
  return 0.25 * Math.min(1, run.lines[i]![0] / Math.max(1, run.ms)) + 0.75 * ((i + 1) / n);
};

/** How many output lines of `run` are visible at progress p (shared with the pictures). */
export function revealed(run: Run | null, p: number): number {
  if (!run || p < OUT_A) return 0;
  const q = clamp01((p - OUT_A) / (OUT_B - OUT_A));
  const n = run.lines.length;
  let k = 0;
  for (let i = 0; i < n; i++) {
    if (at(run, i) <= q + 1e-9) k = i + 1; else break;
  }
  return k;
}

/** The progress at which output line i (0-based) of `run` appears. */
export function lineAt(run: Run | null, i: number): number {
  if (!run || !run.lines.length) return 1;
  const n = run.lines.length;
  const k = Math.max(0, Math.min(n - 1, i));
  return OUT_A + at(run, k) * (OUT_B - OUT_A);
}

const RULES: [RegExp, string][] = [
  [/^\$ .*/, "text-text"],
  [/\b(FAIL(ED)?|ERROR|Traceback|refused|exit [1-9])\b/i, "text-stamp"],
  [/\b(pass(ed)?|ok|OK|PASS)\b|✓|\bmatch(es|ed)?\b/, "text-ok"],
];

function paint(s: string): ReactNode {
  for (const [re, cls] of RULES) if (re.test(s)) return <span className={cls}>{s || " "}</span>;
  // numbers like +0.97 / 96/96 stand out
  const parts = s.split(/([+-]?\d+(?:[.,]\d+)?(?:\/\d+)?)/g);
  return parts.map((x, i) => (i % 2 ? <span key={i} className="text-sky">{x}</span> : x));
}

interface Props {
  run?: Run | null;
  p?: number;
  /** live lines (interactive modules) instead of a recording */
  live?: string[];
  title?: string;
  className?: string;
  note?: ReactNode;
}

export function Terminal({ run = null, p = 1, live, title, className = "", note }: Props) {
  const body = useRef<HTMLDivElement>(null);
  const cmd = run?.command ?? "";
  const typed = live ? "" : cmd.slice(0, Math.round(cmd.length * clamp01(p / TYPE_END)));
  const k = live ? 0 : revealed(run, p);
  const done = !live && run && k >= run.lines.length && p >= OUT_B;
  const lines = live ?? run?.lines.slice(0, k).map((l) => l[1]) ?? [];

  useLayoutEffect(() => {
    const el = body.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length, typed.length]);

  return (
    <div className={`term relative flex min-h-0 flex-col overflow-hidden rounded-lg border border-line ${className}`}>
      <div className="flex items-center gap-2 border-b border-line/80 bg-black/30 px-4 py-2.5">
        <span className="text-[11px] text-ok">~/vouchai</span>
        <span className="truncate text-[11px] text-mute">{title ?? "terminal"}</span>
        <span className="ml-auto hidden shrink-0 text-[10px] uppercase tracking-widest text-mute/70 sm:block">
          {live ? "живой вывод · в браузере" : "запись реального вывода"}
        </span>
      </div>
      <div ref={body} className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-3 text-soft">
        {!live && (
          <div className="whitespace-pre-wrap break-all text-text">
            <span className="text-ok">vouchai</span><span className="text-mute">:~$ </span>{typed}
            {p < TYPE_END + 0.02 && <span className="caret" />}
          </div>
        )}
        {lines.map((s, i) => (
          <div key={i} className="whitespace-pre-wrap break-all">{paint(s)}</div>
        ))}
        {(live || (run && !done && p >= TYPE_END)) && <span className="caret opacity-70" />}
        {done && (
          <div className="mt-1 text-text">
            <span className="text-mute">exit {run!.exit} · {(run!.ms / 1000).toFixed(1)} с реального времени</span>
            <br /><span className="text-ok">vouchai</span><span className="text-mute">:~$ </span><span className="caret" />
          </div>
        )}
      </div>
      {note !== undefined ? note : !live && (
        <div className="border-t border-line/70 px-4 py-1.5 text-[10px] text-mute/80">записано: {terminal.recorded_on} · ускорено</div>
      )}
    </div>
  );
}
