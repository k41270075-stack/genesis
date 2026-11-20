// INSERT COIN → one button «ИГРАТЬ».
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { readme } from "../data";
import { Desk, Scene3D } from "../three/lazy";
import { fx } from "./fx";
import { play } from "./sound";
import { Sprite } from "./sprites";
import { useGame } from "./store";

export function Title({ onPlay }: { onPlay: () => void }) {
  const { calm } = useGame();
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const [inserting, setInserting] = useState(false);

  useEffect(() => {
    let live = true;
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
    const id = window.setInterval(() => setProgress((p) => Math.min(p + 9, 92)), 60);
    void (fonts?.ready ?? Promise.resolve()).then(() => {
      if (!live) return;
      window.clearInterval(id);
      setProgress(100);
      window.setTimeout(() => live && setReady(true), calm ? 0 : 250);
    });
    return () => { live = false; window.clearInterval(id); };
  }, [calm]);

  const start = () => {
    if (!ready || inserting) return;
    setInserting(true);
    play("coin");
    fx.flash();
    fx.confetti(null, 60);
    window.setTimeout(onPlay, calm ? 0 : 650);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); start(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <main className="relative min-h-screen overflow-hidden flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="stars stars--far" aria-hidden="true" />
      <div className="stars" aria-hidden="true" />
      <div className="absolute inset-x-0 top-[6vh] h-[46vh] max-h-[460px] opacity-90">
        <Scene3D scene={<Desk className="h-full w-full" />}
          fallback={<div className="flex h-full items-end justify-center gap-6 pb-6" aria-hidden="true">
            <Sprite name="receipt" scale={6} /><Sprite name="hero" scale={8} /><Sprite name="coin" scale={6} />
          </div>} />
      </div>

      <div className="relative z-10 mt-[30vh] sm:mt-[34vh]">
        <motion.h1 initial={calm ? false : { y: -40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 200, damping: 12 }}
          className="font-arcade text-gold text-3xl sm:text-5xl md:text-6xl tracking-wider [text-shadow:4px_4px_0_#000,8px_8px_0_#D9473A]">
          VOUCHAI
        </motion.h1>
        <p className="font-arcade text-paper text-sm sm:text-lg mt-4 tracking-widest">РЕВИЗОР</p>
        <p className="mt-3 text-fog text-lg">{readme.slogan ?? ""}</p>
        <p className="mt-1 text-paper/90 max-w-xl mx-auto text-[17px]">
          Игра по настоящей RL-среде для ИИ-аудиторов: вывод засчитывается, только если к нему приложены квитанции — записи книг, которые его доказывают.
        </p>

        {!ready ? (
          <div className="mt-8 mx-auto w-64" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Загрузка">
            <div className="font-arcade text-[14px] text-fog mb-2">ЗАГРУЗКА</div>
            <div className="h-4 bg-black p-[3px]"><div className="h-full bg-leaf" style={{ width: `${progress}%` }} /></div>
          </div>
        ) : (
          <div className="mt-8 flex flex-col items-center gap-4">
            <p className="font-arcade text-[14px] text-gold blink" aria-hidden="true">INSERT COIN</p>
            <motion.button type="button" onClick={start} autoFocus
              whileHover={calm ? undefined : { scale: 1.06 }} whileTap={{ scale: 0.94 }}
              className="px-btn text-sm sm:text-base px-10 py-5">
              ИГРАТЬ
            </motion.button>
            <p className="text-fog text-sm">мышь, тач или клавиатура · Enter — играть</p>
          </div>
        )}
      </div>
    </main>
  );
}
