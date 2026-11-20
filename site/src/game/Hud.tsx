// Top bar: where you are, total stars, sound and calm-mode switches.
import type { ReactNode } from "react";
import { LEVELS } from "./levels";
import { Sprite } from "./sprites";
import { useGame } from "./store";

export function Hud({ left, right }: { left?: ReactNode; right?: ReactNode }) {
  const { stars, soundOn, setSound, calm, setCalm } = useGame();
  const total = Object.values(stars).reduce((a, b) => a + b, 0);
  return (
    <header className="sticky top-0 z-40 flex flex-wrap items-center gap-2 bg-night/95 px-3 py-2 border-b-4 border-slate">
      <span className="font-arcade text-[14px] text-gold tracking-wider mr-1">VOUCHAI</span>
      <div className="flex flex-wrap items-center gap-2 mr-auto">{left}</div>
      {right}
      <span className="hud-chip flex items-center gap-1" title="Собрано звёзд">
        <Sprite name="star" scale={2} animate={false} /> {total}/{LEVELS.length * 3}
      </span>
      <button type="button" className="hud-chip" aria-pressed={soundOn} onClick={() => setSound(!soundOn)}>
        ЗВУК: {soundOn ? "ВКЛ" : "ВЫКЛ"}
      </button>
      <button type="button" className="hud-chip" aria-pressed={calm} onClick={() => setCalm(!calm)}
        title="Спокойная версия: без тряски, частиц и анимаций">
        {calm ? "СПОКОЙНО" : "ЭФФЕКТЫ"}
      </button>
    </header>
  );
}
