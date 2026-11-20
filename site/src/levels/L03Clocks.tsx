// Level 3 «Часы»: one bank instant, two calendars. Pick the rate date the policy
// requires; the environment's calculator then derives the error amount.
import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { useGame } from "../game/store";
import { Loading, PxButton, Say } from "../game/ui";
import { atOffset, num, ruDate } from "../lib/format";
import { calculate } from "../lib/sandbox";
import { TYPE_RU, useKit } from "./kit";

function Clock({ who, zone, date, time, tone }: { who: string; zone: string; date: string; time: string; tone: "blue" | "red" }) {
  return (
    <div className="px-panel p-4 text-center">
      <div className="label">{who}</div>
      <div className="text-fog font-mono text-sm">UTC{zone}</div>
      <div className={`mt-2 inline-block bg-black px-4 py-3 font-arcade text-2xl sm:text-4xl ${tone === "blue" ? "text-sky" : "text-ember"} [text-shadow:0_0_8px_currentColor]`}>
        {time}
      </div>
      <div className={`mt-2 font-arcade text-[14px] sm:text-sm ${tone === "blue" ? "text-sky" : "text-ember"}`}>{date}</div>
    </div>
  );
}

/** Round a plain decimal string to an integer: half_up or half_even (as the policy says). */
function roundInt(value: string, mode: string): bigint {
  const neg = value.startsWith("-");
  const [i = "0", f = ""] = value.replace("-", "").split(".");
  let q = BigInt(i);
  const first = f[0] ?? "0", rest = f.slice(1).replace(/0+$/, "");
  if (first > "5" || (first === "5" && (rest !== "" || mode !== "half_even" || q % 2n === 1n))) q += 1n;
  return neg ? -q : q;
}

export default function L03Clocks({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [pick, setPick] = useState<string | null>(null);
  const [tries, setTries] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  if (!kit) return <Loading />;
  const life = kit.ep.life;
  if (!life || !life.rate_correct || !life.rate_used) return <Say>В этом эпизоде нет сценария X1.</Say>;
  const m = kit.ep.manifest;
  const pay = life.payment;
  const bank = atOffset(pay.timestamp, life.period.bank_timezone);
  const local = atOffset(pay.timestamp, life.period.timezone);
  const periodStart = atOffset(life.period.start, life.period.timezone);
  const options = Array.from(new Set([life.rate_used.date, life.rate_correct.date, local.iso])).sort();
  const right = life.rate_correct.date;

  const es = m.currency_exponents[pay.currency] ?? 0, eb = m.currency_exponents[m.base_currency] ?? 2;
  const scale = eb >= es ? `* ${10 ** (eb - es)}` : `/ ${10 ** (es - eb)}`;
  const exprOk = `${pay.amount_minor} * ${life.rate_correct.rate} ${scale}`;
  const exprBooks = `${pay.amount_minor} * ${life.rate_used.rate} ${scale}`;
  const valOk = calculate(exprOk), valBooks = calculate(exprBooks);
  const expected = roundInt(valOk, m.rounding);
  const actual = life.carrier_rows.reduce((s, r) => s + BigInt(r.debit_minor ?? 0), 0n);
  const diff = actual > expected ? actual - expected : expected - actual;
  const agrees = diff === BigInt(life.expected_amount_minor) ||
    (diff > BigInt(life.expected_amount_minor) ? diff - BigInt(life.expected_amount_minor) : BigInt(life.expected_amount_minor) - diff) <= BigInt(life.tolerance_minor);

  const choose = (d: string) => {
    if (pick === right) return;
    setTries((t) => t + 1);
    setPick(d);
    if (d === right) { play("win"); fx.confetti(box.current); }
    else { play("hit"); fx.shake(); fx.burst(box.current, "#D9473A", 30); }
  };

  return (
    <div ref={box} className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Clock who="Банк записал" zone={life.period.bank_timezone} date={bank.date} time={bank.time} tone="blue" />
        <Clock who="У компании в этот миг" zone={life.period.timezone} date={local.date} time={local.time} tone="red" />
      </div>
      <Say who="Дело">
        Платёж {pay.payment_id}: {num(pay.amount_minor)} {pay.currency}. Банк пишет время по UTC, а у компании уже {local.date} — новый отчётный период
        (начался {periodStart.date} в {periodStart.time} по её времени). Правило курса: <b>{String(life.rule.rate_date)}</b> от <b>{String(life.rule.rate_date_basis)}</b>.
        Курс какой даты нужно взять?
      </Say>
      <div className="flex flex-wrap gap-3" role="group" aria-label="Дата курса">
        {options.map((d) => (
          <PxButton key={d} tone={pick === d ? (d === right ? "green" : "red") : "ghost"} onClick={() => choose(d)} disabled={pick === right}>
            курс за {ruDate(d)}
          </PxButton>
        ))}
      </div>
      {pick && pick !== right && <p className="text-ember font-arcade text-[14px]">НЕТ. {pick === life.rate_used.date ? "Так ошиблись сами книги: день перед UTC-датой." : "Правило берёт предыдущий день."} Попробуй ещё.</p>}
      {pick === right && (
        <motion.div initial={calm ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="px-panel p-4 flex flex-col gap-2">
          <p className="font-arcade text-[14px] text-lime">ВЕРНО. А КНИГИ ВЗЯЛИ КУРС ЗА {ruDate(life.rate_used.date)}.</p>
          <p className="text-sm text-fog">Калькулятор среды (тот же, что у агента: только + − × ÷ и десятичные):</p>
          <code className="font-mono text-[14px] text-lime bg-black/50 px-3 py-2 block overflow-x-auto whitespace-pre">
{`правильно: ${exprOk} = ${valOk} → ${m.rounding} → ${expected}
в книгах:  ${exprBooks} = ${valBooks}; проводка ${life.carrier_rows.map((r) => r.row_id).join(", ")}: Dr ${actual}
ошибка:    |${actual} − ${expected}| = ${diff} → ${kit.money(Number(diff))}`}
          </code>
          <p>В эталоне: <b>{TYPE_RU.fx_conversion}</b> {pay.payment_id} = {kit.money(life.expected_amount_minor)}, допуск {life.tolerance_minor}.
            {agrees ? " Совпало." : " Расхождение с эталоном — проверьте данные."}</p>
          {life.partner_issues.map((p) => (
            <p key={p.issue_id} className="text-sky">Сценарий {life.interaction_group}: та же оплата разнесена частично — вторая ошибка <b>{TYPE_RU[p.type] ?? p.type}</b> {p.affected_ids.join(" + ")} = {kit.money(p.expected_amount_minor)}. Одна причина — две ошибки, обе надо найти.</p>
          ))}
          {kit.ep.passport_verifier && <p className="text-sm text-fog">Независимый проверяльщик vouchai_verify по паспорту эпизода: {kit.ep.passport_verifier}.</p>}
          <div className="mt-2">
            <PxButton onClick={() => finish({
              stars: tries <= 1 ? 3 : tries === 2 ? 2 : 1,
              lines: [
                { label: "Попыток", value: String(tries), tone: tries <= 1 ? "good" : "bad" },
                { label: "Правильный курс", value: `${ruDate(right)}: ${life.rate_correct!.rate}` },
                { label: "Курс в книгах", value: `${ruDate(life.rate_used!.date)}: ${life.rate_used!.rate}`, tone: "bad" },
                { label: "Сумма ошибки", value: kit.money(Number(diff)), tone: "good" },
              ],
              note: "Типы ошибок: дубль, разнесение, пересчёт валюты, граница периода. X1 и X2 — их взаимодействия.",
            })}>ДАЛЕЕ</PxButton>
          </div>
        </motion.div>
      )}
    </div>
  );
}
