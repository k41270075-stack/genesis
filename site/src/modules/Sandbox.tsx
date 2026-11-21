// Be the agent: the same five tools and the same 100-action budget over the open
// dev episode, run in the browser (src/lib/sandbox.ts), graded by the matcher.
import { useEffect, useMemo, useRef, useState } from "react";
import { signed } from "../lib/format";
import { useKit } from "../lib/kit";
import { MAX_ACTIONS, Sandbox as Env, TABLES, type Action, type Row, type StepResult } from "../lib/sandbox";
import { tablesOf } from "../lib/episode";
import { earn } from "../game/passport";
import { Label } from "./parts";
import type { VizProps } from "./types";

type Tool = "list_records" | "get_record" | "get_document" | "calculator" | "submit";
const TOOLS: { id: Tool; ru: string }[] = [
  { id: "list_records", ru: "листать таблицу" }, { id: "get_record", ru: "запись по ID" },
  { id: "get_document", ru: "документ" }, { id: "calculator", ru: "калькулятор" }, { id: "submit", ru: "сдать ответ" },
];
const COLS: Record<string, string[]> = {
  ledger: ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency"],
  invoices: ["invoice_id", "doc_id", "issued_at", "currency", "total_minor"],
  payments: ["payment_id", "doc_id", "timestamp", "currency", "amount_minor"],
  fx: ["id", "rate"],
};
const short = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v).slice(0, 40) : String(v));

export default function Sandbox({ setLive }: VizProps) {
  const kit = useKit();
  const env = useMemo(() => (kit ? new Env(kit.ep.episode_id, tablesOf(kit.ep)) : null), [kit]);
  const [tool, setTool] = useState<Tool>("list_records");
  const [table, setTable] = useState("invoices");
  const [id, setId] = useState("");
  const [expr, setExpr] = useState("1100760 * 2 - 37466");
  const [out, setOut] = useState<StepResult | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [left, setLeft] = useState(MAX_ACTIONS);
  const [score, setScore] = useState<string | null>(null);
  const cursors = useRef<Record<string, string | null>>({});

  useEffect(() => {
    if (!kit) return;
    const t = tablesOf(kit.ep);
    setId(String(t.invoices[0]?.doc_id ?? ""));
  }, [kit]);
  useEffect(() => {
    setLive?.(log.length ? log : ["# эпизод открыт: 100 действий, 5 инструментов", "# выберите инструмент слева и нажмите «Выполнить»"]);
  }, [log, setLive]);

  if (!kit || !env) return <div className="p-6 text-mute">загрузка эпизода…</div>;

  const exec = (findings?: "auditor" | "empty") => {
    let a: Action;
    if (tool === "list_records") a = { action: "list_records", table, cursor: cursors.current[table] ?? null };
    else if (tool === "get_record") a = { action: "get_record", table, id };
    else if (tool === "get_document") a = { action: "get_document", doc_id: id };
    else if (tool === "calculator") a = { action: "calculator", expression: expr };
    else a = { action: "submit", findings: { episode_id: kit.ep.episode_id, findings: findings === "auditor" ? kit.auditorFindings : [] } };
    const r = env.step(a);
    if (a.action === "list_records" && r.result) cursors.current[table] = (r.result.next_cursor as string | null) ?? null;
    setOut(r);
    setLeft(r.remaining_steps);
    const shownA = a.action === "submit" ? { action: "submit", findings: `<${findings === "auditor" ? kit.auditorFindings.length : 0} findings>` } : a;
    const brief = r.error ? { error: r.error.code } : a.action === "list_records" ? { rows: (r.result?.rows as Row[]).length, next_cursor: r.result?.next_cursor ? "…" : null }
      : a.action === "calculator" ? r.result : r.result ? { ok: true } : {};
    const lines = [`→ ${JSON.stringify(shownA)}`, `← ${JSON.stringify({ ...brief, remaining_steps: r.remaining_steps, done: r.done })}`];
    if (a.action === "submit") {
      const g = kit.grade(findings === "auditor" ? kit.auditorFindings : [], env.inspection);
      const s = `TP ${g.tp} · FP ${g.fp} · FN ${g.fn} · inspection_steps ${env.inspection} → награда ${signed(g.reward, 3)}`;
      setScore(s);
      earn("m:sandbox");
      lines.push(`# оценщик: ${s}`);
    }
    setLog((l) => [...l, ...lines].slice(-80));
  };
  const reset = () => { env.reset(); cursors.current = {}; setOut(null); setLeft(MAX_ACTIONS); setScore(null); setLog([]); };

  const rows = (out?.result?.rows as Row[] | undefined) ?? null;
  const tname = (out?.result?.table as string | undefined) ?? table;

  return (
    <div className="flex h-full flex-col gap-3 p-5">
      <div className="flex flex-wrap items-center gap-1.5">
        {TOOLS.map((t) => (
          <button key={t.id} onClick={() => setTool(t.id)} disabled={env.done}
            className={`rounded-full border px-3 py-1.5 font-mono text-[11.5px] transition ${tool === t.id ? "border-blue bg-blue/15 text-text" : "border-line text-soft hover:border-line2"}`}>
            {t.id}<span className="ml-1.5 hidden font-sans text-mute sm:inline">· {t.ru}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {(tool === "list_records" || tool === "get_record") && (
          <select value={table} onChange={(e) => setTable(e.target.value)} className="rounded-lg border border-line2 bg-void px-2 py-2 font-mono text-[12px]">
            {TABLES.map((t) => <option key={t}>{t}</option>)}
          </select>
        )}
        {(tool === "get_record" || tool === "get_document") && (
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="ID" className="w-48 rounded-lg border border-line2 bg-void px-3 py-2 font-mono text-[12px]" />
        )}
        {tool === "calculator" && (
          <input value={expr} onChange={(e) => setExpr(e.target.value)} className="w-64 rounded-lg border border-line2 bg-void px-3 py-2 font-mono text-[12px]" />
        )}
        {tool === "submit" ? (
          <>
            <button className="btn-red !py-2 text-[13px]" disabled={env.done} onClick={() => exec("auditor")}>Сдать ответ аудитора</button>
            <button className="btn-ghost !py-2 text-[13px]" disabled={env.done} onClick={() => exec("empty")}>Сдать пустой</button>
          </>
        ) : (
          <button className="btn-red !py-2 text-[13px]" disabled={env.done} onClick={() => exec()}>Выполнить · 1 шаг</button>
        )}
        <button className="ml-auto text-[12px] text-mute underline-offset-4 hover:underline" onClick={reset}>новый эпизод</button>
      </div>

      <div className="flex items-center gap-3">
        <Label>шаги</Label>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-line">
          <div className="h-full rounded-full transition-all duration-300" style={{ width: `${left}%`, background: left > 20 ? "#5B8CFF" : "#FF4D3D" }} />
        </div>
        <span className="tabnum font-mono text-[13px]">{left}/100</span>
      </div>

      <div className="scroll-thin min-h-[220px] flex-1 overflow-auto rounded-xl border border-line bg-void/60 p-3 font-mono text-[11px]">
        {!out && <div className="text-mute">Агент видит только то, что вернули инструменты. Эталон и оценщик — в другом процессе (здесь, в демо, — в браузере).</div>}
        {out?.error && <div className="text-stamp">{out.error.code}: {out.error.message}</div>}
        {rows && (
          <table className="w-full">
            <thead><tr>{COLS[tname]?.map((c) => <th key={c} className="pb-1 pr-3 text-left font-normal text-mute">{c}</th>)}</tr></thead>
            <tbody>{rows.slice(0, 12).map((r, i) => (
              <tr key={i} className="border-t border-line/60">{COLS[tname]?.map((c) => <td key={c} className="py-1 pr-3 text-soft">{short(r[c])}</td>)}</tr>
            ))}</tbody>
          </table>
        )}
        {rows && rows.length > 12 && <div className="mt-1 text-mute">… и ещё {rows.length - 12} строк на этой странице</div>}
        {!rows && out?.result && <pre className="whitespace-pre-wrap text-soft">{JSON.stringify(out.result, null, 1).slice(0, 1600)}</pre>}
      </div>
      {score && <div className="rounded-xl border border-ok/40 bg-ok/10 px-4 py-3 text-[13px]"><b>Эпизод окончен.</b> {score}</div>}
    </div>
  );
}
