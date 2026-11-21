// Baseline policies: a race of mean rewards from -1 to +1 (reports/BASELINES.md),
// the terminal shows two real `run` commands on 5 fresh episodes.
import { reports } from "../data";
import { easeOut, seg } from "../engine/clock";
import { asWritten } from "../lib/format";
import { Label } from "./parts";
import type { VizProps } from "./types";

const RU: Record<string, string> = {
  oracle: "эталон (oracle)", vouchai_auditor: "скриптовый аудитор", simple_reconciler: "простая сверка",
  random_explorer: "случайный агент", flag_all: "«пометить всё»",
};
const NOTE: Record<string, string> = {
  oracle: "видит эталон — доказывает, что максимум достижим",
  vouchai_auditor: "знает правила генератора, видит только таблицы",
  simple_reconciler: "сверяет суммы — путает двойников с ошибками",
  random_explorer: "листает наугад",
  flag_all: "обвиняет всё подряд",
};

export default function Baselines({ p }: VizProps) {
  const t = reports.BASELINES?.sections?.[0]?.tables?.[0];
  const rows = t?.rows ?? [];
  const iR = t?.headers.findIndex((h) => h.includes("mean return")) ?? -1;
  const iF = t?.headers.findIndex((h) => h === "F1") ?? -1;
  return (
    <div className="flex h-full flex-col gap-4 p-5">
      <div className="flex items-end justify-between">
        <div><Label>средняя награда на 10 dev-эпизодах</Label>
          <div className="h-display mt-1 text-[28px]">Гонка политик</div></div>
        <div className="font-mono text-[11px] text-mute">−1 ← 0 → +1</div>
      </div>
      <div className="relative flex flex-1 flex-col justify-center gap-4">
        <div className="absolute inset-y-0 left-[calc(180px+((100%-180px)/2))] w-px bg-line2" />
        {rows.map((r, i) => {
          const v = Number(r[iR]);
          const x = easeOut(seg(p, 0.15 + i * 0.09, 0.45 + i * 0.09));
          const w = Math.abs(v) * 48 * x;
          const good = v > 0.5;
          return (
            <div key={i} className="grid grid-cols-[180px_1fr] items-center gap-0">
              <div className="pr-3">
                <div className="text-[13px] font-semibold">{RU[r[0]!] ?? r[0]}</div>
                <div className="text-[10.5px] leading-tight text-mute">{NOTE[r[0]!]}</div>
              </div>
              <div className="relative h-9">
                <div className="absolute inset-y-1 rounded-md" style={{
                  left: v >= 0 ? "50%" : `${50 - w}%`, width: `${w}%`,
                  background: good ? "linear-gradient(90deg,#1a6b4a,#3DDC97)" : "linear-gradient(270deg,#6b1f18,#FF4D3D)",
                  boxShadow: good ? "0 0 24px -4px #3DDC97" : "0 0 24px -6px #FF4D3D",
                }} />
                <div className="absolute inset-y-1 flex items-center px-2 font-mono text-[12px] font-bold text-void"
                  style={v >= 0 ? { left: "50%", width: `${w}%`, justifyContent: "flex-end" } : { left: `${50 - w}%`, width: `${w}%`, justifyContent: "flex-start" }}>
                  {x > 0.3 ? asWritten(r[iR] ?? "") : ""}
                </div>
                <div className="absolute inset-y-0 flex items-center font-mono text-[10px] text-mute"
                  style={v >= 0 ? { right: "52%" } : { left: "52%" }}>F1 {asWritten(r[iF] ?? "")}</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="rounded-xl border border-stamp/30 bg-stamp/5 p-3 text-[12.5px] text-soft">
        <b className="text-text">Зачем RL, если скрипт решает?</b> Скрипт написан теми, кто знает генератор. Агент этих знаний не получает —
        только таблицы и награду. Разрыв между «простой сверкой» и аудитором и есть сигнал обучения.
      </div>
    </div>
  );
}
