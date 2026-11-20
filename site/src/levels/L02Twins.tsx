// Level 2 «Двойники»: two invoices, one customer, one amount. A subscription,
// not a duplicate. Shows legitimate look-alikes and the cost of haste.
import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Loading, PxButton, Say, Stamp } from "../game/ui";
import { col, findTable, sampleOf } from "../data";
import { atOffset, signed } from "../lib/format";
import type { FindingIn } from "../lib/matcher";
import { useKit } from "./kit";

export default function L02Twins({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [verdict, setVerdict] = useState<"dup" | "nodup" | null>(null);
  const area = useRef<HTMLDivElement>(null);
  if (!kit) return <Loading />;
  const hall = kit.ep.hall;
  if (!hall) return <Say>В этом эпизоде нет пары-двойника.</Say>;
  const [a, b] = hall.invoices as [typeof hall.invoices[0], typeof hall.invoices[0]];
  const tz = kit.ep.manifest.timezone;
  const issuing = (id: string) => hall.ledger_rows.find((r) => r.invoice_id === id)?.debit_minor ?? a.total_minor;
  const wrong: FindingIn = {
    type: "duplicate_invoice", affected_ids: [a.invoice_id, b.invoice_id], claimed_amount_minor: issuing(a.invoice_id),
    currency: kit.base, evidence_ids: [a.doc_id, b.doc_id], explanation: "same customer, same amount",
  };
  const alone = kit.grade([wrong], kit.auditorSteps);
  const honest = kit.grade(kit.auditorFindings, kit.auditorSteps);
  const spoiled = kit.grade([...kit.auditorFindings, wrong], kit.auditorSteps);
  const rule = kit.ep.policy.findings.legitimate_rules?.duplicate_document;

  const deception = findTable("FAILURE_ANALYSIS", "Legitimate case", /deception/i);
  const lookalike = deception?.rows.find((r) => /similar invoice/i.test(r[0] ?? ""));
  const reconciler = deception ? col(deception, "simple_reconciler") : null;

  const choose = (v: "dup" | "nodup") => {
    if (verdict) return;
    setVerdict(v);
    if (v === "dup") { play("boom"); fx.burst(area.current); fx.shake(); fx.flash("#D9473A"); }
    else { play("win"); fx.confetti(area.current); }
  };

  const doc = (inv: typeof a, k: number) => {
    const li = inv.line_items[0]!;
    const when = atOffset(inv.issued_at, tz);
    return (
      <motion.div key={inv.invoice_id} className="px-paper p-4 relative"
        initial={calm ? false : { y: 30, opacity: 0, rotate: k ? 2 : -2 }} animate={{ y: 0, opacity: 1, rotate: k ? 1 : -1 }}>
        <div className="flex items-center justify-between border-b-2 border-night pb-2 mb-2">
          <span className="font-arcade text-[14px]">СЧЁТ</span>
          <span className="font-mono text-sm">{inv.invoice_id}</span>
        </div>
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 font-mono text-[14px]">
          <dt className="text-dusk">клиент</dt><dd>{inv.entity_id}</dd>
          <dt className="text-dusk">выставлен</dt><dd>{when.date} {when.time}</dd>
          <dt className="text-dusk">сумма</dt><dd className="font-bold">{kit.money(inv.total_minor, inv.currency)}</dd>
          <dt className="text-dusk">услуга</dt><dd>{li.description}{inv.line_items.length > 1 ? ` + ещё ${inv.line_items.length - 1}` : ""}</dd>
          <dt className="text-dusk">период услуги</dt>
          <dd>{verdict ? <span className="bg-lime px-1">{li.service_period_start} … {li.service_period_end}</span>
            : <span className="bg-night text-night select-none px-1">██████████████</span>}</dd>
        </dl>
        {verdict && <div className="absolute right-2 top-10"><Stamp text={verdict === "dup" ? "ДУБЛЬ" : "НЕ ДУБЛЬ"} tone={verdict === "dup" ? "red" : "blue"} rotate={k ? 8 : -8} /></div>}
      </motion.div>
    );
  };

  return (
    <div ref={area} className="flex flex-col gap-5">
      <div className="flex items-end gap-4">
        <Sprite name="hero" scale={4} />
        <Say who="Зал">Один клиент, одна сумма, одно описание, разные даты. Кто считает, что это дубль, — жмите «ДУБЛЬ».</Say>
      </div>
      <div className="grid gap-6 md:grid-cols-2">{doc(a, 0)}{doc(b, 1)}</div>
      {!verdict && (
        <div className="flex flex-wrap gap-4">
          <PxButton tone="red" onClick={() => choose("dup")} sfx="stamp">ДУБЛЬ</PxButton>
          <PxButton tone="blue" onClick={() => choose("nodup")} sfx="stamp">НЕ ДУБЛЬ</PxButton>
        </div>
      )}
      {verdict && (
        <motion.div initial={calm ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="px-panel p-4 flex flex-col gap-2">
          <p className={`font-arcade text-[14px] ${verdict === "dup" ? "text-ember" : "text-lime"}`}>
            {verdict === "dup" ? "ПОСПЕШИЛИ: ЭТО ПОДПИСКА" : "ВЕРНО: ЭТО ПОДПИСКА"}
          </p>
          <p>Услуга оказана за разные периоды — это два законных счёта. Правило среды (policy.findings):</p>
          {rule && <p className="font-mono text-[14px] text-sky">«{rule}»</p>}
          <ul className="font-mono text-[14px] mt-1">
            <li>вывод «дубль» в одиночку: <b className="text-ember">{signed(alone.reward)}</b> (TP {alone.tp}, FP {alone.fp})</li>
            <li>честный ответ аудитора: <b className="text-lime">{signed(honest.reward)}</b> → с лишним «дублем»: <b className="text-ember">{signed(spoiled.reward)}</b></li>
          </ul>
          {lookalike && reconciler && (
            <p className="text-fog text-sm">Карта обмана (reports/FAILURE_ANALYSIS.md): похожие счета обманули простую сверку {reconciler(lookalike)} раз на {sampleOf("FAILURE_ANALYSIS")?.n ?? "—"} эпизодах.</p>
          )}
          <div className="mt-2">
            <PxButton onClick={() => finish({
              stars: verdict === "nodup" ? 3 : 1,
              lines: [
                { label: "Ваш вердикт", value: verdict === "dup" ? "дубль" : "не дубль", tone: verdict === "dup" ? "bad" : "good" },
                { label: "«Дубль» в одиночку", value: signed(alone.reward), tone: "bad" },
                { label: "Честный ответ", value: signed(honest.reward), tone: "good" },
                { label: "Честный + лишний «дубль»", value: signed(spoiled.reward), tone: "bad" },
              ],
              note: "Похожий — не значит виноватый. Двойники-ловушки стоят в каждом эпизоде.",
            })}>ДАЛЕЕ</PxButton>
          </div>
        </motion.div>
      )}
    </div>
  );
}
