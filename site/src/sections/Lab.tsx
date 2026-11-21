// The trainers: a grid of tiles; a tile opens its stage (picture + real terminal).
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { MODULES } from "../modules/registry";
import { ACCENT } from "../modules/types";
import { Stage } from "../ui/Stage";

function Glyph({ i, color }: { i: number; color: string }) {
  // a tiny animated signature per tile (CSS only)
  const bars = [0, 1, 2, 3, 4, 5, 6];
  return (
    <div className="flex h-8 items-end gap-[3px]">
      {bars.map((b) => (
        <span key={b} className="w-[5px] rounded-sm opacity-70 group-hover:opacity-100"
          style={{ background: color, height: `${20 + ((i * 37 + b * 23) % 70)}%`, animation: `float-y ${1.6 + ((b + i) % 4) * 0.35}s ease-in-out ${b * 0.12}s infinite` }} />
      ))}
    </div>
  );
}

export function Lab() {
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
          <p className="eyebrow">тренажёры</p>
          <h2 className="h-display mt-4 text-[clamp(34px,4.6vw,68px)]">Всё, что запускается<br />в терминале — <span className="text-stamp">видно глазами</span></h2>
        </div>
        <p className="max-w-[520px] text-[16px] text-soft lg:justify-self-end">
          {MODULES.length} команд проекта. Слева — что происходит внутри, справа — настоящий вывод терминала, записанный
          командой <code className="kbd">python site/capture_terminal.py</code>. Два тренажёра интерактивные: можно самому стать агентом
          и самому попробовать обмануть оценщика.
        </p>
      </div>

      <div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {MODULES.map((m, i) => {
          const c = ACCENT[m.accent];
          return (
            <motion.button key={m.id} onClick={() => setOpen(i)}
              initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: (i % 4) * 0.06, duration: 0.5 }}
              className="group relative overflow-hidden rounded-2xl border border-line bg-ink p-5 text-left transition hover:-translate-y-1 hover:border-line2">
              <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full opacity-0 blur-3xl transition-opacity duration-500 group-hover:opacity-30" style={{ background: c }} />
              <div className="flex items-start justify-between">
                <span className="font-mono text-[12px] text-mute">{String(i + 1).padStart(2, "0")}</span>
                {m.interactive && <span className="chip border-gold/40 text-gold">интерактив</span>}
              </div>
              <div className="mt-6"><Glyph i={i} color={c} /></div>
              <h3 className="mt-5 text-[19px] font-bold leading-tight">{m.title}</h3>
              <p className="mt-1.5 text-[13px] text-mute">{m.tag}</p>
              <div className="mt-5 flex items-center justify-between border-t border-line pt-3 font-mono text-[11.5px]">
                <span className="truncate text-soft">$ {m.cmd}</span>
                <span className="ml-2 shrink-0 transition-transform group-hover:translate-x-1" style={{ color: c }}>▶</span>
              </div>
            </motion.button>
          );
        })}
      </div>

      <AnimatePresence>
        {open !== null && (
          <motion.div className="fixed inset-0 z-50 bg-void/80 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={close} role="dialog" aria-modal="true" aria-label={MODULES[open]!.title}>
            <motion.div onClick={(e) => e.stopPropagation()}
              className="absolute inset-2 flex flex-col overflow-y-auto rounded-3xl border border-line2 bg-void p-4 shadow-card sm:inset-4 sm:p-6 lg:overflow-hidden"
              initial={{ y: 40, scale: 0.97 }} animate={{ y: 0, scale: 1 }} exit={{ y: 30, opacity: 0 }} transition={{ type: "spring", stiffness: 260, damping: 28 }}>
              <div className="mb-3 flex items-center gap-2">
                <button className="kbd hover:text-text" onClick={() => setOpen((open - 1 + MODULES.length) % MODULES.length)}>← пред.</button>
                <button className="kbd hover:text-text" onClick={() => setOpen((open + 1) % MODULES.length)}>след. →</button>
                <button className="ml-auto grid h-9 w-9 place-items-center rounded-full border border-line2 hover:bg-white/5" onClick={close} aria-label="Закрыть">✕</button>
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
