// `judge-recipes`: the jury's closed scenarios D01-D20 x 40 seeds = 800 episodes.
// The heat map is the measured report; the terminal shows a quick real run.
import { reports } from "../data";
import { easeOut, seg } from "../engine/clock";
import { facts, TYPE_RU } from "../lib/kit";
import { lineAt } from "../ui/Terminal";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

export default function Recipes({ p, lines, run }: VizProps) {
  const rows = reports.RECIPES?.sections?.[0]?.tables?.[0]?.rows ?? [];
  const seeds = Number(/\/(\d+)/.exec(rows[0]?.[rows[0].length - 1] ?? "")?.[1] ?? 40);
  const all = (run?.lines ?? []).map((l) => l[1]);
  const firstRow = all.findIndex((s) => /^\|\s*D\d\d\s*\|/.test(s));
  const pStart = firstRow >= 0 ? lineAt(run, firstRow) - 0.02 : 0.12;
  const sweep = easeOut(seg(p, pStart, 0.86));
  const waiting = p < pStart;
  const secs = run ? Math.round((run.ms / 1000) * Math.min(1, seg(p, 0.1, pStart))) : 0;
  const liveRows = all.slice(0, lines).filter((s) => /^\|\s*D\d\d\s*\|/.test(s)).length;
  const cells = Math.round(sweep * rows.length * seeds);
  const kind = (r: string[]) => {
    const t = r[3] ?? "";
    const k = Object.keys(TYPE_RU).find((x) => t.includes(x));
    return k ? TYPE_RU[k] : "чистая компания";
  };
  return (
    <div className="relative flex h-full flex-col gap-3 p-5">
      <div className="flex items-end justify-between">
        <div>
          <Label>{rows.length} сценариев × {seeds} seed</Label>
          <div className="h-display tabnum mt-1 text-[44px] leading-none">{cells}<span className="text-mute">/{rows.length * seeds}</span></div>
        </div>
        <div className="text-right text-[12px] text-mute">
          {waiting ? <span className="font-mono text-gold">● сборка эпизодов · {secs} с</span> : <>каждый эпизод: собран → проверен<br />vouchai_verify → oracle = 1,0</>}
        </div>
      </div>
      <div className="flex-1 space-y-[3px] overflow-hidden">
        {rows.map((r, i) => {
          const filled = Math.max(0, Math.min(seeds, cells - i * seeds));
          const err = !/clean/i.test(r[1] ?? "");
          return (
            <div key={i} className="grid grid-cols-[42px_120px_1fr] items-center gap-2">
              <span className={`font-mono text-[10.5px] ${i < liveRows ? "text-ok" : "text-soft"}`}>{r[0]}</span>
              <span className="truncate text-[10.5px] text-mute">{kind(r)}</span>
              <div className="grid gap-[2px]" style={{ gridTemplateColumns: `repeat(${seeds}, 1fr)` }}>
                {Array.from({ length: seeds }, (_, j) => (
                  <div key={j} className="h-[9px] rounded-[2px]" style={{
                    background: j < filled ? (err ? "#FF4D3D" : "#3DDC97") : "#141927",
                    opacity: j < filled ? 0.55 + 0.45 * ((j + i) % 3 === 0 ? 1 : 0.7) : 1,
                  }} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-4 text-[11px] text-mute">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-ok" />чистая компания: ошибок нет, награда за молчание</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-stamp" />спрятана ошибка нужного вида — эталон её нашёл</span>
      </div>
      <StampMark p={p} at={0.86} className="absolute bottom-3 right-6" size={30} color="#3DDC97">{facts.recipes ? `${facts.recipes.ok}/${facts.recipes.all}` : "—"}</StampMark>
    </div>
  );
}
