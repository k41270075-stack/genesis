// The coin of the leak audit: a fair coin (AUC 0.5) flips on demand.
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type * as THREE from "three";
import { palette } from "../../tailwind.config";
import { PixelCanvas, Toon } from "./PixelCanvas";

function Coin({ flips }: { flips: number }) {
  const ref = useRef<THREE.Group>(null);
  const start = useRef<{ at: number; n: number } | null>(null);
  useFrame(({ clock }) => {
    const g = ref.current;
    if (!g) return;
    const now = clock.getElapsedTime();
    if (!start.current || start.current.n !== flips) start.current = { at: now, n: flips };
    const t = Math.min(1, (now - start.current.at) / 1.4);
    const flying = flips > 0 && t < 1;
    g.position.y = flying ? Math.sin(t * Math.PI) * 1.8 : Math.sin(now * 2) * 0.06;
    g.rotation.x = flying ? Math.PI / 2 + t * Math.PI * 8 : Math.PI / 2 + Math.sin(now) * 0.15;
    g.rotation.z += 0.01;
  });
  return (
    <group ref={ref} rotation={[Math.PI / 2, 0, 0]}>
      <mesh><cylinderGeometry args={[1, 1, 0.16, 20]} /><Toon color={palette.gold} /></mesh>
      <mesh position={[0, 0.085, 0]}><cylinderGeometry args={[0.78, 0.78, 0.02, 20]} /><Toon color={palette.amber} /></mesh>
      <mesh position={[0, -0.085, 0]}><cylinderGeometry args={[0.78, 0.78, 0.02, 20]} /><Toon color={palette.amber} /></mesh>
      <mesh position={[0, 0.1, 0]}><boxGeometry args={[0.18, 0.02, 0.9]} /><Toon color={palette.gold} /></mesh>
      <mesh position={[0, 0.1, -0.3]}><boxGeometry args={[0.7, 0.02, 0.16]} /><Toon color={palette.gold} /></mesh>
      <mesh position={[0, 0.1, -0.05]}><boxGeometry args={[0.7, 0.02, 0.16]} /><Toon color={palette.gold} /></mesh>
    </group>
  );
}

export default function Coin3D({ flips, className = "" }: { flips: number; className?: string }) {
  return (
    <PixelCanvas className={className} camera={[0, 0.6, 4.2]} pixel={5} label="Монета аудита утечек">
      <Coin flips={flips} />
    </PixelCanvas>
  );
}
