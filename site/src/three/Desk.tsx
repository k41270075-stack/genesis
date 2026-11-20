// Title scene: the auditor's desk — ledgers, receipts, a stamp that keeps stamping.
import { Float } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type * as THREE from "three";
import { palette } from "../../tailwind.config";
import { PixelCanvas, Toon } from "./PixelCanvas";

function Book({ position, color, rot = 0 }: { position: [number, number, number]; color: string; rot?: number }) {
  return (
    <group position={position} rotation={[0, rot, 0]}>
      <mesh><boxGeometry args={[1.5, 0.32, 1.1]} /><Toon color={color} /></mesh>
      <mesh position={[0.06, 0, 0]}><boxGeometry args={[1.42, 0.24, 1.12]} /><Toon color={palette.paper} /></mesh>
    </group>
  );
}

function Receipt({ position, rot }: { position: [number, number, number]; rot: number }) {
  return (
    <Float speed={2} rotationIntensity={0.6} floatIntensity={0.8}>
      <group position={position} rotation={[-0.5, rot, 0.1]}>
        <mesh><boxGeometry args={[0.55, 0.02, 1.0]} /><Toon color={palette.white} /></mesh>
        {[0.3, 0.15, 0, -0.15].map((z) => (
          <mesh key={z} position={[-0.04, 0.012, z]}><boxGeometry args={[0.36, 0.005, 0.04]} /><Toon color={palette.night} /></mesh>
        ))}
        <mesh position={[0, 0.012, -0.36]}><boxGeometry args={[0.4, 0.005, 0.12]} /><Toon color={palette.stamp} /></mesh>
      </group>
    </Float>
  );
}

function Stamp() {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() % 2.2;
    const y = t < 0.25 ? 0.25 + (1 - t / 0.25) * 1.1 : t < 0.4 ? 0.25 : 0.25 + Math.min(1.1, (t - 0.4) * 1.4);
    if (ref.current) ref.current.position.y = y;
  });
  return (
    <group ref={ref} position={[1.25, 1, 0.55]}>
      <mesh position={[0, 0, 0]}><cylinderGeometry args={[0.32, 0.32, 0.14, 12]} /><Toon color={palette.stamp} /></mesh>
      <mesh position={[0, 0.28, 0]}><cylinderGeometry args={[0.1, 0.14, 0.45, 8]} /><Toon color={palette.wood} /></mesh>
      <mesh position={[0, 0.58, 0]}><sphereGeometry args={[0.2, 8, 6]} /><Toon color={palette.wood} /></mesh>
    </group>
  );
}

function Scene() {
  const g = useRef<THREE.Group>(null);
  useFrame((_, dt) => { if (g.current) g.current.rotation.y += dt * 0.18; });
  return (
    <group ref={g} position={[0, -0.9, 0]}>
      <mesh position={[0, -0.18, 0]}><boxGeometry args={[5.2, 0.3, 3.2]} /><Toon color={palette.wood} /></mesh>
      {([[-2.4, -1.4], [2.4, -1.4], [-2.4, 1.4], [2.4, 1.4]] as const).map(([x, z]) => (
        <mesh key={`${x}${z}`} position={[x, -1.2, z]}><boxGeometry args={[0.25, 1.9, 0.25]} /><Toon color={palette.wood} /></mesh>
      ))}
      <Book position={[-1.2, 0.13, -0.3]} color={palette.carbon} rot={0.2} />
      <Book position={[-1.15, 0.45, -0.28]} color={palette.leaf} rot={0.05} />
      <Book position={[-1.25, 0.77, -0.32]} color={palette.stamp} rot={-0.15} />
      <mesh position={[1.1, 0.0, 0.5]} rotation={[0, 0.3, 0]}><boxGeometry args={[1.6, 0.04, 1.1]} /><Toon color={palette.paper} /></mesh>
      <Stamp />
      <Receipt position={[0.2, 1.6, -0.6]} rot={0.4} />
      <Receipt position={[-0.4, 2.2, 0.6]} rot={-0.6} />
      <Receipt position={[1.6, 2.0, -0.4]} rot={1.2} />
      {([[0.3, 0.6], [0.5, 0.2], [-0.2, 0.9]] as const).map(([x, z], i) => (
        <mesh key={i} position={[x, 0.05 + i * 0.07, z]}><cylinderGeometry args={[0.18, 0.18, 0.06, 10]} /><Toon color={palette.gold} /></mesh>
      ))}
    </group>
  );
}

export default function Desk({ className = "" }: { className?: string }) {
  return (
    <PixelCanvas className={className} camera={[0, 2.6, 6.2]} pixel={4} label="Пиксельный стол ревизора: книги, квитанции и штамп">
      <Scene />
    </PixelCanvas>
  );
}
