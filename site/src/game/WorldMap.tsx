// The world map: levels are stops on a path; the auditor walks between them.
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Hud } from "./Hud";
import { LEVELS } from "./levels";
import { play } from "./sound";
import { Sprite, Stars } from "./sprites";
import { useGame } from "./store";
import { PxButton } from "./ui";

const WIDE: [number, number][] = [[10, 18], [35, 14], [60, 20], [86, 16], [84, 50], [60, 46], [36, 52], [12, 48], [22, 82], [50, 86], [80, 80]];
const NARROW: [number, number][] = LEVELS.map((_, i) => [i % 2 ? 72 : 28, 5 + i * (90 / (LEVELS.length - 1))]);

function useWide(): boolean {
  const q = "(min-width: 768px)";
  const [wide, setWide] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const f = () => setWide(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return wide;
}

export function WorldMap({ selected, onSelect, onEnter }: { selected: number; onSelect: (i: number) => void; onEnter: (i: number) => void }) {
  const { stars, calm } = useGame();
  const wide = useWide();
  const pos = wide ? WIDE : NARROW;
  const [px, py] = pos[selected] ?? [50, 50];
  const lvl = LEVELS[selected]!;
  const [tilt, setTilt] = useState<[number, number]>([0, 0]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); play("step"); onSelect(Math.min(LEVELS.length - 1, selected + 1)); }
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); play("step"); onSelect(Math.max(0, selected - 1)); }
      if (e.key === "Enter") { e.preventDefault(); onEnter(selected); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, onSelect, onEnter]);

  const firstUnplayed = LEVELS.findIndex((l) => !(stars[l.id] ?? 0));

  return (
    <div className="min-h-screen flex flex-col">
      <Hud left={<span className="hud-chip">КАРТА</span>} />
      <main className="relative flex-1 overflow-hidden"
        onPointerMove={(e) => { if (!calm) setTilt([(e.clientX / window.innerWidth - 0.5) * 2, (e.clientY / window.innerHeight - 0.5) * 2]); }}>
        <div className="stars stars--far" style={{ transform: `translate(${tilt[0] * -6}px, ${tilt[1] * -6}px)` }} aria-hidden="true" />
        <div className="stars" style={{ transform: `translate(${tilt[0] * -14}px, ${tilt[1] * -14}px)` }} aria-hidden="true" />

        <div className="relative mx-auto w-full max-w-6xl px-4 pt-4 pb-56 md:pb-48">
          <h1 className="font-arcade text-gold text-sm sm:text-base">КАРТА РЕВИЗИИ</h1>
          <p className="text-fog mt-1">Уровни — это функции VouchAI. Иди по порядку или выбирай любой: каждый занимает 30–60 секунд, любой можно пропустить.</p>

          <div className="relative mt-4" style={{ height: wide ? 560 : LEVELS.length * 112 }}>
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polyline points={pos.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" stroke="#4B4475" strokeWidth="10"
                vectorEffect="non-scaling-stroke" strokeLinejoin="miter" />
              <polyline points={pos.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" stroke="#9A93C0" strokeWidth="3"
                vectorEffect="non-scaling-stroke" className={calm ? "" : "march"} strokeDasharray="8 6" />
            </svg>

            {LEVELS.map((l, i) => {
              const [x, y] = pos[i]!;
              const s = stars[l.id] ?? 0;
              const active = i === selected;
              return (
                <button key={l.id} type="button"
                  className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1 group ${active ? "z-20" : "z-10"}`}
                  style={{ left: `${x}%`, top: `${y}%` }}
                  onClick={() => { if (active) onEnter(i); else { play("step"); onSelect(i); } }}
                  onDoubleClick={() => onEnter(i)}
                  aria-label={`Уровень ${i + 1}: ${l.title}. ${l.covers}. Звёзд: ${s}`}
                  aria-current={active ? "step" : undefined}>
                  <span className={`grid place-items-center w-16 h-16 sm:w-20 sm:h-20 ${active ? "bg-gold" : s ? "bg-leaf" : i === firstUnplayed ? "bg-carbon" : "bg-slate"} shadow-px group-hover:brightness-110`}>
                    <span className={`grid place-items-center w-12 h-12 sm:w-16 sm:h-16 bg-deep ${active && !calm ? "bob" : ""}`}>
                      <Sprite name={l.icon} scale={l.icon === "boss" ? 2 : l.icon === "star" || l.icon === "coin" ? 4 : 3} animate={active} />
                    </span>
                  </span>
                  <span className="font-arcade text-[14px] sm:text-[14px] bg-night/80 px-1.5 py-0.5 whitespace-nowrap">
                    {String(i + 1).padStart(2, "0")} {l.title.toUpperCase()}
                  </span>
                  <Stars n={s} scale={2} />
                </button>
              );
            })}

            <motion.div className="absolute z-30 pointer-events-none -translate-x-1/2"
              animate={{ left: `${px}%`, top: `calc(${py}% - 92px)` }}
              transition={calm ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 16 }}
              aria-hidden="true">
              <Sprite name="hero" scale={4} />
            </motion.div>
          </div>
        </div>

        <aside className="fixed inset-x-0 bottom-0 z-40 bg-night/95 border-t-4 border-slate px-4 py-3">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2">
            <div className="flex-1 min-w-[240px]">
              <div className="font-arcade text-[14px] text-gold">УРОВЕНЬ {selected + 1}: {lvl.title.toUpperCase()}</div>
              <div className="text-paper">{lvl.goal}</div>
              <div className="text-fog text-sm">Функция проекта: {lvl.covers}</div>
            </div>
            <div className="flex gap-3">
              <PxButton tone="ghost" onClick={() => onSelect(Math.max(0, selected - 1))} aria-label="Предыдущий уровень">◀</PxButton>
              <PxButton onClick={() => onEnter(selected)} sfx="coin">ВОЙТИ</PxButton>
              <PxButton tone="ghost" onClick={() => onSelect(Math.min(LEVELS.length - 1, selected + 1))} aria-label="Следующий уровень">▶</PxButton>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
