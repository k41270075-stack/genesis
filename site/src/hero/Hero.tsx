// First screen: warp tunnel of ledger rows -> a receipt prints -> the stamp hits.
import { motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useEffect, useState } from "react";
import { readme } from "../data";
import { signed, num } from "../lib/format";
import { facts, TYPE_RU, useKit } from "../lib/kit";
import { IMPACT } from "./Storm";

const Storm = lazy(() => import("./Storm"));

function Words({ text, delay, className = "" }: { text: string; delay: number; className?: string }) {
  return (
    <span className={className}>
      {text.split(" ").map((w, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.08em] align-bottom">
          <motion.span className="inline-block" initial={{ y: "110%" }} animate={{ y: 0 }}
            transition={{ delay: delay + i * 0.09, duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }}>
            {w}{" "}
          </motion.span>
        </span>
      ))}
    </span>
  );
}

function Counter({ to, delay, format = (v: number) => num(Math.round(v)) }: { to: number; delay: number; format?: (v: number) => string }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf = 0;
    const t0 = performance.now() + delay * 1000;
    const tick = (now: number) => {
      const x = Math.min(1, Math.max(0, (now - t0) / 1400));
      setV(to * (1 - Math.pow(1 - x, 4)));
      if (x < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, delay]);
  return <>{format(v)}</>;
}

function Receipt() {
  const kit = useKit();
  const lines: { l: string; r?: string; cls?: string }[] = [];
  let reward = "";
  if (kit) {
    const g = kit.grade(kit.auditorFindings, kit.auditorSteps);
    reward = signed(g.reward);
    lines.push({ l: "VOUCHAI · АКТ СВЕРКИ", cls: "font-bold tracking-widest" });
    lines.push({ l: kit.ep.episode_id, cls: "text-paperInk/60" });
    lines.push({ l: `${kit.ep.manifest.company} · ${kit.base} · ${kit.ep.manifest.timezone}`, cls: "text-paperInk/60" });
    lines.push({ l: "—", cls: "rule" });
    kit.auditorFindings.slice(0, 3).forEach((f) => {
      lines.push({ l: TYPE_RU[f.type] ?? f.type, r: kit.money(f.claimed_amount_minor, f.currency), cls: "font-semibold" });
      lines.push({ l: `↳ ${f.evidence_ids.slice(0, 3).join(" ")}`, cls: "text-[10px] text-paperInk/60" });
    });
    lines.push({ l: `… ещё ${kit.auditorFindings.length - 3}`, cls: "text-paperInk/50" });
    lines.push({ l: "—", cls: "rule" });
    lines.push({ l: `TP ${g.tp} · FP ${g.fp} · FN ${g.fn}`, r: `шагов ${g.inspection_steps}` });
    lines.push({ l: "НАГРАДА", r: reward, cls: "text-[15px] font-bold" });
  }
  return (
    <div className="relative w-[300px] sm:w-[330px]">
      {/* the slot of the printer */}
      <motion.div className="relative z-10 mx-auto h-3 w-[110%] -translate-x-[4.5%] rounded-full bg-black shadow-[0_6px_20px_rgba(0,0,0,.9)] ring-1 ring-line2"
        initial={{ opacity: 0, scaleX: 0.3 }} animate={{ opacity: 1, scaleX: 1 }} transition={{ delay: 0.45, duration: 0.4 }} />
      <div className="-mt-1.5 overflow-hidden">
        <motion.div className="receipt px-5 pt-5 text-[11.5px] leading-[1.7] shadow-card"
          initial={{ y: "-102%" }} animate={{ y: 0 }} transition={{ delay: 0.7, duration: 1.4, ease: [0.3, 0.7, 0.2, 1] }}>
          {lines.map((x, i) => x.cls === "rule"
            ? <div key={i} className="my-1.5 border-t border-dashed border-paperInk/40" />
            : (
              <motion.div key={i} className={`flex justify-between gap-3 ${x.cls ?? ""}`}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 + i * 0.07 }}>
                <span className="truncate">{x.l}</span>{x.r && <span className="shrink-0 tabnum">{x.r}</span>}
              </motion.div>
            ))}
          {!kit && <div className="h-[300px]" />}
        </motion.div>
      </div>
      {/* the stamp */}
      <motion.div className="pointer-events-none absolute bottom-[86px] right-[-34px] z-20"
        initial={{ scale: 3.2, opacity: 0, rotate: -34 }} animate={{ scale: 1, opacity: 1, rotate: -13 }}
        transition={{ delay: IMPACT - 0.16, duration: 0.18, ease: [0.5, 0, 0.75, 0] }}>
        <div className="stamp bg-transparent text-[26px] leading-none">доказано</div>
        <div className="mt-1 text-right font-mono text-[10px] font-bold uppercase tracking-widest text-stamp">квитанции приложены</div>
      </motion.div>
      {/* shockwave */}
      <motion.div className="pointer-events-none absolute bottom-24 right-4 z-0 h-40 w-40 rounded-full border-2 border-stamp"
        initial={{ scale: 0, opacity: 0 }} animate={{ scale: [0, 7], opacity: [0.9, 0] }}
        transition={{ delay: IMPACT, duration: 1.1, ease: "easeOut" }} />
    </div>
  );
}

export function Hero({ onTour }: { onTour: () => void }) {
  const reduced = !!useReducedMotion();
  const [webgl] = useState(() => {
    try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; }
  });
  const stats = [
    facts.selftest && { v: facts.selftest.ok, s: `/${facts.selftest.all}`, k: "проверки жюри, наша эмуляция", f: "reports/JURY_SELFTEST.md" },
    facts.recipes && { v: facts.recipes.ok, s: `/${facts.recipes.all}`, k: "эпизоды D01–D20 × 40 seed", f: "reports/RECIPES.md" },
    facts.attacks && { v: facts.attacks, s: "", k: `атаки на награду, лучшая F1 ${facts.bestF1?.replace(".", ",")}`, f: "reports/ATTACK_SEARCH.md" },
    facts.graphs && { v: facts.graphs, s: "", k: "графы matcher против перебора", f: "tests/test_matcher_exhaustive.py" },
  ].filter(Boolean) as { v: number; s: string; k: string; f: string }[];

  return (
    <section id="top" className="relative flex min-h-[100svh] flex-col overflow-hidden">
      <div className="absolute inset-0">
        {webgl && <Suspense fallback={null}><Storm reduced={reduced} /></Suspense>}
      </div>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(5,6,10,.55)_55%,#05060A_100%)]" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-48 bg-gradient-to-b from-transparent to-void" />
      <motion.div className="pointer-events-none absolute inset-0 bg-[#FFE6DA]" initial={{ opacity: 0 }}
        animate={{ opacity: [0, 0.22, 0] }} transition={{ delay: IMPACT, duration: 0.5, times: [0, 0.1, 1] }} />

      <motion.div className="relative z-10 mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-5 pb-8 pt-24 sm:px-8"
        animate={reduced ? undefined : { x: [0, -10, 9, -6, 4, 0], y: [0, 6, -5, 3, -1, 0] }}
        transition={{ delay: IMPACT, duration: 0.45 }}>
        <div className="grid flex-1 items-center gap-12 lg:grid-cols-[1fr_auto]">
          <div>
            <motion.p className="eyebrow mb-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
              <span className="text-stamp">RL-среда</span> для ИИ-аудиторов · Genesis Hackathon 2026, кейс FinTech
            </motion.p>
            <h1 className="h-display text-[clamp(40px,5.8vw,92px)]">
              <Words text="Каждый вывод" delay={0.25} /><br />
              <Words text="требует" delay={0.5} />
              <span className="relative inline-block">
                <Words text="квитанции." delay={0.62} className="text-stamp" />
                <motion.span className="absolute -bottom-1 left-0 h-[0.07em] w-full origin-left bg-stamp"
                  initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: IMPACT, duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }} />
              </span>
            </h1>
            <motion.p className="mt-7 max-w-[620px] text-[17px] text-soft sm:text-[19px]"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.3, duration: 0.7 }}>
              VouchAI — тренажёр для ИИ-аудиторов. Он создаёт вымышленную компанию, прячет в её книгах ошибки и
              законных «двойников», а награду даёт только за вывод, который доказан ссылками на записи.
              <span className="mt-2 block font-mono text-[13px] text-mute">{readme.slogan ?? "Every claim needs a receipt."}</span>
            </motion.p>
            <motion.div className="mt-9 flex flex-wrap gap-3" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.6 }}>
              <button className="btn-red" onClick={onTour}>
                <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 1.5v11l9-5.5z" fill="currentColor" /></svg>
                Автотур · 60 секунд
              </button>
              <a className="btn-ghost" href="#game">Сыграть: ошибка или двойник? ↓</a>
            </motion.div>
          </div>
          <div className="mx-auto lg:mr-6 lg:scale-[1.12] lg:origin-right"><Receipt /></div>
        </div>

        <motion.div className="mt-10 max-w-[760px] font-mono text-[13px]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: IMPACT + 0.15, duration: 0.4 }}>
          {stats.map((s, i) => (
            <motion.div key={i} className="flex items-baseline gap-3 border-b border-line/70 py-2" initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }} transition={{ delay: IMPACT + 0.25 + i * 0.1 }}>
              <span className="shrink-0 text-soft">{s.k}</span>
              <span className="rule-dots h-3 flex-1" />
              <span className="tabnum shrink-0 text-[15px] font-bold text-text"><Counter to={s.v} delay={IMPACT + 0.3 + i * 0.1} /><span className="text-mute">{s.s}</span></span>
              <a href={`https://github.com/k41270075-stack/vouchai/blob/main/${s.f}`} target="_blank" rel="noreferrer"
                className="hidden w-[190px] shrink-0 truncate text-right text-[11.5px] text-mute hover:text-sky sm:block">{s.f}</a>
            </motion.div>
          ))}
        </motion.div>
      </motion.div>
    </section>
  );
}
