// Level 9 «Копирка»: the mirror world. Every ID renamed one-to-one, every table
// shuffled — by this browser, right now. The oracle and the auditor score the same.
import { motion } from "framer-motion";
import { useMemo, useRef, useState } from "react";
import { readmeCommand } from "../data";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Cmd, Loading, PxButton, Say } from "../game/ui";
import { publicIds, tablesOf } from "../lib/episode";
import { signed } from "../lib/format";
import { grade, oracleFindings } from "../lib/matcher";
import { renameEpisode } from "../lib/rename";
import type { Row } from "../lib/sandbox";
import { useKit } from "./kit";

const COLS = ["row_id", "account", "debit_minor", "credit_minor", "invoice_id", "payment_id"];

export default function L09Mirror({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [seed, setSeed] = useState(1);
  const [inside, setInside] = useState(false);
  const portal = useRef<HTMLDivElement>(null);

  const world = useMemo(() => {
    if (!kit) return null;
    const { ep } = kit;
    const tables = tablesOf(ep);
    const copy = renameEpisode(tables, ep.truth.issues, seed);
    const idsCopy = publicIds(copy.tables);
    const tr = (x: string) => copy.map.get(x) ?? x;
    const auditorCopy = kit.auditorFindings.map((f) => ({ ...f, affected_ids: f.affected_ids.map(tr), evidence_ids: f.evidence_ids.map(tr) }));
    const opt = (issues: typeof ep.truth.issues, ids: Set<string>, steps: number) => ({ issues, publicIds: ids, inspectionSteps: steps, episodeId: ep.episode_id });
    const pay = (f: unknown[]) => JSON.stringify({ episode_id: ep.episode_id, findings: f });
    const oracleA = grade(pay(oracleFindings(ep.truth.issues)), opt(ep.truth.issues, kit.ids, 0));
    const oracleB = grade(pay(oracleFindings(copy.issues)), opt(copy.issues, idsCopy, 0));
    const audA = grade(pay(kit.auditorFindings), opt(ep.truth.issues, kit.ids, kit.auditorSteps));
    const audB = grade(pay(auditorCopy), opt(copy.issues, idsCopy, kit.auditorSteps));
    const crossed = grade(pay(kit.auditorFindings), opt(copy.issues, idsCopy, kit.auditorSteps));
    const focus = ep.life?.payment.payment_id ?? ep.truth.issues[0]?.affected_ids[0] ?? "";
    const orig = tables.ledger.filter((r) => r.payment_id === focus || r.invoice_id === focus).slice(0, 6);
    const mirrored = copy.tables.ledger.filter((r) => r.payment_id === tr(focus) || r.invoice_id === tr(focus)).slice(0, 6);
    const firstRowA = tables.ledger[0]?.row_id, firstRowB = copy.tables.ledger[0]?.row_id;
    return { copy, oracleA, oracleB, audA, audB, crossed, orig, mirrored, renamed: copy.map.size, firstRowA, firstRowB };
  }, [kit, seed]);

  if (!kit || !world) return <Loading />;
  const transform = readmeCommand("transform");

  const table = (rows: Row[], tone: "paper" | "blue") => (
    <table className="data-table">
      <thead><tr>{COLS.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{COLS.map((c) => <td key={c} className={tone === "blue" && /_id$/.test(c) ? "text-sky" : ""}>{r[c] === null ? "null" : String(r[c])}</td>)}</tr>)}</tbody>
    </table>
  );

  const enter = () => {
    setInside(true); play("coin"); fx.flash("#4E79E8"); fx.sparkle(portal.current, 40);
  };

  return (
    <div className="flex flex-col gap-5">
      <Say who="Жюри">Мы переименуем все ID — в книгах, документах, курсах и ссылках — и перемешаем строки. Если среда честная, награда не изменится.</Say>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="px-panel p-3 overflow-x-auto scroll-thin">
          <div className="label mb-2">оригинал · проводки одной оплаты</div>
          {table(world.orig, "paper")}
        </div>
        <motion.div ref={portal} className="px-panel p-3 overflow-x-auto scroll-thin relative"
          animate={inside ? { rotateY: 0, opacity: 1 } : { rotateY: calm ? 0 : 180, opacity: calm ? 1 : 0.5 }} transition={{ duration: 0.7 }}
          style={{ transformStyle: "preserve-3d" }}>
          <div className="label mb-2 text-sky">копия · те же проводки под чужими именами</div>
          {inside ? table(world.mirrored, "blue") : <div className="h-40 grid place-items-center"><Sprite name="hero" scale={5} /></div>}
        </motion.div>
      </div>
      <div className="flex flex-wrap gap-3">
        {!inside && <PxButton tone="blue" onClick={enter}>ШАГНУТЬ В КОПИЮ</PxButton>}
        {inside && <PxButton tone="ghost" onClick={() => { setSeed((s) => s + 1); play("blip"); fx.sparkle(portal.current, 20); }}>ПЕРЕИМЕНОВАТЬ ЕЩЁ РАЗ</PxButton>}
      </div>
      {inside && (
        <div className="px-panel p-4 font-mono text-[15px] flex flex-col gap-1">
          <div>переименовано ID: <b className="text-gold">{world.renamed}</b> · первая строка книги: {String(world.firstRowA)} → {String(world.firstRowB)}</div>
          <div>oracle: оригинал <b className="text-lime">{signed(world.oracleA.reward)}</b> = копия <b className="text-lime">{signed(world.oracleB.reward)}</b></div>
          <div>ответ аудитора (переведён тем же отображением): <b className="text-lime">{signed(world.audA.reward, 3)}</b> = <b className="text-lime">{signed(world.audB.reward, 3)}</b></div>
          <div className="text-fog">старые ID в новом мире: TP {world.crossed.tp}, FP {world.crossed.fp} → {signed(world.crossed.reward)} — ID нельзя угадать, только найти.</div>
          {transform && <div className="mt-2"><div className="label mb-1">то же в Python (перестановка и враждебная смена ID)</div><Cmd>{transform}</Cmd></div>}
          <div className="mt-3">
            <PxButton onClick={() => finish({
              stars: 3,
              lines: [
                { label: "Переименовано ID", value: String(world.renamed) },
                { label: "Oracle: оригинал / копия", value: `${signed(world.oracleA.reward)} / ${signed(world.oracleB.reward)}`, tone: "good" },
                { label: "Аудитор: оригинал / копия", value: `${signed(world.audA.reward, 3)} / ${signed(world.audB.reward, 3)}`, tone: "good" },
                { label: "Старые ID в копии", value: signed(world.crossed.reward), tone: "bad" },
              ],
              note: "Парные проверки жюри (перестановка, смена ID, оба сразу) — награда не зависит от имён.",
            })}>ДАЛЕЕ</PxButton>
          </div>
        </div>
      )}
    </div>
  );
}
