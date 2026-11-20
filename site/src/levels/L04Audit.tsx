// Level 4 «Ревизия»: a real mini-audit of the open dev episode with the same five
// tools and the same 100-action budget as an agent; graded by the JS matcher.
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useRef, useState, type ReactNode } from "react";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Bar, HONEST, Loading, PxButton, Say, Stamp } from "../game/ui";
import { tablesOf } from "../lib/episode";
import { frac, num, signed } from "../lib/format";
import { codePoints, LIMITS, TYPES, type FindingIn, type GradeResult } from "../lib/matcher";
import { MAX_ACTIONS, PAGE_LIMIT, Sandbox, TABLES, type Action, type Row, type StepResult } from "../lib/sandbox";
import { REASON_RU, STRUCT_RU, TYPE_RU, useKit, type Kit } from "./kit";

type Tool = "list_records" | "get_record" | "get_document" | "calculator" | "submit";
const TOOLS: { id: Tool; ru: string; hint: string }[] = [
  { id: "list_records", ru: "листать", hint: "страница таблицы, до 50 строк, курсор" },
  { id: "get_record", ru: "запись", hint: "одна строка по ID" },
  { id: "get_document", ru: "документ", hint: "счёт или платёж целиком" },
  { id: "calculator", ru: "счёты", hint: "только + − × ÷ ( ) и десятичные" },
  { id: "submit", ru: "сдать", hint: "отправить бланк — конец эпизода" },
];
const SHOWN: Record<string, string[]> = {
  ledger: ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency", "entity_id", "invoice_id", "payment_id"],
  invoices: ["doc_id", "invoice_id", "entity_id", "issued_at", "currency", "total_minor", "line_items", "credit_for", "replaces_invoice_id"],
  payments: ["doc_id", "payment_id", "timestamp", "currency", "amount_minor", "allocations", "fee_minor", "invoice_refs"],
  fx: ["id", "rate"],
};

interface Draft { type: string; affected: string; amount: string; currency: string; evidence: string; explanation: string }
const emptyDraft = (cur: string): Draft => ({ type: "", affected: "", amount: "", currency: cur, evidence: "", explanation: "" });
const split = (s: string) => s.split(/[\s,;]+/).filter(Boolean);
function toFinding(d: Draft): Record<string, unknown> {
  const amt = /^-?\d+$/.test(d.amount.trim()) && Number.isSafeInteger(Number(d.amount.trim())) ? Number(d.amount.trim()) : d.amount;
  return { type: d.type, affected_ids: split(d.affected), claimed_amount_minor: amt, currency: d.currency,
    evidence_ids: split(d.evidence), explanation: d.explanation };
}

function Odometer({ value }: { value: number }) {
  const digits = String(value).padStart(3, "0").split("");
  return (
    <div className="flex items-center gap-3" role="status" aria-label={`Осталось действий: ${value}`}>
      <div className="flex gap-[3px] bg-black p-[3px]">
        {digits.map((d, i) => (
          <div key={i} className={`w-8 h-11 overflow-hidden bg-paper ${value <= 10 ? "text-stamp" : "text-night"}`}>
            <motion.div animate={{ y: -Number(d) * 44 }} transition={{ type: "spring", stiffness: 300, damping: 24 }}>
              {Array.from({ length: 10 }, (_, k) => <div key={k} className="h-11 grid place-items-center font-arcade text-lg">{k}</div>)}
            </motion.div>
          </div>
        ))}
      </div>
      <div className="label leading-tight">осталось<br />действий</div>
    </div>
  );
}

export default function L04Audit({ finish }: LevelProps) {
  const kit = useKit();
  if (!kit) return <Loading />;
  return <Audit kit={kit} finish={finish} />;
}

function Audit({ kit, finish }: { kit: Kit } & LevelProps) {
  const { calm } = useGame();
  const { ep, ids, base } = kit;
  const sandbox = useMemo(() => new Sandbox(ep.episode_id, tablesOf(ep)), [ep]);
  const [, bump] = useState(0);
  const [tool, setTool] = useState<Tool>("list_records");
  const [table, setTable] = useState<string>("invoices");
  const [cursor, setCursor] = useState<string>("");
  const [limit, setLimit] = useState<string>(String(PAGE_LIMIT));
  const [recId, setRecId] = useState("");
  const [docId, setDocId] = useState("");
  const [expr, setExpr] = useState("");
  const [out, setOut] = useState<{ action: Action; res: StepResult } | null>(null);
  const [journal, setJournal] = useState<{ n: number; text: string; err: boolean }[]>([]);
  const [inventory, setInventory] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([emptyDraft(base)]);
  const [active, setActive] = useState<{ i: number; field: "affected" | "evidence" }>({ i: 0, field: "evidence" });
  const [jsonMode, setJsonMode] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [result, setResult] = useState<{ g: GradeResult; findings: unknown[] } | null>(null);
  const [helped, setHelped] = useState<"none" | "hint" | "autopilot">("none");
  const [hint, setHint] = useState<string | null>(null);
  const invRef = useRef<HTMLDivElement>(null);
  const resRef = useRef<HTMLDivElement>(null);
  const nextCursor = useRef<Record<string, string | null>>({});

  const payloadText = () => JSON.stringify({ episode_id: ep.episode_id, findings: drafts.map(toFinding) }, null, 1);

  const run = (action: Action) => {
    if (sandbox.done) return;
    const res = sandbox.step(action);
    play(res.error ? "hit" : "blip");
    if (res.error) fx.shake();
    setOut({ action, res });
    const short = action.action === "list_records" ? `list_records ${action.table}${action.cursor ? " +курсор" : ""}`
      : action.action === "get_record" ? `get_record ${action.table} ${action.id}`
      : action.action === "get_document" ? `get_document ${action.doc_id}`
      : action.action === "calculator" ? `calculator ${action.expression}` : "submit";
    setJournal((j) => [...j, { n: sandbox.actions, text: res.error ? `${short} → ${res.error.code}` : short, err: Boolean(res.error) }]);
    if (action.action === "list_records" && res.result) {
      const nc = (res.result.next_cursor as string | null) ?? null;
      nextCursor.current[String(res.result.table)] = nc;
      setCursor(nc ?? "");
    }
    if (res.truncated) submit(true);
    bump((v) => v + 1);
  };

  const execute = () => {
    if (tool === "list_records") {
      const lim = /^\d+$/.test(limit) ? Number(limit) : NaN;
      run({ action: "list_records", table, cursor: cursor || null, limit: Number.isNaN(lim) ? (limit as unknown as number) : lim });
    } else if (tool === "get_record") run({ action: "get_record", table, id: recId });
    else if (tool === "get_document") run({ action: "get_document", doc_id: docId });
    else if (tool === "calculator") run({ action: "calculator", expression: expr });
    else submit(false);
  };

  const collect = (id: string, el?: Element | null) => {
    if (!inventory.includes(id)) { setInventory((v) => [...v, id]); play("coin"); fx.sparkle(el ?? invRef.current, 8); }
    setDrafts((ds) => ds.map((d, i) => {
      if (i !== active.i) return d;
      const key = active.field;
      const cur = split(d[key]);
      return cur.includes(id) ? d : { ...d, [key]: [...cur, id].join(", ") };
    }));
  };

  const submit = (truncated: boolean) => {
    const text = truncated ? JSON.stringify({ episode_id: ep.episode_id, findings: [] }) : jsonMode ? jsonText : payloadText();
    if (!sandbox.done) sandbox.step({ action: "submit", findings: text });
    const g = kit.grade(text, sandbox.inspection);
    let findings: unknown[] = [];
    try { const p = JSON.parse(text) as { findings?: unknown[] }; findings = Array.isArray(p.findings) ? p.findings : []; } catch { /* invalid JSON: reward -1 */ }
    setResult({ g, findings });
    bump((v) => v + 1);
    window.setTimeout(() => {
      resRef.current?.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
      if (g.tp) fx.confetti(resRef.current, 40 + g.tp * 25);
      if (g.fp || !g.valid) { fx.burst(resRef.current); fx.shake(); play("boom"); }
      else play("win");
    }, 120);
  };

  const idCell = (v: unknown): ReactNode => {
    if (typeof v === "string" && ids.has(v)) {
      return <button type="button" className="idref" onClick={(e) => collect(v, e.currentTarget)} title="Добавить в бланк и в инвентарь">{v}</button>;
    }
    if (v === null || v === undefined) return <span className="text-dusk">null</span>;
    if (Array.isArray(v)) {
      if (!v.length) return <span className="text-dusk">[]</span>;
      return <span>{v.map((x, i) => <span key={i}>{i ? ", " : ""}{typeof x === "object" && x
        ? (("invoice_id" in (x as Row)) ? <>{idCell((x as Row).invoice_id)}:{String((x as Row).amount_minor)}</> : ("description" in (x as Row) ? String((x as Row).description) : JSON.stringify(x)))
        : idCell(x)}</span>)}</span>;
    }
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  };

  const renderOut = () => {
    if (!out) return <p className="text-fog">Нажми клавишу инструмента и «ВЫПОЛНИТЬ». Подсказка: начни с list_records → invoices. Синие ID кликабельны — они попадают в инвентарь и в активное поле бланка.</p>;
    const { action, res } = out;
    if (res.error) return <p className="text-ember">{`{"error": {"code": "${res.error.code}", "message": "${res.error.message}"}}`}</p>;
    const r = res.result ?? {};
    if (action.action === "list_records") {
      const rows = (r.rows as Row[]) ?? [];
      const cols = SHOWN[String(r.table)] ?? Object.keys(rows[0] ?? {});
      return (
        <>
          <div className="overflow-auto max-h-[380px] scroll-thin">
            <table>
              <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>{rows.map((row, i) => <tr key={i}>{cols.map((c) => <td key={c} className={typeof row[c] === "number" ? "text-right" : ""}>{idCell(row[c])}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-fog">
            <span>строк: {rows.length} · next_cursor: {r.next_cursor ? "есть" : "null"}</span>
            {Boolean(r.next_cursor) && !sandbox.done && (
              <button type="button" className="hud-chip text-lime" onClick={() => run({ action: "list_records", table: String(r.table), cursor: String(r.next_cursor), limit: PAGE_LIMIT })}>
                СЛЕДУЮЩАЯ СТРАНИЦА (1 шаг)
              </button>
            )}
          </div>
        </>
      );
    }
    if (action.action === "calculator") return <p className="font-arcade text-xl text-lime break-all">{String(r.value)}</p>;
    const obj = (r.record ?? r.document ?? r) as Row;
    return (
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-0.5">
        {Object.entries(obj).map(([k, v]) => (
          <div key={k} className="contents"><dt className="text-fog">{k}</dt><dd className="break-all">{
            k === "line_items" && Array.isArray(v)
              ? (v as Row[]).map((li, i) => <div key={i}>{String(li.description)} · {String(li.quantity)}×{String(li.unit_price_minor)} = {String(li.amount_minor)} · {String(li.service_period_start)}…{String(li.service_period_end)}</div>)
              : idCell(v)}</dd></div>
        ))}
      </dl>
    );
  };

  const typesPolicy = ep.policy.findings.types;
  const left = sandbox.remaining();

  return (
    <div className="flex flex-col gap-5">
      <p className="bg-stamp text-white px-4 py-2 font-mono shadow-px" role="note"><b className="font-arcade text-[14px] mr-2">ЧЕСТНО</b>{HONEST}</p>

      <div className="px-panel p-4 flex flex-wrap items-center gap-x-8 gap-y-3">
        <Odometer value={left} />
        <div className="flex flex-col gap-1">
          <div className="label">энергия ревизора</div>
          <Bar value={left} max={MAX_ACTIONS} cells={25} color={left > 30 ? "bg-leaf" : left > 10 ? "bg-gold" : "bg-stamp"} label="Энергия" />
        </div>
        <div className="font-mono text-sm text-fog">
          эпизод {ep.episode_id} · {ep.manifest.company} · {base}<br />
          шагов проверки: <b className="text-paper">{sandbox.inspection}</b> · штраф за шаги: <b className="text-paper">{num(sandbox.inspection * 0.002, 3)}</b>
        </div>
      </div>

      <div className="flex flex-wrap gap-3" role="toolbar" aria-label="Инструменты агента">
        {TOOLS.map((t) => (
          <button key={t.id} type="button" aria-pressed={tool === t.id} title={t.hint}
            onClick={() => { play("blip"); setTool(t.id); }}
            className={`px-btn ${t.id === "submit" ? "px-btn--red" : tool === t.id ? "" : "px-btn--ghost"} flex flex-col items-center gap-1 min-w-[112px]`}>
            <span className="text-[14px]">{t.id}</span><span className="font-mono normal-case text-[14px]">{t.ru}</span>
          </button>
        ))}
      </div>

      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); execute(); }}>
        {(tool === "list_records" || tool === "get_record") && (
          <label className="flex flex-col gap-1"><span className="label">table</span>
            <select className="px-input" value={table} onChange={(e) => { setTable(e.target.value); setCursor(nextCursor.current[e.target.value] ?? ""); }}>
              {TABLES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select></label>
        )}
        {tool === "list_records" && <>
          <label className="flex flex-col gap-1 w-56"><span className="label">cursor (пусто = с начала)</span>
            <input className="px-input" value={cursor} onChange={(e) => setCursor(e.target.value)} /></label>
          <label className="flex flex-col gap-1 w-20"><span className="label">limit</span>
            <input className="px-input" value={limit} onChange={(e) => setLimit(e.target.value)} inputMode="numeric" /></label>
        </>}
        {tool === "get_record" && <label className="flex flex-col gap-1 w-64"><span className="label">id</span>
          <input className="px-input" value={recId} onChange={(e) => setRecId(e.target.value)} placeholder="row_id, doc_id, invoice_id…" /></label>}
        {tool === "get_document" && <label className="flex flex-col gap-1 w-64"><span className="label">doc_id</span>
          <input className="px-input" value={docId} onChange={(e) => setDocId(e.target.value)} placeholder="doc_id или INV-/PAY-…" /></label>}
        {tool === "calculator" && <label className="flex flex-col gap-1 flex-1 min-w-[240px]"><span className="label">expression</span>
          <input className="px-input" value={expr} onChange={(e) => setExpr(e.target.value)} placeholder="137244 * 3.0698 * 100" /></label>}
        {tool === "submit"
          ? <PxButton tone="red" type="submit" disabled={Boolean(result)}>СДАТЬ БЛАНК (submit)</PxButton>
          : <PxButton type="submit" disabled={sandbox.done}>ВЫПОЛНИТЬ (1 шаг)</PxButton>}
      </form>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div className="term p-3 min-h-[220px]" aria-live="polite" aria-label="Ответ среды">{renderOut()}</div>
        <aside className="px-panel p-3 font-mono text-[14px] max-h-[440px] overflow-auto scroll-thin" aria-label="Журнал действий">
          <div className="label mb-2">журнал</div>
          <ol className="flex flex-col gap-0.5">
            {journal.map((j) => <li key={j.n} className={j.err ? "text-ember" : ""}><span className="text-dusk">{String(j.n).padStart(3, "0")}</span> {j.text}</li>)}
          </ol>
        </aside>
      </div>

      <details className="px-panel p-3">
        <summary className="cursor-pointer font-arcade text-[14px] text-gold">БЕСТИАРИЙ: 4 ТИПА ОШИБОК И ЧЕМ ИХ ДОКАЗЫВАТЬ</summary>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {TYPES.map((t) => {
            const p = typesPolicy[t] ?? {};
            return (
              <div key={t} className="bg-night p-3">
                <div className="font-arcade text-[14px] text-ember">{TYPE_RU[t]}</div>
                <div className="font-mono text-[14px] text-fog">{t}</div>
                {typeof p.affected_ids === "string"
                  ? <div className="text-sm mt-1"><span className="text-fog">affected_ids:</span> <span className="font-mono">{p.affected_ids}</span></div>
                  : Object.entries((p.variants ?? {}) as Record<string, { affected_ids?: string }>).map(([v, d]) => (
                    <div key={v} className="text-sm mt-1"><span className="text-fog">{v}:</span> <span className="font-mono">{d.affected_ids ?? ""}</span></div>
                  ))}
                <div className="text-sm"><span className="text-fog">допуск:</span> {String(p.tolerance_minor ?? "—")}</div>
                {Array.isArray(p.evidence) && <ul className="text-sm list-[square] pl-5 mt-1">{(p.evidence as string[]).map((e) => <li key={e}>{e}</li>)}</ul>}
              </div>
            );
          })}
        </div>
      </details>

      <section className="flex flex-col gap-3" aria-label="Бланк вывода">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b-4 border-slate pb-2">
          <h2 className="font-arcade text-[14px] text-gold">БЛАНК ВЫВОДА · {ep.episode_id}</h2>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="hud-chip" onClick={() => {
              if (!jsonMode) setJsonText(payloadText());
              else { try { const p = JSON.parse(jsonText) as { findings: FindingIn[] }; setDrafts(p.findings.map((f) => ({ type: String(f.type ?? ""), affected: (f.affected_ids ?? []).join(", "), amount: String(f.claimed_amount_minor ?? ""), currency: String(f.currency ?? ""), evidence: (f.evidence_ids ?? []).join(", "), explanation: String(f.explanation ?? "") }))); } catch { return; } }
              setJsonMode(!jsonMode);
            }}>{jsonMode ? "ФОРМА" : "JSON"}</button>
            <button type="button" className="hud-chip" disabled={helped !== "none" || Boolean(result)} onClick={() => {
              const iss = ep.truth.issues[0];
              if (!iss) return;
              setHelped("hint"); setHint(`Ищи «${TYPE_RU[iss.type] ?? iss.type}» на ${iss.affected_ids.join(" + ")}.`); play("coin");
            }}>ПОДСКАЗКА</button>
            <button type="button" className="hud-chip" disabled={Boolean(result)} onClick={() => {
              setHelped("autopilot");
              setDrafts(kit.auditorFindings.map((f) => ({ type: f.type, affected: f.affected_ids.join(", "), amount: String(f.claimed_amount_minor), currency: f.currency, evidence: f.evidence_ids.join(", "), explanation: f.explanation })));
              setJsonMode(false); play("coin"); fx.sparkle(invRef.current, 20);
            }} title="Заполнить бланк ответом скриптового аудитора (trajectories.jsonl)">АВТОПИЛОТ АУДИТОРА</button>
          </div>
        </div>
        {hint && <Say who="Подсказка">{hint}</Say>}

        <div ref={invRef} className="px-panel p-3">
          <div className="label mb-2">инвентарь квитанций ({inventory.length}) — клик добавляет ID в активное поле</div>
          <div className="flex flex-wrap gap-2">
            {inventory.length === 0 && <span className="text-fog text-sm">пусто: кликай по синим ID в распечатке</span>}
            <AnimatePresence>
              {inventory.map((id) => (
                <motion.button key={id} type="button" layout initial={calm ? false : { scale: 0, rotate: -30 }} animate={{ scale: 1, rotate: 0 }}
                  className="flex items-center gap-1 bg-night px-2 py-1 font-mono text-[14px] text-sky hover:bg-carbon/30" onClick={() => collect(id)}>
                  <Sprite name="receipt" scale={2} animate={false} />{id}
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        </div>

        {jsonMode ? (
          <textarea className="px-input min-h-[260px]" value={jsonText} onChange={(e) => setJsonText(e.target.value)} aria-label="JSON ответа" spellCheck={false} />
        ) : (
          <div className="flex flex-col gap-5">
            {drafts.map((d, i) => {
              const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDrafts((ds) => ds.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)));
              const isActive = (f: "affected" | "evidence") => active.i === i && active.field === f;
              return (
                <div key={i} className="relative">
                  <div className="absolute inset-0 translate-x-2 translate-y-2 bg-carbon/60" aria-hidden="true" />
                  <fieldset className="relative px-paper p-3 grid gap-2 sm:grid-cols-6">
                    <legend className="sr-only">Вывод {i + 1}</legend>
                    <div className="sm:col-span-6 flex justify-between font-arcade text-[14px]"><span>ВЫВОД № {i + 1}</span>
                      {drafts.length > 1 && <button type="button" className="text-stamp underline" onClick={() => setDrafts((ds) => ds.filter((_, j) => j !== i))}>убрать</button>}</div>
                    <label className="sm:col-span-2 flex flex-col text-[14px]">type
                      <input className="px-input" list="vtypes" value={d.type} onChange={set("type")} placeholder="duplicate_invoice" /></label>
                    <label className="sm:col-span-2 flex flex-col text-[14px]">claimed_amount_minor
                      <input className="px-input" value={d.amount} onChange={set("amount")} inputMode="numeric" placeholder="целое, минимальные единицы" /></label>
                    <label className="sm:col-span-2 flex flex-col text-[14px]">currency (точно, без обрезки)
                      <input className="px-input" value={d.currency} onChange={set("currency")} /></label>
                    <label className={`sm:col-span-3 flex flex-col text-[14px] ${isActive("affected") ? "outline outline-2 outline-gold" : ""}`}>affected_ids
                      <input className="px-input" value={d.affected} onChange={set("affected")} onFocus={() => setActive({ i, field: "affected" })} placeholder="через запятую" /></label>
                    <label className={`sm:col-span-3 flex flex-col text-[14px] ${isActive("evidence") ? "outline outline-2 outline-gold" : ""}`}>evidence_ids ({split(d.evidence).length}/{LIMITS.evidence})
                      <input className="px-input" value={d.evidence} onChange={set("evidence")} onFocus={() => setActive({ i, field: "evidence" })} placeholder="квитанции через запятую" /></label>
                    <label className="sm:col-span-6 flex flex-col text-[14px]">explanation ({codePoints(d.explanation)}/{LIMITS.explanation})
                      <input className="px-input" value={d.explanation} onChange={set("explanation")} /></label>
                  </fieldset>
                </div>
              );
            })}
            <datalist id="vtypes">{TYPES.map((t) => <option key={t} value={t} />)}</datalist>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          {!jsonMode && <PxButton tone="ghost" disabled={drafts.length >= LIMITS.findings} onClick={() => { setDrafts((ds) => [...ds, emptyDraft(base)]); setActive({ i: drafts.length, field: "affected" }); }}>+ ВЫВОД ПОД КОПИРКУ</PxButton>}
          <PxButton tone="red" sfx="stamp" disabled={Boolean(result)} onClick={() => submit(false)}>СДАТЬ БЛАНК</PxButton>
        </div>
      </section>

      {result && (
        <div ref={resRef} className="px-panel p-4 relative">
          <div className="absolute right-4 top-4"><Stamp text={result.g.valid ? "ПРИНЯТО" : "НЕВЕРНАЯ СТРУКТУРА"} tone={result.g.valid ? (result.g.reward > 0 ? "green" : "red") : "red"} /></div>
          <h2 className="font-arcade text-[14px] text-gold">ОЦЕНКА MATCHER</h2>
          <div className="mt-3 flex flex-wrap gap-x-8 gap-y-2 font-arcade text-[14px]">
            <span className="text-lime">TP {result.g.tp}</span><span className="text-ember">FP {result.g.fp}</span><span className="text-sky">FN {result.g.fn}</span>
            <span>F1 {num(result.g.f1, 3)}</span><span>ШАГОВ {result.g.inspection_steps}</span>
            <span className={result.g.reward > 0 ? "text-lime" : "text-ember"}>НАГРАДА {signed(result.g.reward, 3)} ({frac(result.g.reward_exact)})</span>
          </div>
          {!result.g.valid && <ul className="mt-2 text-ember text-sm">{result.g.errors.map((e, i) => <li key={i}>{STRUCT_RU[e.code] ?? e.code}: <span className="font-mono">{e.path}</span></li>)}</ul>}
          {result.g.matching.length > 0 && (
            <table className="data-table mt-3">
              <thead><tr><th>№</th><th>тип</th><th>записи</th><th>вердикт</th></tr></thead>
              <tbody>{result.g.matching.map((m) => {
                const f = result.findings[m.finding_index] as Partial<FindingIn> | undefined;
                return (
                  <tr key={m.finding_index}>
                    <td>{m.finding_index + 1}</td><td>{String(f?.type ?? "")}</td><td>{(f?.affected_ids ?? []).join(", ")}</td>
                    <td className={m.issue_id ? "text-lime" : "text-ember"}>{m.issue_id ? `TP → ${m.issue_id}` : `FP: ${REASON_RU[m.fp_reason ?? ""] ?? m.fp_reason}`}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          )}
          <details className="mt-4" open>
            <summary className="cursor-pointer font-arcade text-[14px] text-sky">ЭТАЛОН ЭПИЗОДА (в среде агент его не видит)</summary>
            <table className="data-table mt-2">
              <thead><tr><th>issue</th><th>тип</th><th>записи</th><th className="n">сумма</th><th className="n">допуск</th><th>одна полная квитанция</th></tr></thead>
              <tbody>{ep.truth.issues.map((iss) => (
                <tr key={iss.issue_id} className={result.g.missed_issue_ids.includes(iss.issue_id) ? "text-fog" : "text-lime"}>
                  <td>{iss.issue_id}</td><td>{iss.type}{iss.interaction_group ? ` (${iss.interaction_group})` : ""}</td><td>{iss.affected_ids.join(", ")}</td>
                  <td className="n">{iss.expected_amount_minor}</td><td className="n">{iss.tolerance_minor ?? 0}</td>
                  <td className="break-all">{(iss.evidence_ids ?? iss.evidence_sets?.[0] ?? []).join(", ")}</td>
                </tr>
              ))}</tbody>
            </table>
          </details>
          <p className="mt-3 text-sm text-fog">Скриптовый аудитор на этом эпизоде: {ep.auditor ? `${signed(ep.auditor.reward, 3)} за ${ep.auditor.inspection_steps} шагов` : "—"} (trajectories.jsonl).</p>
          <div className="mt-3">
            <PxButton onClick={() => {
              const g = result.g;
              let stars = g.reward >= 0.9 ? 3 : g.reward >= 0.3 ? 2 : 1;
              if (helped === "autopilot") stars = Math.min(stars, 2);
              finish({
                stars,
                lines: [
                  { label: "TP / FP / FN", value: `${g.tp} / ${g.fp} / ${g.fn}`, tone: g.fp ? "bad" : "good" },
                  { label: "F1", value: num(g.f1, 3) },
                  { label: "Шагов проверки", value: String(g.inspection_steps) },
                  { label: "Награда", value: signed(g.reward, 3), tone: g.reward > 0 ? "good" : "bad" },
                  ...(helped === "autopilot" ? [{ label: "Автопилот", value: "да (макс. 2 звезды)", tone: "info" as const }] : []),
                ],
                note: "Оценка — JS-копия matcher по опубликованным правилам; тесты сверяют её с Python-грейдером.",
              });
            }}>ДАЛЕЕ</PxButton>
          </div>
        </div>
      )}
    </div>
  );
}
