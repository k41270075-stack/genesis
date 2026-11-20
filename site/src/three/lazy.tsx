// 3D scenes load lazily (own chunks) and only where they can run smoothly;
// calm mode, no WebGL or a weak device get the 2D fallback.
import { Component, lazy, Suspense, type ReactNode } from "react";
import { useGame } from "../game/store";

export const Desk = lazy(() => import("./Desk"));
export const Coin3D = lazy(() => import("./Coin3D"));
export const Wall3D = lazy(() => import("./Wall3D"));
export const Chest3D = lazy(() => import("./Chest3D"));

let webgl: boolean | null = null;
function hasWebGL(): boolean {
  if (webgl === null) {
    try {
      const c = document.createElement("canvas");
      webgl = Boolean(c.getContext("webgl2") ?? c.getContext("webgl"));
    } catch { webgl = false; }
  }
  return webgl;
}

export function use3D(): boolean {
  const { calm } = useGame();
  const weak = typeof navigator !== "undefined" && (navigator.hardwareConcurrency ?? 4) <= 2;
  return !calm && !weak && hasWebGL();
}

class Guard extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

/** Render `scene` when 3D is fine, otherwise (or while loading / on error) the 2D `fallback`. */
export function Scene3D({ scene, fallback }: { scene: ReactNode; fallback: ReactNode }) {
  const ok = use3D();
  if (!ok) return <>{fallback}</>;
  return (
    <Guard fallback={fallback}>
      <Suspense fallback={fallback}>{scene}</Suspense>
    </Guard>
  );
}
