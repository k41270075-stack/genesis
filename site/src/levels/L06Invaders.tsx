// Level 6 «Нашествие»: the one-line attacks of reports/FAILURE_ANALYSIS.md as
// invaders. Each HP bar is its micro F1 against the threshold of the self-check;
// the last wave is the mass flagging of the jury's test 12, graded live.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { col, commandOf, findTable, sampleOf, sectionText } from "../data";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Bar, Cmd, PxButton, Say } from "../game/ui";
import { asWritten, frac, num, signed } from "../lib/format";
import { grade, TYPES, type FindingIn } from "../lib/matcher";

const RU: Record<string, string> = {
  attack_2150_with_refs: "строка 2150 у платежа со ссылками на счета",
  attack_posted_before_document: "проводка раньше своего документа",
  attack_posted_2h_before_document: "проводка за 2+ часа до документа",
  attack_long_delay: "проводка позже документа больше чем на сутки",
  attack_same_second: "два счёта выставлены в одну секунду",
  attack_margin_documents: "документ за пределами периода",
  attack_utc_date_differs: "UTC-дата платежа отличается от местной",
  attack_due_next_period: "срок оплаты в следующем периоде",
  attack_last_rows: "последние строки книги",
  attack_partial_payment: "платёж меньше своего счёта",
};

/** Test 12 of the published jury checks: five records, one error, every record flagged with every type. */
function massFlag() {
  const records = ["R1", "R2", "R3", "R4", "R5"];
  const issue = { issue_id: "A", type: TYPES[0], affected_ids: ["R1"], expected_amount_minor: 10000, currency: "KZT", tolerance_minor: 0, evidence_ids: ["D1", "D2"] };
  const findings: FindingIn[] = records.flatMap((r) => TYPES.map((t) => ({
    type: t, affected_ids: [r], claimed_amount_minor: 10000, currency: "KZT", evidence_ids: ["D1", "D2"], explanation: "flag",
  })));
  const g = grade(JSON.stringify({ episode_id: "fixture", findings }), {
    issues: [issue], publicIds: new Set([...records, "D1", "D2"]), inspectionSteps: 10, episodeId: "fixture",
  });
  return { g, records: records.length, types: TYPES.length, findings: findings.length };
}

export default function L06Invaders({ finish }: LevelProps) {
  const { calm } = useGame();
  const table = findTable("FAILURE_ANALYSIS", "micro F1", /attack/i);
  const thrText = sectionText("FAILURE_ANALYSIS", /attack/i).join(" ");
  const thr = Number(/micro F1\s*<=\s*(\d+(?:\.\d+)?)/.exec(thrText)?.[1] ?? NaN);
  const sample = sampleOf("FAILURE_ANALYSIS");
  const enemies = useMemo(() => {
    if (!table) return [];
    const name = col(table, "Attack"), tp = col(table, "TP"), fp = col(table, "FP"), f1 = col(table, "micro F1"), ret = col(table, "mean return");
    return table.rows.map((r) => ({ name: name(r), tp: tp(r), fp: fp(r), f1: f1(r), ret: ret(r) }));
  }, [table]);
  const mass = useMemo(massFlag, []);
  const [dead, setDead] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const [bossDown, setBossDown] = useState(false);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const bossRef = useRef<HTMLButtonElement>(null);

  const kill = (name: string) => {
    if (dead.has(name)) { setOpen(name); return; }
    play("boom"); fx.burst(refs.current[name]); fx.shake();
    setDead((d) => new Set(d).add(name));
    setOpen(name);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!enemies.length) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const n = (sel + (e.key === "ArrowRight" ? 1 : -1) + enemies.length) % enemies.length;
        setSel(n);
        refs.current[enemies[n]!.name]?.focus();
        play("step");
      }
      if (e.key === " " && (e.target as HTMLElement)?.tagName !== "BUTTON") { e.preventDefault(); kill(enemies[sel]!.name); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!table) return <Say>В reports/FAILURE_ANALYSIS.md нет таблицы атак.</Say>;
  const allDead = dead.size === enemies.length;
  const maxF1 = Math.max(...enemies.map((e) => Number(e.f1)));
  const cur = enemies.find((e) => e.name === open);

  return (
    <div className="flex flex-col gap-5">
      <Say who="Разведка">
        {enemies.length} атак-однострочников: каждая ставит на один поверхностный признак. Порог самопроверки: micro F1 ≤ {asWritten(String(thr))}.
        Полоска — это F1 атаки, белая черта — порог. Кликай по врагам (или ← → и пробел).
      </Say>

      <div className="px-panel p-4 relative overflow-hidden">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {enemies.map((e, i) => (
            <AnimatePresence key={e.name}>
              <motion.button type="button" ref={(el) => { refs.current[e.name] = el; }}
                onClick={() => { setSel(i); kill(e.name); }}
                aria-label={`Атака ${e.name}: ${RU[e.name] ?? ""}, micro F1 ${e.f1}`}
                className={`flex flex-col items-center gap-1 p-2 ${i === sel ? "outline outline-2 outline-gold" : ""} ${dead.has(e.name) ? "opacity-40" : ""}`}
                animate={dead.has(e.name) ? { scale: 0.8, rotate: 12 } : calm ? {} : { y: [0, -6, 0] }}
                transition={dead.has(e.name) ? { duration: 0.3 } : { repeat: Infinity, duration: 1.4, delay: i * 0.1 }}>
                {dead.has(e.name) ? <span className="font-arcade text-[14px] text-lime h-8 grid place-items-center">РАЗОБЛАЧЕНА</span> : <Sprite name="enemy" scale={4} />}
                <Bar value={Number(e.f1)} max={Math.max(1e-9, Math.max(maxF1, thr) * 1.25)} cells={12} color="bg-ember" mark={thr} label={`micro F1 ${e.f1}`} />
                <span className="font-mono text-[14px] text-fog break-all">F1 {asWritten(e.f1)}</span>
              </motion.button>
            </AnimatePresence>
          ))}
        </div>
        <div className="mt-4 flex justify-center"><motion.div animate={{ x: `${(sel - (enemies.length - 1) / 2) * 12}%` }}><Sprite name="hero" scale={4} /></motion.div></div>
      </div>

      {cur && (
        <div className="px-panel p-4 flex flex-col gap-2">
          <div className="font-arcade text-[14px] text-ember">{cur.name}</div>
          <div>Признак: <b>{RU[cur.name] ?? cur.name}</b></div>
          <div className="font-mono text-[14px]">TP {cur.tp} · FP {cur.fp} · micro F1 {asWritten(cur.f1)} · средняя награда {asWritten(cur.ret)}</div>
          <div className="label mt-1">вскрыть пломбу — повторить атаку</div>
          <Cmd>{`python -m vouchai run --policy ${cur.name} --config jury_like --seeds ${sample?.from ?? "0"}:${sample?.to ? Number(sample.to) + 1 : "20"}`}</Cmd>
          <div className="text-sm text-fog">Весь отчёт: <span className="font-mono">{commandOf("FAILURE_ANALYSIS") ?? ""}</span></div>
        </div>
      )}

      {allDead && (
        <motion.div initial={calm ? false : { y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="px-panel p-4 flex flex-col gap-3">
          <div className="font-arcade text-[14px] text-gold">ФИНАЛЬНАЯ ВОЛНА: МАССОВАЯ ПОМЕТКА</div>
          <p>Тест 12 из опубликованных проверок жюри: {mass.records} записей, одна ошибка; помечаем каждую запись всеми {mass.types} типами — {mass.findings} выводов. Считает matcher прямо сейчас:</p>
          <button ref={bossRef} type="button" disabled={bossDown} onClick={() => { setBossDown(true); play("boom"); fx.burst(bossRef.current, undefined, 120); fx.flash("#D9473A"); fx.shake(); }}
            className="self-start flex items-center gap-3 px-btn px-btn--red normal-case">
            <span className="grid grid-cols-4 gap-1">{Array.from({ length: mass.findings }, (_, i) => <Sprite key={i} name="enemy" scale={1} animate={false} />)}</span>
            <span>{bossDown ? "РАЗБИТА" : "УДАРИТЬ"}</span>
          </button>
          {bossDown && (
            <div className="font-mono text-[15px]">
              TP {mass.g.tp} · FP {mass.g.fp} · FN {mass.g.fn} · F1 {mass.g.f1_exact} · шагов {mass.g.inspection_steps} →
              награда <b className="text-ember">{frac(mass.g.reward_exact)} ≈ {num(mass.g.reward, 4)}</b>
            </div>
          )}
          {bossDown && <PxButton onClick={() => finish({
            stars: 3,
            lines: [
              { label: "Разоблачено атак", value: `${dead.size}/${enemies.length}`, tone: "good" },
              { label: "Лучший F1 атаки", value: asWritten(String(maxF1)), tone: maxF1 <= thr ? "good" : "bad" },
              { label: "Порог самопроверки", value: `≤ ${asWritten(String(thr))}` },
              { label: "Массовая пометка", value: signed(mass.g.reward, 4), tone: "bad" },
            ],
            note: `Источник атак: reports/FAILURE_ANALYSIS.md (${sample?.n ?? "—"} эпизодов jury_like). Массовая пометка посчитана в браузере.`,
          })}>ДАЛЕЕ</PxButton>}
        </motion.div>
      )}
    </div>
  );
}
