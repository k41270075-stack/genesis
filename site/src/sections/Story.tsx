// How it works in one screen: the path of an episode, and two answers to it.
import { motion } from "framer-motion";
import presetsJson from "../../data/grade_presets.json";
import { num, signed } from "../lib/format";
import { useKit } from "../lib/kit";

interface P { key: string; title: string; steps: number; payload: { findings: { explanation: string; evidence_ids: string[] }[] }; python: { return: number; tp: number | null; fp: number | null; fn: number | null } }
const presets = (presetsJson as { presets: P[] }).presets;

function Trace() {
  const kit = useKit();
  if (!kit) return <div className="mt-14 h-[150px]" />;
  const m = kit.ep.manifest, c = m.counts;
  const issues = kit.ep.truth.issues;
  const kinds = new Set(issues.map((i) => i.type)).size;
  const g = kit.grade(kit.auditorFindings, kit.auditorSteps);
  const ev = kit.auditorFindings.reduce((n, f) => n + f.evidence_ids.length, 0);
  const cols: [string, string, string][] = [
    ["генератор", `${m.company}`, `${m.period_start.slice(0, 7)} · ${m.base_currency} · ${m.timezone}`],
    ["книги", `${num(c.ledger_rows ?? 0)} строк`, `${c.invoices} счетов · ${c.payments} платежей · ${c.fx_rates} курсов`],
    ["спрятано", `${issues.length} ошибок`, `${kinds} вида из 4; рядом законные двойники`],
    ["агент", `${kit.auditorSteps} шагов`, `из 100; видит только таблицы`],
    ["ответ", `${kit.auditorFindings.length} выводов`, `${ev} ссылок-квитанций`],
    ["награда", signed(g.reward, 3), `TP ${g.tp} · FP ${g.fp} · FN ${g.fn}`],
  ];
  return (
    <div className="mt-14 grid border-y border-line2 sm:grid-cols-3 lg:grid-cols-6">
      {cols.map(([k, v, d], i) => (
        <motion.div key={k} className="relative border-b border-line px-4 py-6 sm:border-r lg:border-b-0"
          initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
          <div className="font-mono text-[11.5px] text-mute">{String(i + 1).padStart(2, "0")} {k}</div>
          <div className={`mt-3 font-display text-[24px] font-bold leading-tight ${i === 5 ? "text-ok" : i === 2 ? "text-stamp" : ""}`}>{v}</div>
          <div className="mt-1.5 text-[12.5px] leading-snug text-mute">{d}</div>
          {i < 5 && <div className="absolute -right-[7px] top-1/2 z-10 hidden h-3 w-3 -translate-y-1/2 rotate-45 border-r border-t border-line2 bg-void lg:block" />}
        </motion.div>
      ))}
    </div>
  );
}

export function Story() {
  const essay = presets.find((p) => p.key === "essay");
  const auditor = presets.find((p) => p.key === "auditor");
  return (
    <section id="how" className="relative mx-auto max-w-[1320px] px-5 py-24 sm:px-8">
      <p className="eyebrow"><span className="text-stamp">1200</span> — как устроено, на одном настоящем эпизоде</p>
      <h2 className="h-display mt-4 max-w-[900px] text-[clamp(32px,4.2vw,60px)]">Награда — только за доказанное</h2>
      <Trace />

      {essay && auditor && (
        <div className="mt-20 grid gap-4 md:grid-cols-2">
          <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
            className="relative overflow-hidden rounded-lg border border-stamp/30 bg-stamp/[0.04] p-6">
            <div className="eyebrow text-stamp">ответ «красиво»</div>
            <p className="mt-4 text-[15px] italic leading-relaxed text-soft">«{essay.payload.findings[0]!.explanation}»</p>
            <div className="mt-5 flex items-end justify-between">
              <span className="font-mono text-[12px] text-mute">квитанций: {essay.payload.findings[0]!.evidence_ids.length}</span>
              <span className="h-display text-[54px] leading-none text-stamp">{signed(essay.python.return)}</span>
            </div>
          </motion.div>
          <motion.div initial={{ opacity: 0, x: 30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
            className="relative overflow-hidden rounded-lg border border-ok/30 bg-ok/[0.04] p-6">
            <div className="eyebrow text-ok">ответ «доказано»</div>
            <div className="mt-4 space-y-1.5 font-mono text-[12.5px] text-soft">
              {auditor.payload.findings.slice(0, 4).map((f, i) => <div key={i} className="truncate">{f.evidence_ids.join(" · ")}</div>)}
              <div className="text-mute">… {auditor.payload.findings.length} выводов, у каждого — свои квитанции</div>
            </div>
            <div className="mt-5 flex items-end justify-between">
              <span className="font-mono text-[12px] text-mute">TP {auditor.python.tp} · FP {auditor.python.fp} · FN {auditor.python.fn}</span>
              <span className="h-display text-[54px] leading-none text-ok">{signed(auditor.python.return)}</span>
            </div>
          </motion.div>
          <p className="text-[12px] text-mute md:col-span-2">Обе награды посчитаны настоящим <code className="kbd">judge_adapter.score_episode</code> на открытом эпизоде (site/grade_presets.py). Объяснение в выборе не участвует.</p>
        </div>
      )}
    </section>
  );
}
