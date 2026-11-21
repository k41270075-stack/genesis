// The matcher against brute force: every bipartite graph up to 4 findings x 4
// issues. Small multiples flicker through graphs while the counter runs.
import { hash01, seg, easeOut } from "../engine/clock";
import { facts } from "../lib/kit";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

function Mini({ seed }: { seed: number }) {
  const nf = 1 + Math.floor(hash01(seed) * 4), ni = 1 + Math.floor(hash01(seed + 1) * 4);
  const edges: [number, number][] = [];
  for (let i = 0; i < nf; i++) for (let j = 0; j < ni; j++) if (hash01(seed * 31 + i * 7 + j) < 0.45) edges.push([i, j]);
  // greedy matching for the highlight (the real check is in the terminal)
  const usedI = new Set<number>(), usedJ = new Set<number>(), match: [number, number][] = [];
  edges.forEach(([i, j]) => { if (!usedI.has(i) && !usedJ.has(j)) { usedI.add(i); usedJ.add(j); match.push([i, j]); } });
  const y = (k: number, n: number) => 8 + (k + 0.5) * (44 / n);
  return (
    <svg viewBox="0 0 60 60" className="h-full w-full">
      {edges.map(([i, j], k) => <line key={k} x1={12} y1={y(i, nf)} x2={48} y2={y(j, ni)} stroke="#2A3145" strokeWidth={1.2} />)}
      {match.map(([i, j], k) => <line key={k} x1={12} y1={y(i, nf)} x2={48} y2={y(j, ni)} stroke="#3DDC97" strokeWidth={2} />)}
      {Array.from({ length: nf }, (_, i) => <circle key={i} cx={12} cy={y(i, nf)} r={3.2} fill="#5B8CFF" />)}
      {Array.from({ length: ni }, (_, j) => <circle key={j} cx={48} cy={y(j, ni)} r={3.2} fill="#FFC34D" />)}
    </svg>
  );
}

export default function Exhaustive({ p, run, lines }: VizProps) {
  const total = facts.graphs ?? 0;
  const done = (run?.lines ?? []).slice(0, lines).some((l) => /^OK/.test(l[1]));
  const n = Math.round(total * easeOut(seg(p, 0.1, done ? 0.75 : 0.9)));
  const frame = Math.floor(p * 160);
  return (
    <div className="relative flex h-full flex-col gap-4 p-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Label>графов «выводы × ошибки» до 4 × 4</Label>
          <div className="h-display tabnum mt-1 text-[48px] leading-none">{n.toLocaleString("ru-RU")}</div>
        </div>
        <div className="text-right">
          <Label>расхождений с перебором</Label>
          <div className="h-display mt-1 text-[48px] leading-none text-ok">0</div>
        </div>
      </div>
      <div className="grid flex-1 grid-cols-6 gap-2 sm:grid-cols-8">
        {Array.from({ length: 32 }, (_, k) => (
          <div key={k} className="aspect-square rounded-lg border border-line bg-void/60 p-1">
            <Mini seed={k * 1009 + frame * 37} />
          </div>
        ))}
      </div>
      <div className="text-[12px] text-mute">
        Для каждого графа максимальное паросочетание и правило выбора жюри (наименьшая последовательность issue_id, индекс)
        считаются двумя способами: нашим matcher и полным перебором всех паросочетаний. Плюс метаморфные свойства на случайных ответах.
      </div>
      <StampMark p={p} at={0.8} className="absolute bottom-24 right-10" size={30} color="#3DDC97">0 расхождений</StampMark>
    </div>
  );
}
