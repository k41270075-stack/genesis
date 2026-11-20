// Level 8 «Стена»: zone A (policy) and zone B (generator, truth, grader) talk only
// through stdio. Requests pass; the truth does not. Closed mode pays 0 per step.
import { motion } from "framer-motion";
import { useMemo, useRef, useState } from "react";
import { meta, readme } from "../data";
import { fx } from "../game/fx";
import type { LevelProps } from "../game/levels";
import { play } from "../game/sound";
import { Sprite } from "../game/sprites";
import { useGame } from "../game/store";
import { Cmd, Loading, PxButton, Say, Stamp } from "../game/ui";
import { tablesOf } from "../lib/episode";
import { Sandbox } from "../lib/sandbox";
import { Scene3D, Wall3D } from "../three/lazy";
import type { Packet } from "../three/Wall3D";
import { useKit } from "./kit";

export default function L08Wall({ finish }: LevelProps) {
  const kit = useKit();
  const { calm } = useGame();
  const [packet, setPacket] = useState<Packet>("none");
  const [nonce, setNonce] = useState(0);
  const [done, setDone] = useState<Set<Packet>>(new Set());
  const [reply, setReply] = useState<string | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const sandbox = useMemo(() => (kit ? new Sandbox(kit.ep.episode_id, tablesOf(kit.ep)) : null), [kit]);
  if (!kit || !sandbox) return <Loading />;
  const [uidB, uidA] = [readme.uids?.[0] ?? "—", readme.uids?.[1] ?? "—"];
  const ja = meta.judge_adapter;

  const send = (p: Packet) => {
    setPacket(p);
    setNonce((n) => n + 1);
    setDone((d) => new Set(d).add(p));
    if (p === "list") {
      sandbox.reset();
      const r = sandbox.step({ action: "list_records", table: "ledger", cursor: null, limit: 50 });
      const rows = (r.result?.rows as unknown[] | undefined)?.length ?? 0;
      setReply(`→ {"name": "list_records", "args": {"table": "ledger", "limit": 50}}\n← {"records": [${rows} строк открытой книги], "next_cursor": "…", "remaining_steps": ${r.remaining_steps}}`);
      play("blip");
    } else if (p === "submit") {
      setReply(`→ {"name": "submit", "args": {"findings": {...}}}\n← {"accepted": true}; reward = 0 — в закрытом режиме награда на каждом шаге 0,\n   итоги (TP/FP/FN, F1, return) остаются у оценщика в зоне B`);
      play("coin");
    } else {
      setReply(`→ open("/proc/<pid зоны B>/environ"), open("private/truth.json")\n← PermissionError: зона B работает под uid ${uidB}, политика — под uid ${uidA}`);
      window.setTimeout(() => { play("hit"); fx.shake(); fx.burst(stage.current, "#D9473A", 50); fx.flash("#D9473A"); }, calm ? 0 : 500);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div ref={stage} className="px-panel p-0 relative overflow-hidden">
        <div className="h-72 sm:h-80">
          <Scene3D scene={<Wall3D packet={packet} nonce={nonce} className="h-full w-full" />}
            fallback={
              <div className="h-full grid grid-cols-[1fr_auto_1fr] items-end gap-2 p-4 bg-deep">
                <div className="flex flex-col items-center gap-2"><Sprite name="hero" scale={5} /><span className="label">зона A</span></div>
                <div className="flex flex-col items-center"><Sprite name="shield" scale={6} /><span className="label">stdio</span></div>
                <div className="flex flex-col items-center gap-2"><Sprite name="chest" scale={4} animate={false} /><span className="label">зона B</span></div>
              </div>
            } />
        </div>
        <div className="absolute left-3 top-3 hud-chip">ЗОНА A · ПОЛИТИКА · uid {uidA}</div>
        <div className="absolute right-3 top-3 hud-chip">ЗОНА B · СРЕДА + ЭТАЛОН + ОЦЕНЩИК · uid {uidB}</div>
        {packet === "spy" && <div className="absolute inset-x-0 bottom-6 grid place-items-center"><Stamp key={nonce} text="ОТКАЗАНО" big /></div>}
      </div>

      <div className="flex flex-wrap gap-3">
        <PxButton tone="green" onClick={() => send("list")}>ОТПРАВИТЬ list_records</PxButton>
        <PxButton onClick={() => send("submit")}>ОТПРАВИТЬ submit</PxButton>
        <PxButton tone="red" onClick={() => send("spy")} sfx="step">ПРОЛЕЗТЬ К ЭТАЛОНУ</PxButton>
      </div>

      {reply && (
        <motion.pre key={nonce} initial={calm ? false : { opacity: 0 }} animate={{ opacity: 1 }}
          className="term p-3 whitespace-pre-wrap break-words">{reply}</motion.pre>
      )}

      <Say who="Как устроено">
        Генератор, эталон и оценщик живут в дочернем процессе (зона B); политика говорит с ней только JSON-строками по stdio.
        Это граница по процессам. Граница по правам ОС — отдельные пользователи uid {uidB} и uid {uidA} — включается в контейнере, запущенном от root
        (так проверяет CI); вне контейнера честно остаётся только граница процессов.
        {ja && <> Адаптер жюри <span className="font-mono">{ja.file ?? "judge_adapter.py"}</span>: {ja.functions.join(", ")}{ja.uses_process_env ? " — среда для жюри поднимается через ProcessEnv, то есть тоже за стеной." : "."}</>}
      </Say>
      {readme.isolation_command && <div><div className="label mb-1">изолированный прогон со шпионом</div><Cmd>{readme.isolation_command}</Cmd></div>}

      {done.size >= 3 && (
        <PxButton onClick={() => finish({
          stars: 3,
          lines: [
            { label: "list_records", value: "прошёл по stdio", tone: "good" },
            { label: "submit", value: "принят, награда шага 0", tone: "good" },
            { label: "Эталон", value: "недоступен", tone: "good" },
            { label: "uid зон", value: `${uidA} / ${uidB}` },
          ],
          note: "Простое сокрытие полей в Python-объекте изоляцией не считается — поэтому отдельный процесс.",
        })}>ДАЛЕЕ</PxButton>
      )}
      {done.size < 3 && <p className="text-fog text-sm">Попробуй все три запроса ({done.size}/3).</p>}
    </div>
  );
}
