// `judge-selftest`: the 80 checks of the jury (96 cells with our matcher tests)
// flip green as their rows appear in the real output.
import { reports } from "../data";
import { hash01, seg } from "../engine/clock";
import { lineAt } from "../ui/Terminal";
import { Label, Ripple, StampMark } from "./parts";
import type { VizProps } from "./types";

const BLOCK_RU = ["Контракт среды", "Сценарии D01–D20", "Matcher и награда", "Парные проверки"];

export default function Selftest({ run, lines, p }: VizProps) {
  const all = (run?.lines ?? []).map((l) => l[1]);
  const where = new Map<string, number>();
  all.forEach((s, i) => { const m = /^\|\s*([A-Za-z0-9_]+)\s*\|\s*(pass|fail)/.exec(s); if (m) where.set(m[1]!, i); });
  const blocks = (reports.JURY_SELFTEST?.sections ?? []).filter((s) => s.tables.length);
  const total = blocks.reduce((n, b) => n + (b.tables[0]?.rows.length ?? 0), 0);
  const on = (id: string) => { const i = where.get(id); return i !== undefined && i < lines; };
  const done = blocks.reduce((n, b) => n + (b.tables[0]?.rows.filter((r) => on(r[0]!)).length ?? 0), 0);
  const first = Math.min(...Array.from(where.values()));
  const waiting = lines <= first;
  const pEnd = lineAt(run, Math.max(...Array.from(where.values())));
  const secs = run ? Math.round((run.ms / 1000) * Math.min(1, seg(p, 0.1, lineAt(run, first)))) : 0;

  return (
    <div className="relative flex h-full flex-col gap-4 p-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Label>через judge_adapter.py — как у жюри</Label>
          <div className="h-display tabnum mt-1 text-[44px] leading-none">{done}<span className="text-mute">/{total}</span></div>
        </div>
        <div className="text-right font-mono text-[12px] text-mute">
          {waiting ? <span className="text-gold">● идёт прогон · {secs} с</span> : <span className="text-ok">● отчёт готов</span>}
        </div>
      </div>
      <div className="grid flex-1 content-start gap-4 sm:grid-cols-2">
        {blocks.map((b, bi) => {
          const rows = b.tables[0]?.rows ?? [];
          return (
            <div key={bi} className="rounded-xl border border-line bg-void/50 p-3">
              <div className="mb-2 flex justify-between text-[12px]"><b>{BLOCK_RU[bi] ?? b.heading}</b>
                <span className="font-mono text-mute">{rows.filter((r) => on(r[0]!)).length}/{rows.length}</span></div>
              <div className="grid grid-cols-10 gap-1">
                {rows.map((r, k) => {
                  const lit = on(r[0]!);
                  const shimmer = waiting ? 0.15 + 0.25 * hash01(k * 13 + bi * 101 + Math.floor(p * 60)) : 0;
                  return (
                    <div key={k} title={`${r[0]} · ${r[1]} · ${r[2]}`}
                      className="grid aspect-square place-items-center rounded-[4px] font-mono text-[8px] transition-all duration-300"
                      style={{ background: lit ? "#3DDC97" : `rgba(91,140,255,${shimmer})`, color: lit ? "#05060A" : "#2A3145",
                        boxShadow: lit ? "0 0 10px rgba(61,220,151,.6)" : "none", transform: lit ? "scale(1)" : "scale(.86)" }}>
                      {r[0]!.length <= 3 ? r[0] : ""}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="relative">
        <Ripple p={p} at={pEnd + 0.01} color="#3DDC97" className="left-[80%] top-[-80px]" />
      </div>
      <StampMark p={p} at={pEnd + 0.01} className="absolute bottom-8 right-8" size={42} color="#3DDC97">{done}/{total}</StampMark>
    </div>
  );
}
