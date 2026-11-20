// Level 1 «Касса»: the real submit of our scripted auditor printed as a receipt,
// each finding becomes a receipt in the inventory, then the reward formula.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Cmd, Loading, PxButton, Say, Stamp } from "../game/ui";
import { claims } from "../data";
import { frac, num, ruDate, signed } from "../lib/format";
import { TYPE_RU, useKit } from "./kit";

export default function L01Kassa({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [printed, setPrinted] = useState(0);
  const [stage, setStage] = useState<"print" | "formula" | "stamp">("print");
  const inv = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => {
    if (!kit) return [];
    const { ep } = kit;
    const m = ep.manifest;
    const out: { text: string; loot?: boolean }[] = [
      { text: "      VOUCHAI · КАССА РЕВИЗОРА" },
      { text: "-".repeat(34) },
      { text: `ЭПИЗОД   ${ep.episode_id}` },
      { text: `КОМПАНИЯ ${m.company} (вымышл.)` },
      { text: `ПЕРИОД   [${ruDate(m.period_start)}, ${ruDate(m.period_end)})` },
      { text: `ПОЛИТИКА ${ep.auditor?.policy ?? "—"}` },
      { text: "-".repeat(34) },
    ];
    kit.auditorFindings.forEach((f, i) => {
      out.push({ text: `ВЫВОД ${i + 1}: ${f.type}` });
      out.push({ text: `  ЗАПИСИ: ${f.affected_ids.join(", ")}` });
      out.push({ text: `  СУММА: ${kit.money(f.claimed_amount_minor, f.currency)}` });
      out.push({ text: `  ДОКАЗАТЕЛЬСТВА: ${f.evidence_ids.length}`, loot: true });
    });
    out.push({ text: "-".repeat(34) });
    out.push({ text: `ШАГОВ ПРОВЕРКИ: ${kit.auditorSteps}` });
    return out;
  }, [kit]);

  useEffect(() => {
    if (stage !== "print" || !lines.length) return;
    if (printed >= lines.length) { const id = window.setTimeout(() => setStage("formula"), calm ? 0 : 500); return () => window.clearTimeout(id); }
    const id = window.setTimeout(() => {
      setPrinted((p) => p + 1);
      if (lines[printed]?.loot) { play("coin"); fx.sparkle(inv.current, 10); } else play("type");
    }, calm ? 0 : 110);
    return () => window.clearTimeout(id);
  }, [printed, lines, stage, calm]);

  if (!kit) return <Loading />;
  const g = kit.grade(kit.auditorFindings, kit.auditorSteps);
  const journal = kit.ep.auditor?.reward;
  const loot = lines.slice(0, printed).filter((l) => l.loot).length;
  const solvable = claims.find((c) => c.id === "solvable");

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
      <div className="relative">
        <div className="bg-white text-night font-mono text-[14px] leading-[1.45] px-4 pt-4 pb-6 shadow-px min-h-[420px]" aria-live="off">
          {lines.slice(0, printed).map((l, i) => (
            <motion.div key={i} initial={calm ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="whitespace-pre-wrap break-all">{l.text}</motion.div>
          ))}
          {stage !== "print" && (
            <motion.div initial={calm ? false : { scale: 1.4 }} animate={{ scale: 1 }} className="mt-1 font-arcade text-[14px]">
              ИТОГ: НАГРАДА {signed(g.reward)}
            </motion.div>
          )}
          {stage === "stamp" && <div className="absolute right-3 bottom-10"><Stamp text="КВИТАНЦИЯ ПРИЛОЖЕНА" rotate={-10} /></div>}
        </div>
        <div className="h-3 bg-[length:16px_12px] bg-repeat-x" aria-hidden="true"
          style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='12' shape-rendering='crispEdges'%3E%3Cpath d='M0 0h16v4h-4v4h-4v4H8V8H4V4H0z' fill='%23FFF8E6'/%3E%3C/svg%3E\")" }} />
      </div>

      <div className="flex flex-col gap-4">
        <Say who="Наставник">
          Агент-аудитор проверяет книги вымышленной компании и сдаёт выводы. Слева — настоящая лента: что наш скриптовый аудитор отправил на открытом эпизоде. Каждый вывод — это тип ошибки, записи, сумма и <b>квитанции</b>: ID записей, которые его доказывают.
        </Say>

        <div ref={inv} className="px-panel p-3">
          <div className="label mb-2">Инвентарь квитанций</div>
          <div className="flex flex-wrap gap-2 min-h-[48px]">
            <AnimatePresence>
              {kit.auditorFindings.slice(0, loot).map((f, i) => (
                <motion.div key={i} initial={calm ? false : { y: -40, opacity: 0, rotate: -20 }} animate={{ y: 0, opacity: 1, rotate: 0 }}
                  className="flex items-center gap-2 bg-night px-2 py-1" title={f.evidence_ids.join(", ")}>
                  <Sprite name="receipt" scale={3} animate={false} />
                  <span className="text-sm">{TYPE_RU[f.type] ?? f.type} · {f.evidence_ids.length}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>

        {stage !== "print" && (
          <motion.div initial={calm ? false : { opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="px-panel p-4">
            <div className="label mb-2">Формула награды (общая для всех)</div>
            <p className="font-arcade text-[14px] sm:text-[14px] leading-loose text-paper">
              награда = 2·F1 − 1 − 0,002·шаги
            </p>
            <p className="font-mono text-lime text-[15px] mt-2">
              2·{num(g.f1, 3)} − 1 − 0,002·{g.inspection_steps} = {frac(g.reward_exact)} = {signed(g.reward, 3)}
            </p>
            <p className="text-sm text-fog mt-2">
              TP {g.tp} · FP {g.fp} · FN {g.fn}. В журнале траекторий у этого прогона награда {journal !== undefined ? signed(journal, 3) : "—"} — браузер пересчитал ту же.
              Слова в объяснении на награду не влияют: только тип, записи, сумма, валюта и квитанции.
            </p>
            {solvable && <div className="mt-3"><div className="label mb-1">Проверить самому</div><Cmd>{solvable.command}</Cmd></div>}
            <div className="mt-4 flex flex-wrap gap-3">
              {stage === "formula" && <PxButton tone="red" sfx="stamp" onClick={() => { setStage("stamp"); fx.confetti(null, 100); }}>ПОСТАВИТЬ ШТАМП</PxButton>}
              {stage === "stamp" && (
                <PxButton onClick={() => finish({
                  stars: 3,
                  lines: [
                    { label: "Выводов с квитанциями", value: String(kit.auditorFindings.length), tone: "good" },
                    { label: "TP / FP / FN", value: `${g.tp} / ${g.fp} / ${g.fn}` },
                    { label: "Шагов проверки", value: String(g.inspection_steps) },
                    { label: "Награда аудитора", value: signed(g.reward, 3), tone: "good" },
                  ],
                  note: "Источник: trajectories.jsonl (vouchai_auditor, dev). Пересчитано JS-копией matcher.",
                })}>ДАЛЕЕ</PxButton>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
