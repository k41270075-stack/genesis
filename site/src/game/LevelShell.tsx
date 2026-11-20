// A level on screen: HUD (map, skip), the level itself, then the score board.
import { AnimatePresence, motion } from "framer-motion";
import { Component, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { fx } from "./fx";
import { Hud } from "./Hud";
import { LEVELS, type LevelResult } from "./levels";
import { play } from "./sound";
import { Sprite, Stars } from "./sprites";
import { useGame } from "./store";
import { Loading, PxButton } from "./ui";

class LevelGuard extends Component<{ children: ReactNode; onMap: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="px-panel p-6 flex flex-col items-start gap-4">
        <p className="font-arcade text-[14px] text-ember">УРОВЕНЬ НЕ ЗАГРУЗИЛСЯ</p>
        <p>Попробуйте обновить страницу или выбрать другой уровень.</p>
        <PxButton onClick={this.props.onMap}>НА КАРТУ</PxButton>
      </div>
    );
  }
}

export function LevelShell({ index, onMap, onNext }: { index: number; onMap: () => void; onNext: () => void }) {
  const lvl = LEVELS[index]!;
  const { award, calm } = useGame();
  const [result, setResult] = useState<LevelResult | null>(null);
  const [run, setRun] = useState(0);
  const board = useRef<HTMLDivElement>(null);

  const finish = useCallback((r: LevelResult) => {
    award(lvl.id, r.stars);
    setResult(r);
  }, [award, lvl.id]);

  useEffect(() => {
    if (!result) return;
    play(result.stars >= 2 ? "win" : "lose");
    window.setTimeout(() => (result.stars >= 2 ? fx.confetti(board.current, 120) : fx.burst(board.current)), 200);
  }, [result]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onMap(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onMap]);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [index]);

  const { Comp } = lvl;
  const last = index === LEVELS.length - 1;
  return (
    <div className="min-h-screen flex flex-col">
      <Hud
        left={<>
          <button type="button" className="hud-chip" onClick={onMap}>◀ КАРТА</button>
          <span className="hud-chip text-gold">{String(index + 1).padStart(2, "0")} · {lvl.title.toUpperCase()}</span>
        </>}
        right={!result && (
          <button type="button" className="hud-chip" onClick={() => { play("blip"); onNext(); }}
            title="Пропустить уровень (без звёзд)">ПРОПУСТИТЬ ▶</button>
        )}
      />
      <motion.main key={`${index}-${run}`} className="flex-1 mx-auto w-full max-w-6xl px-3 sm:px-5 py-5"
        initial={calm ? false : { clipPath: "inset(0 100% 0 0)" }} animate={{ clipPath: "inset(0 0% 0 0)" }}
        transition={{ duration: 0.45, ease: [0.7, 0, 0.3, 1] }}>
        <div className="mb-4">
          <h1 className="font-arcade text-gold text-base sm:text-xl">{lvl.title.toUpperCase()}</h1>
          <p className="text-fog">{lvl.goal} <span className="text-dusk">·</span> <span className="text-sky">{lvl.covers}</span></p>
        </div>
        <LevelGuard onMap={onMap}>
          <Suspense fallback={<Loading />}>
            <Comp finish={finish} />
          </Suspense>
        </LevelGuard>
      </motion.main>

      <AnimatePresence>
        {result && (
          <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-labelledby="board-title"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div ref={board} className="px-panel w-full max-w-lg p-6 text-center"
              initial={calm ? false : { scale: 0.6, y: 40 }} animate={{ scale: 1, y: 0 }} transition={{ type: "spring", stiffness: 260, damping: 16 }}>
              <div className="flex justify-center mb-2"><Sprite name={result.stars >= 2 ? "hero" : "boss"} scale={4} /></div>
              <h2 id="board-title" className="font-arcade text-sm text-gold">УРОВЕНЬ {index + 1} ПРОЙДЕН</h2>
              <div className="my-4 flex justify-center"><Stars n={result.stars} scale={5} /></div>
              <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-left font-mono text-[14px]">
                {result.lines.map((l) => (
                  <div key={l.label} className="contents">
                    <dt className="text-fog">{l.label}</dt>
                    <dd className={`text-right ${l.tone === "good" ? "text-lime" : l.tone === "bad" ? "text-ember" : "text-paper"}`}>{l.value}</dd>
                  </div>
                ))}
              </dl>
              {result.note && <p className="mt-3 text-sm text-fog">{result.note}</p>}
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <PxButton tone="ghost" onClick={() => { setResult(null); setRun((r) => r + 1); }}>ЕЩЁ РАЗ</PxButton>
                <PxButton tone="ghost" onClick={onMap}>КАРТА</PxButton>
                {!last && <PxButton autoFocus onClick={onNext} sfx="coin">ДАЛЕЕ ▶</PxButton>}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
