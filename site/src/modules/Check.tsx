// `python -m vouchai check`: 25 test modules light up around a ring as their
// PASS lines arrive; the centre counts the tests.
import { lineAt } from "../ui/Terminal";
import { easeOut, seg } from "../engine/clock";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

export default function Check({ run, lines, p }: VizProps) {
  const all = (run?.lines ?? []).map((l) => l[1]);
  const mods = all.map((s, i) => ({ i, m: /^PASS\s+(\S+)\s+(\d+) tests\s+([\d.]+)s/.exec(s) })).filter((x) => x.m) as { i: number; m: RegExpExecArray }[];
  const head = all[0] ?? "";
  const done = all.findIndex((s) => /^OK\s+\d+ tests/.test(s));
  const total = done >= 0 ? Number(/(\d+) tests/.exec(all[done]!)![1]) : 0;
  const passed = mods.filter((x) => x.i < lines).reduce((s, x) => s + Number(x.m[2]), 0);
  const N = mods.length || 1;
  const R = 150, r0 = 108;
  const arc = (k: number) => {
    const a0 = (k / N) * Math.PI * 2 - Math.PI / 2 + 0.012, a1 = ((k + 1) / N) * Math.PI * 2 - Math.PI / 2 - 0.012;
    const P = (rad: number, a: number) => `${200 + rad * Math.cos(a)} ${200 + rad * Math.sin(a)}`;
    return `M${P(R, a0)} A${R} ${R} 0 0 1 ${P(R, a1)} L${P(r0, a1)} A${r0} ${r0} 0 0 0 ${P(r0, a0)}Z`;
  };
  const last = mods.filter((x) => x.i < lines).pop();
  const pDone = done >= 0 ? lineAt(run, done) : 2;

  return (
    <div className="grid h-full items-center gap-4 p-5 md:grid-cols-[auto_1fr]">
      <div className="relative mx-auto aspect-square w-full max-w-[400px]">
        <svg viewBox="0 0 400 400" className="h-full w-full">
          <circle cx={200} cy={200} r={176} fill="none" stroke="#1D2231" strokeDasharray="2 6" />
          {mods.map((x, k) => {
            const on = x.i < lines;
            const t = easeOut(seg(p, lineAt(run, x.i) - 0.01, lineAt(run, x.i) + 0.03));
            return <path key={k} d={arc(k)} fill={on ? "#3DDC97" : "#141927"} fillOpacity={on ? 0.25 + 0.65 * t : 1}
              stroke={on ? "#3DDC97" : "#1D2231"} strokeWidth={1} style={on ? { filter: `drop-shadow(0 0 ${6 * t}px #3DDC97)` } : undefined} />;
          })}
          <circle cx={200} cy={200} r={176 * Math.min(1, 0.6 + seg(p, 0, 0.1) * 0.4)} fill="none" stroke="#3DDC97" strokeOpacity={0.15} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="h-display tabnum text-[54px] leading-none">{passed}</div>
            <div className="mt-1 font-mono text-[11px] text-mute">из {total || "…"} тестов</div>
          </div>
        </div>
        <StampMark p={p} at={pDone + 0.01} className="absolute bottom-6 right-0" size={22} color="#3DDC97" rotate={-8}>OK · exit 0</StampMark>
      </div>
      <div className="min-w-0 space-y-4">
        <div>
          <Label>одна команда проверки</Label>
          <div className="mt-2 font-mono text-[12px] text-soft">{head}</div>
          <div className="font-mono text-[12px] text-mute">{all[1]}</div>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px]">
          {mods.map((x, k) => (
            <div key={k} className={`flex justify-between gap-2 transition-colors ${x.i < lines ? "text-soft" : "text-line2"}`}>
              <span className="truncate">{x.i < lines ? "✓" : "·"} {x.m[1]}</span><span className="shrink-0">{x.m[2]}</span>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-line bg-void/60 px-4 py-3 text-[13px] text-soft">
          {last ? <>сейчас: <b className="text-text">{last.m[1]}</b> — {last.m[2]} тестов за {last.m[3]} с</> : "запуск…"}
        </div>
      </div>
    </div>
  );
}
