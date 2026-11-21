// `transform`: the jury's paired checks — every ID renamed, every table
// shuffled, times shifted; a correct grader must give the same reward.
import { useMemo } from "react";
import { easeInOut, hash01, seg } from "../engine/clock";
import { tablesOf } from "../lib/episode";
import { useKit } from "../lib/kit";
import { renameEpisode } from "../lib/rename";
import { Label, StampMark } from "./parts";
import type { VizProps } from "./types";

const ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

export default function Transform({ p, run }: VizProps) {
  const kit = useKit();
  const all = (run?.lines ?? []).map((l) => l[1]);
  const orig = /oracle reward ([\d.]+)/.exec(all.find((s) => s.startsWith("original")) ?? "")?.[1];
  const trans = /oracle reward ([\d.]+)/.exec(all.find((s) => s.startsWith("transformed")) ?? "")?.[1];
  const data = useMemo(() => {
    if (!kit) return null;
    const t = tablesOf(kit.ep);
    const r = renameEpisode(t, kit.ep.truth.issues, 7);
    const rows = t.ledger.slice(0, 9).map((row) => String(row.row_id));
    return { rows, map: r.map };
  }, [kit]);
  if (!data) return <div className="p-6 text-mute">загрузка…</div>;
  const n = data.rows.length;
  const morph = seg(p, 0.2, 0.55);
  const shuffle = easeInOut(seg(p, 0.55, 0.75));
  const order = data.rows.map((_, i) => i).sort((a, b) => hash01(a * 7 + 3) - hash01(b * 7 + 3));
  return (
    <div className="relative grid h-full gap-5 p-5 md:grid-cols-[1fr_260px]">
      <div className="flex flex-col">
        <Label>тот же приём в браузере · открытый эпизод, {n} строк книги</Label>
        <div className="relative mt-3 flex-1" style={{ minHeight: n * 40 }}>
          {data.rows.map((id, i) => {
            const target = data.map.get(id) ?? id;
            const k = Math.min(1, Math.max(0, morph * 1.6 - i * 0.07));
            const shownId = id.split("").map((c, j) => {
              const t = target[j] ?? "";
              if (k >= 1) return t;
              if (k <= 0) return c;
              return hash01(i * 97 + j * 13 + Math.floor(p * 500)) < k ? t : ALPH[Math.floor(hash01(i * 31 + j + Math.floor(p * 300)) * ALPH.length)];
            }).join("") + (k >= 1 ? target.slice(id.length) : "");
            const y = (1 - shuffle) * i + shuffle * order.indexOf(i);
            return (
              <div key={id} className="absolute inset-x-0 flex items-center gap-3 rounded-lg border border-line bg-void/60 px-3 py-2 font-mono text-[12px]"
                style={{ top: y * 40 }}>
                <span className="text-mute">{String(i + 1).padStart(2, "0")}</span>
                <span className={k > 0 && k < 1 ? "text-blue" : k >= 1 ? "text-gold" : "text-text"}>{shownId}</span>
                <span className="ml-auto h-1.5 rounded bg-line2" style={{ width: `${30 + hash01(i) * 40}%` }} />
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex flex-col justify-center gap-4">
        {[
          ["переименовать", "каждый ID → новый, взаимно однозначно", morph],
          ["перемешать", "строки всех таблиц в новом порядке", shuffle],
          ["сдвинуть время", "та же граница периода в другом поясе", seg(p, 0.75, 0.82)],
        ].map(([a, b, x], i) => (
          <div key={i} className="rounded-xl border border-line p-3" style={{ borderColor: (x as number) >= 1 ? "rgba(255,195,77,.5)" : undefined }}>
            <div className="text-[13px] font-semibold">{(x as number) >= 1 ? "✓ " : ""}{a as string}</div>
            <div className="text-[11px] text-mute">{b as string}</div>
          </div>
        ))}
        <div className="rounded-xl border border-ok/40 bg-ok/5 p-3 font-mono text-[12px]">
          <div className="text-mute">награда эталона</div>
          <div className="mt-1 flex justify-between"><span>до</span><b>{orig ?? "…"}</b></div>
          <div className="flex justify-between"><span>после</span><b className="text-ok">{p > 0.8 ? trans : "…"}</b></div>
        </div>
      </div>
      <StampMark p={p} at={0.84} className="absolute bottom-10 left-1/3" size={30} color="#FFC34D">награда та же</StampMark>
    </div>
  );
}
