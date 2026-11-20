// Level 10 «Сундук»: the prediction sealed in the README — seed → the same world
// on any machine. Then determinism of the demo episode and the replay command.
import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { readme, readmeCommand } from "../data";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Cmd, Loading, PxButton, Say } from "../game/ui";
import { asWritten } from "../lib/format";
import { Chest3D, Scene3D } from "../three/lazy";
import { useKit } from "./kit";

export default function L10Chest({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [open, setOpen] = useState(false);
  const [guess, setGuess] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const pred = readme.prediction;
  if (!kit) return <Loading />;
  if (!pred?.sha256) return <Say>В README нет раздела с предсказанием.</Say>;
  const tail = pred.sha256.slice(-6);
  const replay = readmeCommand("replay");
  const matched = guess.trim().toLowerCase() === tail;

  const unlock = () => {
    setOpen(true);
    play("win"); fx.flash("#F4C64E"); fx.confetti(box.current, 140); fx.shake();
  };

  return (
    <div ref={box} className="flex flex-col gap-5">
      <div className="grid gap-4 md:grid-cols-[360px_minmax(0,1fr)] items-center">
        <div className="h-64 px-panel">
          <Scene3D scene={<Chest3D open={open} className="h-full w-full" />}
            fallback={<div className="h-full grid place-items-center"><Sprite name="chest" scale={10} animate={false} /></div>} />
        </div>
        <Say who="Печать">
          Запечатано заранее в README: seed <b>{pred.seed}</b>, конфиг <b>{pred.config}</b>{pred.version ? `, версия ${pred.version}` : ""}. На любой машине генератор строит один и тот же мир —
          до байта. На замке — последние 6 знаков sha256 открытых таблиц: <span className="font-arcade text-gold">…{tail}</span>.
          Введи их (или просто вскрой) — и сверим.
          <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); unlock(); }}>
            <input className="px-input w-40 font-arcade text-[14px]" value={guess} onChange={(e) => setGuess(e.target.value)} placeholder="??????" aria-label="Последние 6 знаков хеша" maxLength={6} />
            <PxButton type="submit" disabled={open}>ВСКРЫТЬ</PxButton>
          </form>
        </Say>
      </div>

      {open && (
        <motion.div initial={calm ? false : { opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="px-panel p-4 flex flex-col gap-3">
          <div className="font-arcade text-[14px] text-gold">ВНУТРИ</div>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 font-mono text-[14px]">
            <dt className="text-fog">episode_id</dt><dd>{pred.episode_id}</dd>
            <dt className="text-fog">sha256</dt><dd className="break-all">{pred.sha256.slice(0, -6)}<mark className="bg-gold text-night">{tail}</mark></dd>
            {pred.rewards.map((r) => <div key={r.policy} className="contents"><dt className="text-fog">{r.policy}</dt><dd>{asWritten(r.reward)}</dd></div>)}
          </dl>
          {guess && <p className={matched ? "text-lime" : "text-ember"}>{matched ? "Твой код совпал с печатью." : `Ты ввёл «${guess}», на печати «${tail}».`}</p>}
          <div className="label">воспроизвести на своей машине</div>
          {pred.commands.map((c) => <Cmd key={c}>{c}</Cmd>)}
          {pred.hash_command && <Cmd>{pred.hash_command}</Cmd>}
          <Say who="Ещё детерминизм">
            Демо-эпизод этой игры {kit.ep.episode_id}: sha256 открытых таблиц <span className="font-mono break-all">{kit.ep.tables_sha256}</span> ({kit.ep.sha256_recipe}).
            Траектории всех базовых политик записаны и проигрываются заново шаг в шаг.
          </Say>
          {replay && <Cmd>{replay}</Cmd>}
          <PxButton onClick={() => finish({
            stars: matched ? 3 : 2,
            lines: [
              { label: "Эпизод", value: pred.episode_id ?? "—" },
              { label: "Хеш", value: `…${tail}`, tone: "good" },
              { label: "Код с замка", value: matched ? "совпал" : guess ? "не совпал" : "не вводили", tone: matched ? "good" : "info" },
            ],
            note: matched ? "Предсказание сбылось: seed → тот же мир на любой машине." : "Третья звезда — за верный код с замка.",
          })}>ДАЛЕЕ</PxButton>
        </motion.div>
      )}
    </div>
  );
}
