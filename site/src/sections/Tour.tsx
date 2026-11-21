// The 60-second tour: an intro card, six trainers on autoplay (picture left, real
// terminal right), an outro. `#video` hides the controls for screen recording.
import { motion } from "framer-motion";
import { useEffect } from "react";
import { readme } from "../data";
import { easeOut, seg, usePlayback } from "../engine/clock";
import { MODULES, TOUR } from "../modules/registry";
import { Stage } from "../ui/Stage";
import { REPO, SITE } from "./links";

const INTRO = 3000, OUTRO = 3500;

export function Tour({ onClose, video = false }: { onClose: () => void; video?: boolean }) {
  const total = INTRO + TOUR.reduce((s, x) => s + x.ms, 0) + OUTRO;
  const pb = usePlayback(total, true);
  const t = pb.t;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); if (e.key === " ") { e.preventDefault(); if (pb.playing) pb.pause(); else pb.play(); } };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose, pb]);

  let acc = INTRO, cur = -1, local = 0;
  TOUR.forEach((x, i) => { if (t >= acc && t < acc + x.ms) { cur = i; local = (t - acc) / x.ms; } acc += x.ms; });
  const outro = t >= acc;
  const mod = cur >= 0 ? MODULES.find((m) => m.id === TOUR[cur]!.id)! : null;
  const idx = mod ? MODULES.indexOf(mod) : 0;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-void">
      {t < INTRO && (
        <div className="grid flex-1 place-items-center px-6 text-center">
          <div>
            <motion.div className="eyebrow" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>60 секунд · 6 команд · слева картинка, справа настоящий терминал</motion.div>
            <div className="h-display mt-6 text-[clamp(56px,9vw,150px)]" style={{ transform: `scale(${1 + seg(t, 0, INTRO) * 0.06})` }}>
              Vouch<span className="text-stamp">AI</span>
            </div>
            <div className="mt-4 font-mono text-[18px] text-soft" style={{ opacity: seg(t, 600, 1200) }}>{readme.slogan}</div>
          </div>
        </div>
      )}
      {mod && (
        <div className="min-h-0 flex-1 p-5 sm:p-8" style={{ opacity: Math.min(1, local * 12, (1 - local) * 14) }}>
          <Stage key={mod.id} mod={mod} index={idx} total={MODULES.length} auto pOverride={Math.min(1, local * 1.04)} />
        </div>
      )}
      {outro && (
        <div className="grid flex-1 place-items-center px-6 text-center">
          <div style={{ opacity: easeOut(seg(t, acc, acc + 500)) }}>
            <div className="h-display text-[clamp(40px,6vw,96px)]">Every claim needs<br /><span className="text-stamp">a receipt.</span></div>
            <div className="mt-8 flex flex-wrap justify-center gap-6 font-mono text-[18px] text-soft">
              <span>{REPO.replace("https://", "")}</span><span>{SITE.replace("https://", "")}</span>
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center gap-3 border-t border-line px-5 py-3 sm:px-8">
        <span className="font-display text-[14px] font-semibold">Vouch<span className="text-stamp">AI</span></span>
        <div className="flex flex-1 gap-1">
          {TOUR.map((x, i) => {
            const m = MODULES.find((mm) => mm.id === x.id)!;
            const fill = i < cur || outro ? 1 : i === cur ? local : 0;
            return (
              <div key={x.id} className="flex-1">
                <div className="h-1 overflow-hidden rounded-full bg-line"><div className="h-full bg-stamp" style={{ width: `${fill * 100}%` }} /></div>
                <div className={`mt-1 hidden truncate text-[10px] md:block ${i === cur ? "text-text" : "text-mute"}`}>{m.title}</div>
              </div>
            );
          })}
        </div>
        {!video && (
          <>
            <button className="kbd hover:text-text" onClick={pb.playing ? pb.pause : pb.play}>{pb.playing ? "пауза" : "дальше"}</button>
            <button className="kbd hover:text-text" onClick={onClose}>✕ закрыть</button>
          </>
        )}
      </div>
    </div>
  );
}
