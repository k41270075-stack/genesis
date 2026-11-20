// Level 7 «Монета»: the leak audit. A fair coin has AUC 0.5; every "empty"
// feature of reports/LEAK_AUDIT.md lands as a coin inside the corridor.
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { col, commandOf, findTable, reports, sampleOf } from "../data";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Cmd, PxButton, Say } from "../game/ui";
import { asWritten, num } from "../lib/format";
import { Coin3D, Scene3D } from "../three/lazy";

const FEATURE_RU: Record<string, string> = {
  amount_last_digit: "последняя цифра суммы", id_first_symbol: "первый символ ID", id_last_symbol: "последний символ ID",
  lookalikes_nearby: "похожие документы рядом", minute_of_hour: "минута часа", notes_text: "текст примечания",
  position_in_table: "позиция в таблице", round_amount: "круглая сумма", seconds_of_minute: "секунды", weekday: "день недели",
};

export default function L07Coin({ finish }: LevelProps) {
  const { calm } = useGame();
  const t = findTable("LEAK_AUDIT", "AUC");
  const rep = reports.LEAK_AUDIT;
  const boundText = [...(rep?.intro ?? []), rep?.meta?.command ?? ""].join(" ");
  const bound = Number(/\|AUC\s*-\s*0\.5\|\s*<=\s*(\d+(?:\.\d+)?)/.exec(boundText)?.[1] ?? NaN);
  const sample = sampleOf("LEAK_AUDIT");
  const rows = useMemo(() => {
    if (!t) return [];
    const g = col(t, "Error type"), f = col(t, "Feature"), auc = col(t, "AUC"), pos = col(t, "Positives"), ctl = col(t, "Controls");
    return t.rows.map((r) => ({ group: g(r), feature: f(r), auc: auc(r), pos: pos(r), ctl: ctl(r) }));
  }, [t]);
  const groups = useMemo(() => Array.from(new Set(rows.map((r) => r.group))), [rows]);
  const [flips, setFlips] = useState(0);
  const [landed, setLanded] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);

  if (!t || !rows.length) return <Say>В reports/LEAK_AUDIT.md нет таблицы AUC.</Say>;
  const worst = rows.reduce((w, r) => (Math.abs(Number(r.auc) - 0.5) > Math.abs(Number(w.auc) - 0.5) ? r : w), rows[0]!);
  const lo = 0.5 - 1.6 * bound, hi = 0.5 + 1.6 * bound;
  const W = 900, rowH = 46, top = 30, H = top + groups.length * rowH + 40, L = 190, R = 20;
  const x = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const placed = rows.map((r, i) => {
    const gi = groups.indexOf(r.group);
    const same = rows.slice(0, i).filter((o) => o.group === r.group && Math.abs(x(Number(o.auc)) - x(Number(r.auc))) < 14).length;
    return { ...r, i, cx: x(Number(r.auc)), cy: top + gi * rowH + rowH / 2 + (same % 2 ? -1 : 1) * Math.ceil(same / 2) * 9 };
  });
  const inside = rows.filter((r) => Math.abs(Number(r.auc) - 0.5) <= bound).length;
  const sel = focus !== null ? placed[focus] : null;

  const toss = () => {
    setFlips((f) => f + 1);
    play("coin");
    window.setTimeout(() => { setLanded(true); fx.sparkle(null, 30); play("win"); }, calm ? 0 : 1400);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 md:grid-cols-[300px_minmax(0,1fr)] items-center">
        <div className="h-60 px-panel">
          <Scene3D scene={<Coin3D flips={flips} className="h-full w-full" />}
            fallback={<div className="h-full grid place-items-center"><Sprite name="coin" scale={12} /></div>} />
        </div>
        <Say who="Детектор утечек">
          Монета угадывает с AUC 0,5. Если «пустой» признак (секунды, символы ID, день недели, круглая сумма, позиция строки) отличает цели ошибок от честных
          двойников лучше монеты — это утечка, и агент учился бы на ней, а не на бухгалтерии. Проверено {rows.length} признаков на {sample?.n ?? "—"} эпизодах.
          Коридор самопроверки: |AUC − 0,5| ≤ {asWritten(String(bound))}.
          <div className="mt-3"><PxButton onClick={toss} disabled={flips > 0 && !landed}>{landed ? "ЕЩЁ РАЗ" : "ПОДБРОСИТЬ МОНЕТУ"}</PxButton></div>
        </Say>
      </div>

      {landed && (
        <div className="px-panel p-3">
          <div className="overflow-x-auto scroll-thin"><svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[820px] h-auto" role="group" aria-label="AUC признаков в коридоре">
            <rect x={x(0.5 - bound)} y={top - 10} width={x(0.5 + bound) - x(0.5 - bound)} height={groups.length * rowH + 20} fill="#4E79E8" opacity="0.18" />
            <line x1={x(0.5 - bound)} x2={x(0.5 - bound)} y1={top - 10} y2={H - 30} stroke="#8FB2FF" strokeDasharray="6 4" />
            <line x1={x(0.5 + bound)} x2={x(0.5 + bound)} y1={top - 10} y2={H - 30} stroke="#8FB2FF" strokeDasharray="6 4" />
            <line x1={x(0.5)} x2={x(0.5)} y1={top - 10} y2={H - 30} stroke="#EFE9D6" strokeDasharray="2 4" />
            {[lo, 0.5 - bound, 0.5, 0.5 + bound, hi].map((v) => (
              <text key={v} x={x(v)} y={H - 10} textAnchor="middle" className="fill-fog font-mono" fontSize="16">{num(v, 2)}</text>
            ))}
            {groups.map((g, gi) => (
              <text key={g} x={8} y={top + gi * rowH + rowH / 2 + 4} className="fill-fog font-mono" fontSize="15">{g}</text>
            ))}
            {placed.map((p) => (
              <motion.g key={p.i} tabIndex={0} role="button" aria-label={`${p.group}, ${p.feature}: AUC ${p.auc}`}
                initial={calm ? false : { y: -H, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
                transition={calm ? { duration: 0 } : { delay: p.i * 0.025, type: "spring", stiffness: 220, damping: 14 }}
                onMouseEnter={() => setFocus(p.i)} onFocus={() => setFocus(p.i)} onClick={() => { setFocus(p.i); play("blip"); }}
                className="cursor-pointer outline-none">
                <rect x={p.cx - 7} y={p.cy - 7} width="14" height="14" fill={p === worst || p.feature === worst.feature && p.group === worst.group ? "#FF7A5C" : "#F4C64E"}
                  stroke={focus === p.i ? "#FFF8E6" : "#000"} strokeWidth={focus === p.i ? 3 : 1.5} />
                <rect x={p.cx - 3} y={p.cy - 3} width="6" height="6" fill="#E8892E" />
              </motion.g>
            ))}
          </svg></div>
          <p className="font-mono text-[14px] min-h-[2.8em] mt-2" aria-live="polite">
            {sel ? <>{sel.group} · {FEATURE_RU[sel.feature] ?? sel.feature} ({sel.feature}) · AUC <b className="text-gold">{asWritten(sel.auc)}</b> · целей {sel.pos}, контролей {sel.ctl}</>
              : "Наведи на монету (или Tab) — признак и его AUC."}
          </p>
          <p className="text-sm">Внутри коридора: <b className="text-lime">{inside} из {rows.length}</b>. Самый «говорящий»: {worst.group} · {FEATURE_RU[worst.feature] ?? worst.feature} — AUC {asWritten(worst.auc)}.</p>
          {commandOf("LEAK_AUDIT") && <div className="mt-2"><Cmd>{commandOf("LEAK_AUDIT")!}</Cmd></div>}
          <div className="mt-3">
            <PxButton onClick={() => finish({
              stars: 3,
              lines: [
                { label: "Признаков проверено", value: String(rows.length) },
                { label: "Внутри коридора", value: `${inside}/${rows.length}`, tone: inside === rows.length ? "good" : "bad" },
                { label: "Худший |AUC − 0,5|", value: num(Math.abs(Number(worst.auc) - 0.5), 3) },
                { label: "Граница", value: `≤ ${asWritten(String(bound))}` },
              ],
              note: "Источник: reports/LEAK_AUDIT.md (Mann–Whitney AUC, цели против подобранных контролей).",
            })}>ДАЛЕЕ</PxButton>
          </div>
        </div>
      )}
    </div>
  );
}
