// The prediction chest: sealed, then opened — coins of light rise out of it.
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type * as THREE from "three";
import { palette } from "../../tailwind.config";
import { PixelCanvas, Toon } from "./PixelCanvas";

function Chest({ open }: { open: boolean }) {
  const lid = useRef<THREE.Group>(null);
  const root = useRef<THREE.Group>(null);
  const sparks = useRef<THREE.Group>(null);
  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime();
    if (lid.current) {
      const target = open ? -1.9 : 0;
      lid.current.rotation.x += (target - lid.current.rotation.x) * Math.min(1, dt * 5);
    }
    if (root.current) root.current.rotation.y = Math.sin(t * 0.6) * 0.35 + 0.5;
    if (sparks.current) {
      sparks.current.visible = open;
      sparks.current.children.forEach((c, i) => {
        const p = ((t * 0.6 + i * 0.13) % 1);
        c.position.set(Math.sin(i * 2.1) * 0.6 * (1 - p), 0.5 + p * 2.2, Math.cos(i * 1.7) * 0.4 * (1 - p));
      });
    }
  });
  return (
    <group ref={root} position={[0, -0.8, 0]}>
      <mesh position={[0, 0.4, 0]}><boxGeometry args={[2, 0.8, 1.2]} /><Toon color={palette.wood} /></mesh>
      <mesh position={[0, 0.4, 0.61]}><boxGeometry args={[2.04, 0.12, 0.02]} /><Toon color={palette.gold} /></mesh>
      <mesh position={[0, 0.5, 0.62]}><boxGeometry args={[0.3, 0.36, 0.06]} /><Toon color={palette.gold} /></mesh>
      <group ref={lid} position={[0, 0.8, -0.6]}>
        <mesh position={[0, 0.2, 0.6]}><boxGeometry args={[2.04, 0.4, 1.24]} /><Toon color={palette.wood} /></mesh>
        <mesh position={[0, 0.41, 0.6]}><boxGeometry args={[2.06, 0.04, 0.2]} /><Toon color={palette.gold} /></mesh>
      </group>
      <group ref={sparks}>
        {Array.from({ length: 12 }, (_, i) => (
          <mesh key={i}><boxGeometry args={[0.12, 0.12, 0.12]} /><Toon color={i % 2 ? palette.gold : palette.white} /></mesh>
        ))}
      </group>
    </group>
  );
}

export default function Chest3D({ open, className = "" }: { open: boolean; className?: string }) {
  return (
    <PixelCanvas className={className} camera={[0, 1.4, 4.6]} pixel={4} label={open ? "Сундук открыт" : "Запечатанный сундук-предсказание"}>
      <Chest open={open} />
    </PixelCanvas>
  );
}
