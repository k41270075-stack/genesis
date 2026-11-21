// One module on stage: the picture on the left, the real terminal on the right,
// both driven by the same clock; transport controls at the bottom.
import { useMemo, useState } from "react";
import { usePlayback } from "../engine/clock";
import { earn } from "../game/passport";
import { ACCENT, type ModuleDef } from "../modules/types";
import { session } from "../terminal";
import { revealed, Terminal } from "./Terminal";

interface Props {
  mod: ModuleDef;
  index: number;
  total: number;
  auto?: boolean;
  compact?: boolean;
  onEnd?: () => void;
  /** externally driven progress (tour / recorder); the internal clock is ignored */
  pOverride?: number;
}

export function Stage({ mod, index, total, auto = false, compact = false, onEnd, pOverride }: Props) {
  const pb = usePlayback(mod.duration, !mod.interactive || auto, () => {
    if (!auto && pOverride === undefined) earn(`m:${mod.id}`);
    onEnd?.();
  });
  const p = pOverride ?? (mod.interactive && !auto ? 1 : pb.p);
  const run = useMemo(() => session(mod.runs), [mod.runs]);
  const lines = revealed(run, p);
  const [live, setLive] = useState<string[] | null>(null);
  const showLive = mod.interactive && !auto && live;
  const color = ACCENT[mod.accent];
  const { Viz } = mod;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <header className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div className="min-w-0">
          <div className="eyebrow">
            <span style={{ color }}>{String(index + 1).padStart(2, "0")}</span> / {total} · <span className="text-soft">$ {mod.cmd}</span>
          </div>
          <h3 className={`h-display mt-2 ${compact ? "text-[26px]" : "text-[clamp(26px,3vw,40px)]"}`}>{mod.title}</h3>
        </div>
        <p className="max-w-[640px] flex-1 text-[14px] leading-relaxed text-soft">{mod.about}</p>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="relative min-h-[360px] overflow-hidden rounded-lg border border-line bg-ink">
          <div className="absolute inset-x-0 top-0 h-[2px]" style={{ background: color }} />
          <div className="relative h-full">
            <Viz p={p} run={run} lines={lines} auto={auto} setLive={setLive} />
          </div>
        </div>
        <Terminal className="min-h-[280px]" run={showLive ? null : run} live={showLive ? live : undefined} p={p}
          title={showLive ? "живой вывод · тот же протокол" : run?.command}
          note={mod.note ? <div className="border-t border-line/70 px-4 py-1.5 text-[10px] text-mute/80">{mod.note}</div> : undefined} />
      </div>

      {!(mod.interactive && !auto) && pOverride === undefined && (
        <div className="flex items-center gap-3">
          <button className="grid h-10 w-10 place-items-center rounded border border-line2 hover:bg-white/5"
            onClick={pb.playing ? pb.pause : pb.play} aria-label={pb.playing ? "Пауза" : "Запустить"}>
            {pb.playing
              ? <svg width="12" height="12" viewBox="0 0 12 12"><rect x="2" y="1" width="3" height="10" fill="currentColor" /><rect x="7" y="1" width="3" height="10" fill="currentColor" /></svg>
              : <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2.5 1v10l8-5z" fill="currentColor" /></svg>}
          </button>
          <button className="grid h-10 w-10 place-items-center rounded border border-line2 hover:bg-white/5" onClick={pb.restart} aria-label="Сначала">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8a5 5 0 1 0 1.5-3.5M3 2v3h3" /></svg>
          </button>
          <input type="range" min={0} max={1000} value={Math.round(pb.p * 1000)} aria-label="Перемотка"
            onChange={(e) => { pb.pause(); pb.seek((Number(e.target.value) / 1000) * mod.duration); }}
            className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-line"
            style={{ background: `linear-gradient(to right, ${color} ${pb.p * 100}%, #1D2231 ${pb.p * 100}%)` }} />
          <button className="kbd hover:text-text" onClick={() => pb.setSpeed(pb.speed === 1 ? 2 : pb.speed === 2 ? 0.5 : 1)}>×{pb.speed}</button>
        </div>
      )}
    </div>
  );
}
