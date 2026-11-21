// `python -m vouchai demo`: the scripted auditor pages through the books with the
// five tools, submits receipts and is graded. Everything is parsed from the recording.
import { easeOut, seg } from "../engine/clock";
import { lineAt } from "../ui/Terminal";
import { num } from "../lib/format";
import { TYPE_RU } from "../lib/kit";
import { Appear, Gauge, Label, Odometer, StampMark } from "./parts";
import type { VizProps } from "./types";

const TABLE_RU: Record<string, string> = { invoices: "счета", payments: "платежи", fx: "курсы", ledger: "книга" };

export function parseDemo(all: string[]) {
  const ep = all.map((s) => /^Episode (\S+): (.+?) \(fictional\), base (\w+), time zone (\S+), period (\S+) \.\. (\S+)/.exec(s)).find(Boolean);
  const counts = all.map((s) => /^Ledger rows (\d+), invoices (\d+), payments (\d+)/.exec(s)).find(Boolean);
  const grader = all.findIndex((s) => s.startsWith("Grader:"));
  const g = grader >= 0 ? /TP (\d+), FP (\d+), FN (\d+), F1 ([\d.]+), reward ([-\d.]+)/.exec(all[grader]!) : null;
  return { ep, counts, grader, g };
}

export default function Demo({ run, lines, p }: VizProps) {
  const all = (run?.lines ?? []).map((l) => l[1]);
  const shown = all.slice(0, lines);
  const { ep, counts, grader, g } = parseDemo(all);
  const calls = shown.map((s) => /^\s+list_records\((\w+)\) -> (\d+) rows, (\d+) steps left/.exec(s)).filter(Boolean) as RegExpExecArray[];
  const left = calls.length ? Number(calls[calls.length - 1]![3]) : 100;
  const findings = shown.map((s) => /^\s+- (\w+) \[(.+?)\] (\d+) (\w+), (\d+) evidence IDs/.exec(s)).filter(Boolean) as RegExpExecArray[];
  const graded = grader >= 0 && lines > grader;
  const base = shown.map((s) => /^(\w+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+(\d+)\s+([\d.]+)$/.exec(s)).filter(Boolean) as RegExpExecArray[];
  const shelves = ["invoices", "payments", "fx", "ledger"];
  const pg = lineAt(run, grader);

  return (
    <div className="grid h-full gap-4 p-5 md:grid-cols-[1fr_230px]">
      <div className="flex min-h-0 flex-col gap-4">
        <Appear p={p} at={0.1} className="flex flex-wrap items-center gap-2">
          <span className="chip border-blue/40 text-sky">{ep?.[2] ?? "компания"}</span>
          <span className="chip">база {ep?.[3]}</span>
          <span className="chip">пояс {ep?.[4]}</span>
          <span className="chip">{ep?.[5]} → {ep?.[6]}</span>
          {counts && <span className="chip">{num(Number(counts[1]))} строк · {counts[2]} счетов · {counts[3]} платежей</span>}
        </Appear>

        <div className="grid flex-1 grid-cols-4 gap-3">
          {shelves.map((t) => {
            const pages = calls.filter((c) => c[1] === t);
            const active = calls.length > 0 && calls[calls.length - 1]![1] === t && !graded;
            return (
              <div key={t} className={`relative flex min-h-[150px] flex-col rounded-xl border p-2.5 transition-colors ${active ? "border-blue/70 bg-blue/5" : "border-line bg-void/40"}`}>
                <Label>{TABLE_RU[t]}</Label>
                <div className="mt-1 truncate font-mono text-[10px] text-mute">list_records("{t}")</div>
                <div className="relative mt-3 flex-1">
                  {pages.map((c, k) => (
                    <div key={k} className="absolute inset-x-0 rounded-md border border-paperInk/20 bg-paper px-2 py-1.5 text-paperInk shadow-card"
                      style={{ top: k * 18, transform: `rotate(${(k % 2 ? 1 : -1) * 0.8}deg)`, zIndex: k }}>
                      <div className="flex justify-between whitespace-nowrap font-mono text-[9.5px]"><span>с.{k + 1}</span><span>{c[2]} стр.</span></div>
                      <div className="mt-1 space-y-[3px]">
                        {Array.from({ length: 4 }, (_, j) => <div key={j} className="h-[3px] rounded bg-paperInk/25" style={{ width: `${55 + ((k * 7 + j * 13) % 40)}%` }} />)}
                      </div>
                    </div>
                  ))}
                  {active && <div className="absolute inset-x-0 h-0.5 bg-blue shadow-glowb" style={{ top: 18 * Math.max(0, pages.length - 1) + ((p * 4000) % 50) }} />}
                </div>
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          {findings.map((f, k) => (
            <Appear key={k} p={p} at={0} className="receipt rounded-t-md px-3 pt-2.5 text-[10.5px] leading-snug">
              <div className="font-bold">{TYPE_RU[f[1]!] ?? f[1]}</div>
              <div className="truncate text-paperInk/60">{f[2]!.replace(/'/g, "")}</div>
              <div className="mt-1 tabnum">{num(Number(f[3]) / 100, 2)} {f[4] === "KZT" ? "₸" : f[4]}</div>
              <div className="font-bold text-stamp">{f[5]} квитанции</div>
            </Appear>
          ))}
          {!findings.length && <div className="col-span-full rounded-xl border border-dashed border-line px-4 py-6 text-center text-[13px] text-mute">выводы появятся после submit</div>}
        </div>
      </div>

      <div className="flex flex-col items-center gap-4">
        <div className="text-center">
          <Label>осталось шагов</Label>
          <Odometer value={left} className="mt-2 justify-center" />
          <div className="mt-2 font-mono text-[11px] text-mute">из 100 · каждое действие = 1 шаг</div>
        </div>
        <div className={`relative transition-opacity duration-500 ${graded ? "opacity-100" : "opacity-20"}`}>
          <Gauge value={graded && g ? Number(g[5]) * easeOut(seg(p, pg, pg + 0.08)) : 0} size={210}
            label={g ? `TP ${g[1]} · FP ${g[2]} · FN ${g[3]} · F1 ${g[4]}` : "награда"} />
          {graded && <StampMark p={p} at={pg + 0.06} className="absolute -right-6 top-2" size={16}>доказано</StampMark>}
        </div>
        <div className="w-full space-y-1.5">
          {base.map((b, k) => {
            const r = Number(b[5]);
            return (
              <div key={k} className="grid grid-cols-[96px_1fr] items-center gap-2 font-mono text-[10px]">
                <span className="truncate text-soft">{b[1]}</span>
                <div className="relative h-2.5 rounded bg-line">
                  <div className="absolute top-0 h-full w-px bg-mute/60" style={{ left: "50%" }} />
                  <div className="absolute top-0 h-full rounded" style={{
                    left: r >= 0 ? "50%" : `${50 + r * 50}%`, width: `${Math.abs(r) * 50}%`, background: r >= 0.5 ? "#3DDC97" : "#FF4D3D",
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
