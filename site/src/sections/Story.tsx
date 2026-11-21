// How it works in one screen: the path of an episode, and two answers to it.
import { motion } from "framer-motion";
import presetsJson from "../../data/grade_presets.json";
import { signed } from "../lib/format";

const STEPS = [
  ["Генератор", "вымышленная компания: книга, счета, платежи, курсы"],
  ["Ошибки и двойники", "4 вида ошибок, 25 видов законных похожих случаев"],
  ["Агент", "5 инструментов, 100 шагов, видит только таблицы"],
  ["Ответ", "каждый вывод — со ссылками на записи-квитанции"],
  ["Награда", "clip(2·F1 − 1 − 0,002·шаги, −1, 1)"],
];

interface P { key: string; title: string; steps: number; payload: { findings: { explanation: string; evidence_ids: string[] }[] }; python: { return: number; tp: number | null; fp: number | null; fn: number | null } }
const presets = (presetsJson as { presets: P[] }).presets;

export function Story() {
  const essay = presets.find((p) => p.key === "essay");
  const auditor = presets.find((p) => p.key === "auditor");
  return (
    <section id="how" className="relative mx-auto max-w-[1320px] px-5 py-24 sm:px-8">
      <p className="eyebrow">как устроено</p>
      <h2 className="h-display mt-4 max-w-[900px] text-[clamp(32px,4.2vw,60px)]">Награда — только за доказанное</h2>

      <div className="relative mt-14">
        <svg className="pointer-events-none absolute left-0 right-0 top-[27px] hidden h-2 w-full lg:block" preserveAspectRatio="none" viewBox="0 0 1000 8">
          <line x1="40" y1="4" x2="960" y2="4" stroke="#2A3145" strokeWidth="2" strokeDasharray="4 6" />
          <circle r="5" fill="#FF4D3D" cy="4">
            <animate attributeName="cx" from="40" to="960" dur="3.2s" repeatCount="indefinite" />
          </circle>
        </svg>
        <div className="grid gap-6 lg:grid-cols-5">
          {STEPS.map(([a, b], i) => (
            <motion.div key={a} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}>
              <div className={`relative z-10 grid h-14 w-14 place-items-center rounded-2xl border font-mono text-[15px] ${i === 4 ? "border-stamp bg-stamp/15 text-stamp" : "border-line2 bg-ink"}`}>
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="mt-4 text-[18px] font-bold">{a}</div>
              <div className={`mt-1 text-[14px] leading-snug ${i === 4 ? "font-mono text-[12.5px] text-text" : "text-mute"}`}>{b}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {essay && auditor && (
        <div className="mt-20 grid gap-4 md:grid-cols-2">
          <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
            className="relative overflow-hidden rounded-2xl border border-stamp/30 bg-stamp/[0.04] p-6">
            <div className="eyebrow text-stamp">ответ «красиво»</div>
            <p className="mt-4 text-[15px] italic leading-relaxed text-soft">«{essay.payload.findings[0]!.explanation}»</p>
            <div className="mt-5 flex items-end justify-between">
              <span className="font-mono text-[12px] text-mute">квитанций: {essay.payload.findings[0]!.evidence_ids.length}</span>
              <span className="h-display text-[54px] leading-none text-stamp">{signed(essay.python.return)}</span>
            </div>
          </motion.div>
          <motion.div initial={{ opacity: 0, x: 30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
            className="relative overflow-hidden rounded-2xl border border-ok/30 bg-ok/[0.04] p-6">
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
