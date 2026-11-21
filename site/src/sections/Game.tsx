// «Ошибка или двойник?»: twelve cases from the open dev episode (site/game_cases.py).
// The visitor is the agent: accuse or let pass; the result is graded by the case's formula.
import { AnimatePresence, motion, useAnimationControls } from "framer-motion";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import gameJson from "../../data/game.json";
import presetsJson from "../../data/grade_presets.json";
import { hash01 } from "../engine/clock";
import { earn } from "../game/passport";
import { signed } from "../lib/format";
import { rewardOf } from "../lib/matcher";

interface Card { label: string; lines: [string, string][] }
interface Case { kind: "error" | "twin"; type: string; claim: string; cards: Card[]; explain: string }
const GAME = gameJson as unknown as { episode_id: string; company: string; cases: Case[] };
const PRESETS = (presetsJson as { presets: { key: string; steps: number; python: { return: number } }[] }).presets;
const LIMIT_MS = 20000;
const AuditDesk = lazy(() => import("../game/AuditDesk"));
const hasWebGL = (() => {
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; }
})();

type Verdict = "accuse" | "pass";

function shuffled(n: number, seed: number): number[] {
  return Array.from({ length: n }, (_, i) => i).sort((a, b) => hash01(a * 7919 + seed * 104729) - hash01(b * 7919 + seed * 104729));
}

function Doc({ card, i }: { card: Card; i: number }) {
  return (
    <motion.div className="receipt w-full max-w-[290px] rounded-t px-4 pt-3.5 text-[11.5px] leading-[1.6] shadow-card"
      initial={{ y: 40, opacity: 0, rotate: i % 2 ? 4 : -4 }} animate={{ y: 0, opacity: 1, rotate: i % 2 ? 1.2 : -1.2 }}
      transition={{ delay: 0.08 * i, type: "spring", stiffness: 240, damping: 22 }}>
      <div className="mb-1.5 border-b border-dashed border-paperInk/40 pb-1.5 font-bold uppercase tracking-wide">{card.label}</div>
      {card.lines.map(([k, v], j) => (
        <div key={j} className="flex justify-between gap-3"><span className="shrink-0 text-paperInk/55">{k}</span><span className="text-right">{v}</span></div>
      ))}
    </motion.div>
  );
}

export function Game() {
  const cases = GAME.cases;
  const [attempt, setAttempt] = useState(0);
  const [phase, setPhase] = useState<"intro" | "play" | "done">("intro");
  const [k, setK] = useState(0);
  const [answers, setAnswers] = useState<(Verdict | "timeout")[]>([]);
  const [shown, setShown] = useState<Verdict | "timeout" | null>(null);
  const [left, setLeft] = useState(LIMIT_MS);
  const shake = useAnimationControls();
  const order = useMemo(() => shuffled(cases.length, attempt + 1), [cases.length, attempt]);
  const cur = cases[order[k] ?? 0]!;
  const t0 = useRef(0);

  const score = useMemo(() => {
    let tp = 0, fp = 0, fn = 0, streak = 0, best = 0;
    answers.forEach((a, i) => {
      const c = cases[order[i]!]!;
      const accused = a === "accuse";
      const right = accused === (c.kind === "error");
      if (accused && c.kind === "error") tp++;
      if (accused && c.kind === "twin") fp++;
      if (!accused && c.kind === "error") fn++;
      streak = right ? streak + 1 : 0;
      best = Math.max(best, streak);
    });
    const r = rewardOf(tp, fp, fn, 0);
    return { tp, fp, fn, streak, best, reward: r.reward.n / r.reward.d, f1: r.f1.n / r.f1.d };
  }, [answers, cases, order]);

  const answer = useCallback((v: Verdict | "timeout") => {
    if (shown || phase !== "play") return;
    setShown(v);
    setAnswers((x) => [...x, v]);
    const right = (v === "accuse") === (cur.kind === "error");
    if (!right) void shake.start({ x: [0, -14, 12, -8, 5, 0], transition: { duration: 0.4 } });
  }, [shown, phase, cur.kind, shake]);

  const next = useCallback(() => {
    if (!shown) return;
    if (k + 1 >= cases.length) { setPhase("done"); return; }
    setK(k + 1); setShown(null); setLeft(LIMIT_MS);
  }, [shown, k, cases.length]);

  // per-case timer: running out = letting the case pass
  useEffect(() => {
    if (phase !== "play" || shown) return;
    t0.current = performance.now();
    let raf = 0;
    const tick = () => {
      const l = Math.max(0, LIMIT_MS - (performance.now() - t0.current));
      setLeft(l);
      if (l <= 0) { answer("timeout"); return; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [phase, shown, k, answer]);

  useEffect(() => {
    if (phase !== "play") return;
    const on = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!shown && (e.key === "1" || e.key === "ArrowLeft")) answer("accuse");
      else if (!shown && (e.key === "2" || e.key === "ArrowRight")) answer("pass");
      else if (shown && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); next(); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [phase, shown, answer, next]);

  useEffect(() => {
    if (phase !== "done") return;
    earn("game");
    if (score.reward >= 0.9) earn("game_ace");
  }, [phase, score.reward]);

  const start = () => { setAnswers([]); setK(0); setShown(null); setLeft(LIMIT_MS); setPhase("play"); };
  const again = () => { setAttempt((a) => a + 1); start(); };
  const auditor = PRESETS.find((p) => p.key === "auditor");
  const flag = PRESETS.find((p) => p.key === "flag_all");
  const right = shown ? ((shown === "accuse") === (cur.kind === "error")) : null;

  return (
    <section id="game" className="relative border-y border-line bg-[#08090d]">
      <div className="mx-auto max-w-[1320px] px-5 py-24 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_1fr] lg:items-end">
          <div>
            <p className="eyebrow"><span className="text-stamp">2150</span> — сыграйте за агента</p>
            <h2 className="h-display mt-4 text-[clamp(32px,4.2vw,60px)]">Ошибка или двойник?</h2>
          </div>
          <p className="max-w-[540px] text-[16px] text-soft lg:justify-self-end">
            {cases.length} случаев из открытого эпизода «{GAME.company}». Половина — настоящие ошибки, половина выглядит так же,
            но законна. Ложное обвинение стоит дороже молчания: в конце мы посчитаем вашу награду по формуле кейса.
          </p>
        </div>

        <div className="mt-12 rounded-lg border border-line bg-ink">
          {phase === "intro" && (
            <div className="grid gap-8 p-8 lg:grid-cols-[1.1fr_1fr] lg:items-center">
              {hasWebGL && (
                <div className="h-[340px] overflow-hidden rounded-md border border-line">
                  <Suspense fallback={null}><AuditDesk caseIndex={-1} act={null} right={null} left={cases.length} /></Suspense>
                </div>
              )}
              <div>
              <p className="mb-4 font-display text-[22px] font-bold leading-snug">Ревизор ждёт документы. Вы решаете — он ставит штамп.</p>
              <div className="space-y-2 text-[15px] text-soft">
                <div><span className="kbd">1</span> или <span className="kbd">←</span> — «ошибка, обвиняю»</div>
                <div><span className="kbd">2</span> или <span className="kbd">→</span> — «законно, пропускаю»</div>
                <div><span className="kbd">Enter</span> — следующий случай · на решение {LIMIT_MS / 1000} секунд</div>
              </div>
              <button className="btn-red mt-6 text-[16px]" onClick={start}>Начать ревизию</button>
              </div>
            </div>
          )}

          {phase === "play" && (
            <div className="p-5 sm:p-8">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[12px] text-mute">
                <span>случай {k + 1}/{cases.length}</span>
                <span>TP <b className="text-ok">{score.tp}</b> · FP <b className="text-stamp">{score.fp}</b> · FN <b className="text-gold">{score.fn}</b></span>
                {score.streak >= 2 && <span className="text-gold">серия ×{score.streak}</span>}
                <div className="ml-auto h-1.5 w-40 overflow-hidden rounded bg-line">
                  <div className="h-full" style={{ width: `${(left / LIMIT_MS) * 100}%`, background: left < 5000 ? "#FF4D3D" : "#5B8CFF" }} />
                </div>
              </div>
              <motion.div animate={shake} className={hasWebGL ? "mt-5 grid gap-6 lg:grid-cols-[1fr_1.05fr]" : ""}>
                {hasWebGL && (
                  <div className="h-[300px] overflow-hidden rounded-md border border-line lg:h-[420px]">
                    <Suspense fallback={null}>
                      <AuditDesk caseIndex={k + attempt * 100} act={shown} right={right} left={cases.length - k - 1} />
                    </Suspense>
                  </div>
                )}
                <div>
                <h3 className="font-display text-[clamp(22px,2.4vw,30px)] font-bold leading-tight">{cur.claim}</h3>
                <div className="relative mt-6 flex min-h-[230px] flex-wrap items-start justify-center gap-4" key={`${attempt}-${k}`}>
                  {cur.cards.map((c, i) => <Doc key={i} card={c} i={i} />)}
                  <AnimatePresence>
                    {shown && (
                      <motion.div className="pointer-events-none absolute left-1/2 top-1/2 z-10"
                        initial={{ scale: 3, opacity: 0, rotate: -30, x: "-50%", y: "-50%" }} animate={{ scale: 1, opacity: 1, rotate: -12, x: "-50%", y: "-50%" }}
                        transition={{ duration: 0.2, ease: [0.5, 0, 0.75, 0] }}>
                        <div className="whitespace-nowrap rounded-md px-5 py-2 font-display text-[40px] font-bold uppercase leading-none tracking-wide"
                          style={{ color: cur.kind === "error" ? "#FF4D3D" : "#7EA3FF", border: "5px double currentColor", background: "rgba(5,6,10,.88)" }}>
                          {cur.kind === "error" ? "ошибка" : "законно"}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
                </div>
              </motion.div>
              <div className="mt-8 border-t border-line pt-6">
                {!shown ? (
                  <div className="flex flex-wrap gap-3">
                    <button className="btn-red" onClick={() => answer("accuse")}>Ошибка — обвиняю <span className="kbd border-white/30 bg-transparent text-white/80">1</span></button>
                    <button className="btn-ghost" onClick={() => answer("pass")}>Законно — пропускаю <span className="kbd">2</span></button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-4">
                    <div className={`font-display text-[20px] font-bold ${right ? "text-ok" : "text-stamp"}`}>
                      {shown === "timeout" ? "Время вышло — случай пропущен. " : ""}{right ? "Верно." : cur.kind === "error" ? "Пропущена ошибка (FN)." : "Ложное обвинение (FP)."}
                    </div>
                    <p className="min-w-[260px] flex-1 text-[14px] text-soft">{cur.explain}</p>
                    <button className="btn-ghost" onClick={next}>{k + 1 >= cases.length ? "Итог" : "Дальше"} <span className="kbd">Enter</span></button>
                  </div>
                )}
              </div>
            </div>
          )}

          {phase === "done" && (
            <div className="grid gap-10 p-8 md:grid-cols-[auto_1fr] md:items-center">
              <div>
                <div className="eyebrow">ваша награда</div>
                <div className={`h-display tabnum mt-2 text-[88px] leading-none ${score.reward >= 0.5 ? "text-ok" : score.reward >= 0 ? "text-gold" : "text-stamp"}`}>{signed(score.reward)}</div>
                <div className="mt-2 font-mono text-[13px] text-mute">TP {score.tp} · FP {score.fp} · FN {score.fn} · лучшая серия {score.best}</div>
              </div>
              <div className="space-y-4">
                <div className="font-mono text-[12.5px] leading-relaxed text-soft">
                  F1 = 2·TP / (2·TP + FP + FN) = {score.f1.toFixed(3).replace(".", ",")}<br />
                  награда = clip(2·F1 − 1) = {signed(score.reward)} <span className="text-mute">(без платы за шаги)</span>
                </div>
                <table className="w-full max-w-[520px] text-[13px]">
                  <tbody>
                    <tr className="border-t border-line"><td className="py-2 text-soft">вы</td><td className="py-2 text-right font-mono">{signed(score.reward)}</td></tr>
                    {auditor && <tr className="border-t border-line"><td className="py-2 text-soft">скриптовый аудитор, тот же эпизод целиком</td><td className="py-2 text-right font-mono text-ok">{signed(auditor.python.return)}</td></tr>}
                    {flag && <tr className="border-t border-line"><td className="py-2 text-soft">«пометить всё»</td><td className="py-2 text-right font-mono text-stamp">{signed(flag.python.return)}</td></tr>}
                  </tbody>
                </table>
                <div className="flex flex-wrap gap-3">
                  <button className="btn-red" onClick={again}>Ещё раз, в другом порядке</button>
                  <a className="btn-ghost" href="#lab">К тренажёрам</a>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
