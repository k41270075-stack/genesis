// The passport button, the stamp book and the stamp toast.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { hash01 } from "../engine/clock";
import { onStamp, rankOf, resetPassport, stamps, usePassport, type StampDef } from "./passport";

function RoundStamp({ def, on, i, size = 104 }: { def: StampDef; on: boolean; i: number; size?: number }) {
  const rot = (hash01(i * 13 + 5) - 0.5) * 24;
  return (
    <div className="grid place-items-center" style={{ width: size, height: size }} title={on ? def.title : `Как получить: ${def.hint}`}>
      <div className="grid h-full w-full place-items-center rounded-full p-2 text-center"
        style={on
          ? { border: "3px double #FF4D3D", color: "#FF4D3D", transform: `rotate(${rot}deg)`, background: "rgba(255,77,61,.06)" }
          : { border: "1.5px dashed #2A3145", color: "#4b5468" }}>
        <div>
          <div className="font-mono text-[8.5px] uppercase tracking-[0.12em] opacity-80">{on ? "проверено" : String(i + 1).padStart(2, "0")}</div>
          <div className="mt-0.5 font-display text-[11.5px] font-bold leading-tight">{def.title}</div>
        </div>
      </div>
    </div>
  );
}

export function PassportButton({ onOpen }: { onOpen: () => void }) {
  const got = usePassport();
  const n = Object.keys(got).length;
  return (
    <button onClick={onOpen} className="flex items-center gap-2 rounded border border-line2 px-3 py-2 text-[13px] hover:bg-white/5"
      aria-label={`Паспорт ревизора: ${n} из ${stamps().length} штампов`}>
      <svg width="14" height="16" viewBox="0 0 14 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="1" y="1" width="12" height="14" rx="1.5" /><circle cx="7" cy="7" r="2.6" /><path d="M4 12h6" /></svg>
      <span className="tabnum font-mono">{n}/{stamps().length}</span>
    </button>
  );
}

export function PassportDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const got = usePassport();
  const list = stamps();
  const n = list.filter((s) => got[s.id]).length;
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] bg-void/70 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.aside onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Паспорт ревизора"
            className="absolute bottom-0 right-0 top-0 w-full max-w-[560px] overflow-y-auto border-l border-line2 bg-[#0d0f15] p-6 sm:p-8"
            initial={{ x: 80, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 80, opacity: 0 }} transition={{ type: "spring", stiffness: 280, damping: 30 }}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="eyebrow">паспорт ревизора · хранится только в этом браузере</div>
                <h3 className="h-display mt-2 text-[34px]">{rankOf(n)}</h3>
                <div className="mt-1 font-mono text-[13px] text-mute">{n} из {list.length} штампов</div>
              </div>
              <button className="kbd hover:text-text" onClick={onClose}>✕</button>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded bg-line"><div className="h-full bg-stamp transition-all" style={{ width: `${(n / list.length) * 100}%` }} /></div>
            <div className="mt-8 grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4">
              {list.map((s, i) => (
                <div key={s.id} className="flex flex-col items-center">
                  <RoundStamp def={s} on={!!got[s.id]} i={i} />
                  {!got[s.id] && <div className="mt-1.5 text-center text-[10.5px] leading-tight text-mute">{s.hint}</div>}
                </div>
              ))}
            </div>
            <button className="mt-10 text-[12px] text-mute underline-offset-4 hover:underline" onClick={resetPassport}>начать паспорт заново</button>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function StampToasts() {
  const [items, setItems] = useState<{ key: number; def: StampDef }[]>([]);
  const got = usePassport();
  const n = Object.keys(got).length;
  useEffect(() => onStamp((def) => {
    const key = Date.now() + Math.random();
    setItems((x) => [...x, { key, def }]);
    setTimeout(() => setItems((x) => x.filter((y) => y.key !== key)), 3600);
  }), []);
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[80] flex flex-col gap-3" aria-live="polite">
      <AnimatePresence>
        {items.map(({ key, def }) => (
          <motion.div key={key} className="flex items-center gap-4 rounded border border-stamp/40 bg-[#14100f] px-4 py-3 shadow-card"
            initial={{ x: 60, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 60, opacity: 0 }}>
            <motion.div initial={{ scale: 2.6, rotate: -30, opacity: 0 }} animate={{ scale: 1, rotate: -10, opacity: 1 }}
              transition={{ delay: 0.15, duration: 0.18, ease: [0.5, 0, 0.75, 0] }}
              className="grid h-12 w-12 place-items-center rounded-full font-mono text-[9px] font-bold uppercase text-stamp" style={{ border: "3px double #FF4D3D" }}>
              штамп
            </motion.div>
            <div>
              <div className="text-[13px] font-semibold text-text">{def.title}</div>
              <div className="font-mono text-[11px] text-mute">паспорт: {n}/{stamps().length} · {rankOf(n)}</div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
