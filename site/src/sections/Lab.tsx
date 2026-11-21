// The trainers: a grid of tiles; a tile opens its stage (picture + real terminal).
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { MODULES } from "../modules/registry";
import { ACCENT } from "../modules/types";
import { Stage } from "../ui/Stage";
import { session } from "../terminal";
import { usePassport } from "../game/passport";

const dur = (ms: number) => {
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1).replace(".", ",")} с`;
  return `${Math.floor(s / 60)} мин ${Math.round(s % 60)} с`;
};

export function Lab() {
  const got = usePassport();
  const [open, setOpen] = useState<number | null>(() => {
    const m = /^#m-([a-z]+)$/.exec(window.location.hash);
    const i = m ? MODULES.findIndex((x) => x.id === m[1]) : -1;
    return i >= 0 ? i : null;
  });
  const close = useCallback(() => { setOpen(null); history.replaceState(null, "", "#lab"); }, []);
  useEffect(() => { if (open !== null) history.replaceState(null, "", `#m-${MODULES[open]!.id}`); }, [open]);
  useEffect(() => {
    const on = () => {
      const m = /^#m-([a-z]+)$/.exec(window.location.hash);
      const i = m ? MODULES.findIndex((x) => x.id === m[1]) : -1;
      if (i >= 0) setOpen(i);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (open === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") setOpen((o) => (o === null ? o : (o + 1) % MODULES.length));
      if (e.key === "ArrowLeft") setOpen((o) => (o === null ? o : (o - 1 + MODULES.length) % MODULES.length));
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, close]);

  return (
    <section id="lab" className="relative mx-auto max-w-[1320px] px-5 py-28 sm:px-8">
      <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-end">
        <div>
          <p className="eyebrow"><span className="text-stamp">1010</span> — тренажёры</p>
          <h2 className="h-display mt-4 text-[clamp(34px,4.6vw,64px)]">Каждая команда<br />и её настоящий вывод</h2>
        </div>
        <p className="max-w-[520px] text-[16px] text-soft lg:justify-self-end">
          Слева в тренажёре — что происходит внутри, справа — запись терминала. Мы запустили каждую команду
          (<code className="kbd">python site/capture_terminal.py</code>) и сохранили каждую строку с моментом её появления.
          Время в таблице — сколько команда работала на самом деле.
        </p>
      </div>

      <div className="mt-12 border-t border-line2">
        <div className="hidden grid-cols-[48px_1.3fr_1.2fr_90px_70px_40px] gap-4 border-b border-line py-2.5 font-mono text-[11px] text-mute md:grid">
          <span>№</span><span>тренажёр</span><span>команда</span><span className="text-right">время</span><span className="text-right">выход</span><span />
        </div>
        {MODULES.map((m, i) => {
          const c = ACCENT[m.accent];
          const run = session(m.runs);
          return (
            <button key={m.id} onClick={() => setOpen(i)}
              className="group grid w-full grid-cols-[36px_1fr_auto] items-center gap-x-4 gap-y-1 border-b border-line py-4 text-left transition-colors hover:bg-white/[0.025] md:grid-cols-[48px_1.3fr_1.2fr_90px_70px_40px]">
              <span className="font-mono text-[13px]" style={{ color: c }}>{String(i + 1).padStart(2, "0")}</span>
              <span className="min-w-0">
                <span className="block font-display text-[19px] font-bold leading-snug">{m.title}{got[`m:${m.id}`] && <span className="ml-2 align-middle font-mono text-[10px] font-normal text-stamp" title="штамп в паспорте">◉</span>}</span>
                <span className="block text-[13px] text-mute">{m.tag}</span>
              </span>
              <span className="col-start-2 truncate font-mono text-[12.5px] text-soft md:col-start-auto">$ {m.cmd}</span>
              <span className="hidden text-right font-mono text-[12.5px] text-soft md:block">{run ? dur(run.ms) : "в браузере"}</span>
              <span className="hidden text-right font-mono text-[12.5px] md:block">{run ? <span className={run.exit ? "text-stamp" : "text-ok"}>exit {run.exit}</span> : <span className="text-gold">живой</span>}</span>
              <span className="row-span-2 row-start-1 text-right font-mono text-mute transition-transform group-hover:translate-x-1 group-hover:text-text md:row-auto md:row-start-auto" style={{ gridColumn: "-2 / -1" }}>→</span>
            </button>
          );
        })}
      </div>

      <AnimatePresence>
        {open !== null && (
          <motion.div className="fixed inset-0 z-50 bg-void/80 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={close} role="dialog" aria-modal="true" aria-label={MODULES[open]!.title}>
            <motion.div onClick={(e) => e.stopPropagation()}
              className="absolute inset-2 flex flex-col overflow-y-auto rounded-lg border border-line2 bg-void p-4 shadow-card sm:inset-4 sm:p-6 lg:overflow-hidden"
              initial={{ y: 40, scale: 0.97 }} animate={{ y: 0, scale: 1 }} exit={{ y: 30, opacity: 0 }} transition={{ type: "spring", stiffness: 260, damping: 28 }}>
              <div className="mb-3 flex items-center gap-2">
                <button className="kbd hover:text-text" onClick={() => setOpen((open - 1 + MODULES.length) % MODULES.length)}>← пред.</button>
                <button className="kbd hover:text-text" onClick={() => setOpen((open + 1) % MODULES.length)}>след. →</button>
                <button className="ml-auto grid h-9 w-9 place-items-center rounded border border-line2 hover:bg-white/5" onClick={close} aria-label="Закрыть">✕</button>
              </div>
              <div className="min-h-0 flex-1">
                <Stage key={MODULES[open]!.id} mod={MODULES[open]!} index={open} total={MODULES.length} />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
