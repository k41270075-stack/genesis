// `attack-search`: 390 combined cheating policies fire at the reward and stop
// below the threshold; under them, the leak audit (AUC of meaningless features).
import { reports } from "../data";
import { easeOut, hash01, seg } from "../engine/clock";
import { facts } from "../lib/kit";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

const short = (s: string) => s.replace(/attack_/g, "").replace(/_/g, " ").replace(/ \+ first (\d+)/, " · первые $1");

export default function Attack({ p }: VizProps) {
  const top = reports.ATTACK_SEARCH?.sections?.[0]?.tables?.[0]?.rows ?? [];
  const thr = Number(facts.threshold ?? 0.2);
  const best = Number(facts.bestF1 ?? 0);
  const leak = reports.LEAK_AUDIT?.sections?.[0]?.tables?.[0]?.rows ?? [];
  const X = (f1: number) => `${(f1 / 0.3) * 100}%`;
  const swarm = Math.round((facts.attacks ?? 0) * easeOut(seg(p, 0.08, 0.5)));
  const leakX = (auc: number) => `${((auc - 0.35) / 0.3) * 100}%`;

  return (
    <div className="relative flex h-full flex-col gap-4 p-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Label>кандидатов-обманщиков проверено</Label>
          <div className="h-display tabnum mt-1 text-[44px] leading-none">{swarm}</div>
        </div>
        <div className="max-w-[300px] text-right text-[12px] text-mute">комбинации однострочных атак: И, ИЛИ, подстраховка суммы, лимиты обвинений; ни одна не читает эталон</div>
      </div>

      <div className="relative flex-1 rounded-xl border border-line bg-void/50 p-4">
        <div className="relative h-full min-h-[220px]">
          {/* swarm of all candidates: dots stuck under the wall */}
          {Array.from({ length: Math.min(swarm, 390) }, (_, i) => {
            const f = best * Math.pow(hash01(i * 3 + 1), 1.8);
            return <div key={i} className="absolute h-1 w-1 rounded-full bg-stamp/50" style={{ left: X(f), top: `${4 + hash01(i * 7) * 92}%` }} />;
          })}
          <div className="absolute inset-y-0 w-[3px] bg-gold shadow-[0_0_24px_#FFC34D]" style={{ left: X(thr) }}>
            <div className="absolute -top-1 left-2 whitespace-nowrap font-mono text-[10px] text-gold">порог F1 {String(thr).replace(".", ",")}</div>
          </div>
          <div className="absolute right-0 top-0 h-full w-[2px] bg-ok/50" />
          <div className="absolute bottom-full left-0 mb-1 font-mono text-[9px] text-mute">точки — все кандидаты (каждый левее лучшего F1 {facts.bestF1}); полосы — 6 лучших из отчёта</div>
          <div className="absolute right-2 top-1 text-right font-mono text-[10px] text-ok">честный аудитор →<br />F1 1,0 · +0,97</div>
          <div className="absolute inset-x-0 bottom-0 top-8 flex flex-col justify-end gap-1.5">
            {top.slice(0, 6).map((r, i) => {
              const f1 = Number(r[4]);
              const x = easeOut(seg(p, 0.45 + i * 0.05, 0.6 + i * 0.05));
              return (
                <div key={i} className="relative h-5">
                  <div className="absolute inset-y-0 left-0 rounded-r bg-gradient-to-r from-stamp/20 to-stamp" style={{ width: `calc(${X(f1)} * ${x})` }} />
                  {x >= 1 && <div className="absolute top-0 h-5 w-5 -translate-x-1/2 rounded-full border-2 border-gold/80" style={{ left: X(f1), opacity: 1 - seg(p, 0.6 + i * 0.05, 0.75 + i * 0.05) }} />}
                  <div className="absolute inset-y-0 left-2 flex items-center truncate pr-2 font-mono text-[10px] text-white/90" style={{ maxWidth: "60%" }}>{short(r[0] ?? "")}</div>
                  <div className="absolute inset-y-0 flex items-center pl-2 font-mono text-[10px] text-soft" style={{ left: `calc(${X(f1)} * ${x})` }}>{r[4]}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div>
        <div className="flex justify-between"><Label>аудит утечек: {leak.length} признаков без бухгалтерского смысла</Label>
          <span className="font-mono text-[10px] text-mute">AUC: 0,5 = подсказки нет</span></div>
        <div className="relative mt-2 h-10 rounded-lg border border-line bg-void/50">
          <div className="absolute inset-y-0 bg-ok/10" style={{ left: leakX(0.4), right: `calc(100% - ${leakX(0.6)})` }} />
          <div className="absolute inset-y-0 w-px bg-ok/60" style={{ left: leakX(0.5) }} />
          {leak.map((r, i) => {
            const auc = Number(r[r.length - 1]);
            const x = seg(p, 0.55 + (i / leak.length) * 0.25, 0.6 + (i / leak.length) * 0.25);
            return <div key={i} className="absolute h-2 w-2 -translate-x-1/2 rounded-full bg-blue" style={{ left: leakX(auc), top: `${15 + hash01(i * 5) * 60}%`, opacity: x }} />;
          })}
          <div className="absolute -bottom-4 font-mono text-[9px] text-mute" style={{ left: leakX(0.4) }}>0,4</div>
          <div className="absolute -bottom-4 font-mono text-[9px] text-mute" style={{ left: leakX(0.6) }}>0,6</div>
        </div>
      </div>
      <StampMark p={p} at={0.82} className="absolute right-10 top-28" size={28}>не пробили</StampMark>
    </div>
  );
}
