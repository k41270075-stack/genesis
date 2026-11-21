// `replay`: every published trajectory is replayed step by step against a fresh
// environment; each observation must match byte for byte.
import { hash01, seg } from "../engine/clock";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

export default function Replay({ p, run, lines }: VizProps) {
  const all = (run?.lines ?? []).map((l) => l[1]);
  const m = all.map((s) => /OK - (\d+) transitions in (\d+) trajectories/.exec(s)).find(Boolean);
  const nT = m ? Number(m[2]) : 80, nS = m ? Number(m[1]) : 0;
  const done = lines >= all.length && all.length > 0;
  const head = seg(p, 0.12, done ? 0.85 : 0.88);
  const cols = 20, rows = Math.ceil(nT / cols);
  return (
    <div className="relative flex h-full flex-col gap-4 p-5">
      <div className="flex items-end justify-between">
        <div><Label>траекторий в trajectories.jsonl</Label>
          <div className="h-display tabnum mt-1 text-[48px] leading-none">{Math.round(nT * head)}<span className="text-mute">/{nT}</span></div></div>
        <div className="text-right"><Label>переходов сверено</Label>
          <div className="h-display tabnum mt-1 text-[48px] leading-none">{Math.round(nS * head).toLocaleString("ru-RU")}</div></div>
      </div>
      <div className="grid flex-1 content-center gap-2" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: rows * cols }, (_, k) => {
          if (k >= nT) return <div key={k} />;
          const at = k / nT;
          const ok = head > at;
          const len = 8 + Math.floor(hash01(k) * 18);
          return (
            <div key={k} className="flex h-14 flex-col justify-end gap-[2px] rounded-md border p-1"
              style={{ borderColor: ok ? "rgba(61,220,151,.5)" : "#1D2231", background: ok ? "rgba(61,220,151,.06)" : "transparent" }}>
              {Array.from({ length: Math.min(8, Math.ceil(len / 3)) }, (_, j) => (
                <div key={j} className="h-[3px] rounded" style={{ background: ok ? "#3DDC97" : "#2A3145", opacity: ok ? 0.5 + j * 0.06 : 1 }} />
              ))}
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-3 gap-3 text-[12px]">
        {[["действие", "из записи"], ["наблюдение", "сравнивается побайтно"], ["награда", "та же до дроби"]].map(([a, b]) => (
          <div key={a} className="rounded-xl border border-line p-3"><b>{a}</b><div className="text-mute">{b}</div></div>
        ))}
      </div>
      <StampMark p={p} at={0.88} className="absolute right-10 top-28" size={30} color="#3DDC97">воспроизведено точно</StampMark>
    </div>
  );
}
