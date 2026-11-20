import { useCallback, useEffect, useRef, useState } from "react";
import { fx, FxLayer } from "./game/fx";
import { LevelShell } from "./game/LevelShell";
import { LEVELS } from "./game/levels";
import { useGame } from "./game/store";
import { Title } from "./game/Title";
import { WorldMap } from "./game/WorldMap";

type Scene = { kind: "title" } | { kind: "map" } | { kind: "level"; index: number };

function sceneFromHash(): Scene {
  const m = /^#(\d+)$/.exec(window.location.hash);
  if (m) {
    const i = Number(m[1]) - 1;
    if (i >= 0 && i < LEVELS.length) return { kind: "level", index: i };
  }
  if (window.location.hash === "#map") return { kind: "map" };
  return { kind: "title" };
}

export default function App() {
  const { calm } = useGame();
  const [scene, setScene] = useState<Scene>(sceneFromHash);
  const [selected, setSelected] = useState(() => {
    const s = sceneFromHash();
    return s.kind === "level" ? s.index : 0;
  });
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => { fx.setStage(stage.current); }, []);
  useEffect(() => {
    const onHash = () => {
      const s = sceneFromHash();
      setScene(s);
      if (s.kind === "level") setSelected(s.index);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    const hash = scene.kind === "level" ? `#${scene.index + 1}` : scene.kind === "map" ? "#map" : "";
    if (window.location.hash !== hash) window.history.replaceState(null, "", hash || window.location.pathname);
  }, [scene]);

  const toMap = useCallback(() => setScene({ kind: "map" }), []);
  const enter = useCallback((i: number) => { setSelected(i); setScene({ kind: "level", index: i }); }, []);
  const next = useCallback(() => {
    setScene((s) => {
      if (s.kind !== "level") return s;
      const n = s.index + 1;
      if (n >= LEVELS.length) return { kind: "map" };
      setSelected(n);
      return { kind: "level", index: n };
    });
  }, []);

  return (
    <div ref={stage} className={calm ? "" : "crt"}>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[70] px-btn">К содержимому</a>
      <div id="main-content">
        {scene.kind === "title" && <Title onPlay={toMap} />}
        {scene.kind === "map" && <WorldMap selected={selected} onSelect={setSelected} onEnter={enter} />}
        {scene.kind === "level" && <LevelShell key={scene.index} index={scene.index} onMap={toMap} onNext={next} />}
      </div>
      <FxLayer />
    </div>
  );
}
