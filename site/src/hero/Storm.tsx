// The opening shot: a tunnel of ledger rows rushing at warp speed, braking,
// then blown outwards by the impact of the stamp (IMPACT seconds after mount).
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { hash01 } from "../engine/clock";

export const IMPACT = 2.35;
const N = 3200;
const NEAR = 12, FAR = -150;

const COLORS = {
  dim: new THREE.Color("#2B3A63"),
  dim2: new THREE.Color("#1B2440"),
  red: new THREE.Color("#FF4D3D").multiplyScalar(1.6),
  blue: new THREE.Color("#5B8CFF").multiplyScalar(1.4),
  ok: new THREE.Color("#3DDC97").multiplyScalar(1.2),
  white: new THREE.Color("#ECEAE4"),
};

interface Row { a: number; r: number; z: number; len: number; spin: number; kind: number }

function Tunnel({ reduced }: { reduced: boolean }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const flash = useRef<THREE.MeshBasicMaterial>(null);
  const group = useRef<THREE.Group>(null);
  const { pointer, camera } = useThree();
  const start = useRef<number | null>(null);
  const tmp = useMemo(() => new THREE.Object3D(), []);

  const rows = useMemo<Row[]>(() => Array.from({ length: N }, (_, i) => {
    const k = hash01(i * 7 + 1);
    const kind = k < 0.035 ? 1 : k < 0.08 ? 2 : k < 0.095 ? 3 : k < 0.15 ? 4 : 0;
    return {
      a: hash01(i * 3 + 2) * Math.PI * 2,
      r: 4.2 + Math.pow(hash01(i * 5 + 3), 0.7) * 9,
      z: FAR + hash01(i * 11 + 4) * (NEAR - FAR),
      len: 0.4 + hash01(i * 13 + 5) * 2.2,
      spin: (hash01(i * 17 + 6) - 0.5) * 0.4,
      kind,
    };
  }), []);

  const setColors = (m: THREE.InstancedMesh | null) => {
    (mesh as React.MutableRefObject<THREE.InstancedMesh | null>).current = m;
    if (!m) return;
    rows.forEach((row, i) => {
      const c = row.kind === 1 ? COLORS.red : row.kind === 2 ? COLORS.blue : row.kind === 3 ? COLORS.ok
        : row.kind === 4 ? COLORS.white : (i % 2 ? COLORS.dim : COLORS.dim2);
      m.setColorAt(i, c);
    });
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  };

  useFrame((state, dt) => {
    const m = mesh.current;
    if (!m) return;
    if (start.current === null) start.current = state.clock.elapsedTime;
    const t = reduced ? 10 : state.clock.elapsedTime - start.current;
    const d = Math.min(dt, 1 / 20);
    // speed: warp, braking towards the impact, then a slow drift
    const warp = t < IMPACT ? 140 * Math.pow(1 - t / IMPACT, 2) + 4 : 4;
    const since = t - IMPACT;
    const blast = since > 0 ? Math.exp(-since * 2.2) : 0;
    const stretch = 1 + warp * 0.09;
    rows.forEach((row, i) => {
      row.z += warp * d;
      if (row.z > NEAR) row.z -= NEAR - FAR;
      const r = row.r + blast * 9 * (0.4 + hash01(i));
      const a = row.a + t * 0.02 + row.spin * blast;
      tmp.position.set(Math.cos(a) * r, Math.sin(a) * r, row.z);
      tmp.rotation.set(0, 0, a + Math.PI / 2);
      tmp.scale.set(row.len, 1, stretch);
      tmp.updateMatrix();
      m.setMatrixAt(i, tmp.matrix);
    });
    m.instanceMatrix.needsUpdate = true;

    if (ring.current) {
      const s = since > 0 ? 1 + since * 26 : 0.001;
      ring.current.scale.setScalar(s);
      (ring.current.material as THREE.MeshBasicMaterial).opacity = since > 0 ? Math.max(0, 0.9 - since * 0.75) : 0;
    }
    if (flash.current) flash.current.opacity = since > 0 ? Math.max(0, 0.5 - since * 1.6) : 0;
    if (group.current) {
      group.current.rotation.x += (pointer.y * 0.12 - group.current.rotation.x) * 0.04;
      group.current.rotation.y += (-pointer.x * 0.16 - group.current.rotation.y) * 0.04;
      group.current.rotation.z = t * 0.03;
    }
    const shake = since > 0 && since < 0.6 ? (1 - since / 0.6) * 0.35 : 0;
    camera.position.x = (Math.random() - 0.5) * shake;
    camera.position.y = (Math.random() - 0.5) * shake;
  });

  return (
    <group ref={group}>
      <instancedMesh ref={setColors} args={[undefined, undefined, N]} frustumCulled={false}>
        <boxGeometry args={[1, 0.045, 0.08]} />
        <meshBasicMaterial vertexColors={false} toneMapped={false} transparent opacity={0.95}
          blending={THREE.AdditiveBlending} depthWrite={false} />
      </instancedMesh>
      <mesh ref={ring} position={[0, 0, -6]}>
        <ringGeometry args={[0.96, 1, 128]} />
        <meshBasicMaterial color="#FF4D3D" toneMapped={false} transparent opacity={0} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh position={[0, 0, 4]}>
        <planeGeometry args={[60, 60]} />
        <meshBasicMaterial ref={flash} color="#FFD9C9" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

export default function Storm({ reduced = false }: { reduced?: boolean }) {
  return (
    <Canvas dpr={[1, 1.6]} gl={{ antialias: true, powerPreference: "high-performance" }}
      camera={{ fov: 62, position: [0, 0, 8], near: 0.1, far: 220 }}>
      <color attach="background" args={["#05060A"]} />
      <fog attach="fog" args={["#05060A", 18, 120]} />
      <Tunnel reduced={reduced} />
    </Canvas>
  );
}
