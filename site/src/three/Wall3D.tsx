// The wall between zone A (policy) and zone B (environment + grader).
import { useFrame } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { palette } from "../../tailwind.config";
import { PixelCanvas, Toon, toonRamp } from "./PixelCanvas";

export type Packet = "none" | "list" | "submit" | "spy";

function Bricks() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const bricks = useMemo(() => {
    const out: [number, number][] = [];
    for (let row = 0; row < 9; row++) for (let col = 0; col < 7; col++) {
      if (row === 3 && (col === 3)) continue; // the stdio pipe passes here
      out.push([col * 0.62 - 1.86 + (row % 2 ? 0.31 : 0), row * 0.32 + 0.16]);
    }
    return out;
  }, []);
  const mat = useMemo(() => new THREE.MeshToonMaterial({ color: palette.stamp, gradientMap: toonRamp() }), []);
  const geo = useMemo(() => new THREE.BoxGeometry(0.58, 0.28, 0.5), []);
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    bricks.forEach(([across, up], i) => { m.makeTranslation(0, up, across); ref.current?.setMatrixAt(i, m); });
    if (ref.current) ref.current.instanceMatrix.needsUpdate = true;
  }, [bricks]);
  return <instancedMesh ref={ref} args={[geo, mat, bricks.length]} />;
}

function Mover({ packet, nonce }: { packet: Packet; nonce: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const start = useRef({ at: -1, n: -1 });
  useFrame(({ clock }) => {
    const m = ref.current;
    if (!m) return;
    const now = clock.getElapsedTime();
    if (start.current.n !== nonce) start.current = { at: now, n: nonce };
    const t = Math.min(1, (now - start.current.at) / 1.6);
    m.visible = packet !== "none" && t < 1;
    if (packet === "spy") {
      // runs at the wall and bounces back
      const x = t < 0.5 ? -2.4 + t * 4.2 : -0.3 - (t - 0.5) * 4.2;
      m.position.set(x, 0.6, -1.2);
    } else {
      // through the pipe and back: x from -2.4 to 2.4 and home again
      const x = t < 0.5 ? -2.4 + t * 9.6 : 2.4 - (t - 0.5) * 9.6;
      m.position.set(x, 1.12, 0);
    }
    m.rotation.y += 0.1;
  });
  const color = packet === "spy" ? palette.ember : packet === "submit" ? palette.gold : palette.lime;
  return <mesh ref={ref}><boxGeometry args={[0.32, 0.32, 0.32]} /><Toon color={color} /></mesh>;
}

function Scene({ packet, nonce }: { packet: Packet; nonce: number }) {
  const g = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (g.current) g.current.rotation.y = -0.5 + Math.sin(clock.getElapsedTime() * 0.3) * 0.18; });
  return (
    <group ref={g} position={[0, -1.2, 0]}>
      <mesh position={[-2.2, -0.05, 0]}><boxGeometry args={[4, 0.1, 4]} /><Toon color={palette.slate} /></mesh>
      <mesh position={[2.2, -0.05, 0]}><boxGeometry args={[4, 0.1, 4]} /><Toon color={palette.deep} /></mesh>
      <Bricks />
      <mesh position={[0, 1.12, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.24, 0.24, 1.4, 10, 1, true]} /><Toon color={palette.sky} /></mesh>
      {/* zone A: the agent */}
      <mesh position={[-2.6, 0.5, -0.6]}><boxGeometry args={[0.6, 1, 0.6]} /><Toon color={palette.carbon} /></mesh>
      <mesh position={[-2.6, 1.2, -0.6]}><boxGeometry args={[0.45, 0.4, 0.45]} /><Toon color="#E9B98F" /></mesh>
      {/* zone B: sandbox, truth chest, grader */}
      <mesh position={[2.0, 0.35, -1.0]}><boxGeometry args={[0.9, 0.7, 0.9]} /><Toon color={palette.leaf} /></mesh>
      <mesh position={[2.8, 0.3, 0.9]}><boxGeometry args={[0.9, 0.6, 0.6]} /><Toon color={palette.wood} /></mesh>
      <mesh position={[2.8, 0.66, 0.9]}><boxGeometry args={[0.92, 0.14, 0.62]} /><Toon color={palette.gold} /></mesh>
      <mesh position={[1.6, 0.5, 1.2]}><cylinderGeometry args={[0.35, 0.35, 1, 8]} /><Toon color={palette.paper} /></mesh>
      <Mover packet={packet} nonce={nonce} />
    </group>
  );
}

export default function Wall3D({ packet, nonce, className = "" }: { packet: Packet; nonce: number; className?: string }) {
  return (
    <PixelCanvas className={className} camera={[0, 2.8, 7.5]} pixel={4} label="Стена между зоной A (политика) и зоной B (среда и оценщик)">
      <Scene packet={packet} nonce={nonce} />
    </PixelCanvas>
  );
}
