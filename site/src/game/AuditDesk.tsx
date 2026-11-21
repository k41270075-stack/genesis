// 3D stage of the game: our auditor at a desk with a conveyor of documents.
// He stamps an accused document red and drops it in the tray, or stamps a
// legitimate one blue and files it on the shelf; he cheers or shakes his head.
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

export type Act = "accuse" | "pass" | "timeout" | null;

interface Props {
  caseIndex: number;
  act: Act;
  right: boolean | null;
  left: number;
}

function paperTexture(seed: number): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 340;
  const g = c.getContext("2d")!;
  g.fillStyle = "#F4EFE3"; g.fillRect(0, 0, 256, 340);
  g.fillStyle = "#1A1712"; g.fillRect(20, 22, 120, 12);
  g.fillStyle = "#8a8170";
  for (let i = 0; i < 11; i++) {
    const w = 120 + ((seed * 37 + i * 53) % 100);
    g.fillRect(20, 60 + i * 22, w, 5);
  }
  g.strokeStyle = "#8a8170"; g.setLineDash([6, 5]); g.beginPath(); g.moveTo(20, 312); g.lineTo(236, 312); g.stroke();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function stampTexture(text: string, color: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 200;
  const g = c.getContext("2d")!;
  g.strokeStyle = color; g.fillStyle = color;
  g.lineWidth = 14; g.strokeRect(14, 14, 484, 172);
  g.lineWidth = 5; g.strokeRect(34, 34, 444, 132);
  g.font = "bold 92px 'PT Serif', Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 256, 104);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const ease = (x: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);

function Scene({ caseIndex, act, right, left }: Props) {
  const since = useRef(0);
  const lastAct = useRef<Act>(null);
  const lastCase = useRef(-1);
  const caseSince = useRef(0);
  const body = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const paper = useRef<THREE.Group>(null);
  const stamp = useRef<THREE.Mesh>(null);
  const flash = useRef<THREE.PointLight>(null);
  const belt = useRef<THREE.Group>(null);

  const paperTex = useMemo(() => paperTexture(caseIndex + 1), [caseIndex]);
  const redStamp = useMemo(() => stampTexture("ОШИБКА", "#E0301E"), []);
  const blueStamp = useMemo(() => stampTexture("ЗАКОННО", "#2F5BD8"), []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (lastCase.current !== caseIndex) { lastCase.current = caseIndex; caseSince.current = t; }
    if (lastAct.current !== act) { lastAct.current = act; since.current = t; }
    const s = act ? t - since.current : 0;
    const enter = ease((t - caseSince.current) / 0.6);
    const accused = act === "accuse";

    // the document: slides in from the conveyor, then goes to the tray or the shelf
    if (paper.current) {
      let x = -3.4 + 3.4 * enter, y = 1.02, z = 0.55, ry = 0;
      if (act) {
        const out = ease((s - 0.55) / 0.5);
        if (accused) { x += -2.6 * out; y -= 0.15 * out; z += 0.6 * out; ry = -0.5 * out; }
        else { x += 3.0 * out; y += 0.9 * out; z -= 0.8 * out; ry = 0.6 * out; }
      }
      paper.current.position.set(x, y, z);
      paper.current.rotation.set(-Math.PI / 2 + 0.25, 0, ry);
    }
    if (stamp.current) {
      const pop = act ? ease((s - 0.22) / 0.12) : 0;
      stamp.current.visible = pop > 0;
      stamp.current.scale.setScalar(0.4 + 0.6 * pop + (pop < 1 ? (1 - pop) * 1.2 : 0));
      (stamp.current.material as THREE.MeshBasicMaterial).map = accused ? redStamp : blueStamp;
    }
    // right arm: raise the stamp, slam on the paper (both verdicts are stamped)
    if (armR.current) {
      const up = act ? Math.sin(Math.min(1, s / 0.22) * Math.PI / 2) : 0;
      const down = act ? ease((s - 0.18) / 0.08) : 0;
      const back = act ? ease((s - 0.45) / 0.3) : 0;
      armR.current.rotation.x = -0.35 - 1.1 * up + 1.75 * down - 0.65 * back + Math.sin(t * 2) * 0.03;
    }
    // left arm: waves on a correct answer
    if (armL.current) {
      const wave = act && right ? Math.sin(s * 14) * 0.5 * Math.max(0, 1 - s / 1.4) : 0;
      armL.current.rotation.z = 0.25 + (act && right ? 0.9 * Math.min(1, s * 4) * Math.max(0, 1 - (s - 1) * 2) : 0) + wave;
    }
    // body: idle breathing, a jump when right, a slump when wrong
    if (body.current) {
      const jump = act && right ? Math.max(0, Math.sin(Math.min(1, (s - 0.4) / 0.4) * Math.PI)) * 0.35 : 0;
      const slump = act && right === false ? 0.12 * Math.min(1, (s - 0.4) * 3) : 0;
      body.current.position.y = Math.sin(t * 2) * 0.03 + jump - slump;
    }
    if (head.current) {
      const shake = act && right === false ? Math.sin(s * 22) * 0.35 * Math.max(0, 1 - (s - 0.4) / 0.9) * (s > 0.4 ? 1 : 0) : 0;
      head.current.rotation.y = shake + Math.sin(t * 0.8) * 0.06;
      head.current.rotation.x = act ? 0.25 * Math.min(1, s * 5) * Math.max(0, 1 - (s - 0.3) * 3) : 0.12;
    }
    if (mouth.current) mouth.current.rotation.z = act && right === false ? Math.PI : 0;
    if (flash.current) {
      const f = act ? Math.max(0, 1 - Math.abs(s - 0.3) * 4) : 0;
      flash.current.intensity = 26 * f;
      flash.current.color.set(right === false ? "#FF3B2E" : accused ? "#FF5A49" : "#6F95FF");
    }
    if (belt.current) belt.current.position.x = ((t * 0.6) % 0.5) - 0.25;
  });

  const queue = Math.max(0, Math.min(6, left));
  return (
    <>
      <color attach="background" args={["#0B0D13"]} />
      <fog attach="fog" args={["#0B0D13", 9, 18]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[-2, 3, 5]} intensity={1.1} color="#C9D6FF" />
      <spotLight position={[1.5, 6, 3.5]} angle={0.55} penumbra={0.6} intensity={90} color="#FFE2B8" castShadow />
      <pointLight ref={flash} position={[0, 2.2, 1.6]} intensity={0} distance={8} />

      {/* floor and back wall with shelves */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow><planeGeometry args={[30, 30]} /><meshStandardMaterial color="#10131B" /></mesh>
      {[0, 1, 2].map((i) => (
        <mesh key={i} position={[3.6, 1.2 + i * 0.9, -2.2]}><boxGeometry args={[2.4, 0.08, 0.6]} /><meshStandardMaterial color="#2A2018" /></mesh>
      ))}
      {Array.from({ length: 14 }, (_, i) => (
        <mesh key={i} position={[2.6 + (i % 7) * 0.32, 1.45 + Math.floor(i / 7) * 0.9, -2.2]}>
          <boxGeometry args={[0.22, 0.46, 0.5]} /><meshStandardMaterial color={i % 3 ? "#2B3B66" : "#6B2A22"} />
        </mesh>
      ))}

      {/* desk */}
      <mesh position={[0, 0.95, 0.45]} castShadow receiveShadow><boxGeometry args={[3.2, 0.12, 1.5]} /><meshStandardMaterial color="#4A3324" roughness={0.7} /></mesh>
      {[[-1.45, 0.45, 1.05], [1.45, 0.45, 1.05], [-1.45, 0.45, -0.15], [1.45, 0.45, -0.15]].map((p, i) => (
        <mesh key={i} position={p as [number, number, number]}><boxGeometry args={[0.1, 0.9, 0.1]} /><meshStandardMaterial color="#2E2016" /></mesh>
      ))}
      {/* red tray (accused) and the conveyor (incoming) */}
      <mesh position={[-2.6, 0.85, 1.1]}><boxGeometry args={[1.1, 0.25, 0.9]} /><meshStandardMaterial color="#7A1E16" /></mesh>
      <group position={[-3.6, 0.92, 0.55]}>
        <mesh><boxGeometry args={[2.2, 0.08, 0.8]} /><meshStandardMaterial color="#1A1D26" /></mesh>
        <group ref={belt}>
          {Array.from({ length: 6 }, (_, i) => (
            <mesh key={i} position={[-1 + i * 0.5, 0.045, 0]}><boxGeometry args={[0.05, 0.01, 0.78]} /><meshStandardMaterial color="#3A4256" /></mesh>
          ))}
        </group>
        {Array.from({ length: queue }, (_, i) => (
          <mesh key={i} position={[-0.6, 0.06 + i * 0.025, 0]} rotation={[-Math.PI / 2, 0, (i % 2 ? 0.06 : -0.05)]}>
            <planeGeometry args={[0.6, 0.8]} /><meshStandardMaterial color="#E8E2D2" side={THREE.DoubleSide} />
          </mesh>
        ))}
      </group>

      {/* the current document */}
      <group ref={paper}>
        <mesh castShadow><planeGeometry args={[0.9, 1.2]} /><meshStandardMaterial map={paperTex} side={THREE.DoubleSide} /></mesh>
        <mesh ref={stamp} position={[0, 0.05, 0.005]} rotation={[0, 0, -0.25]}>
          <planeGeometry args={[0.8, 0.31]} /><meshBasicMaterial transparent map={redStamp} depthWrite={false} />
        </mesh>
      </group>

      {/* the auditor */}
      <group ref={body} position={[0, 0, -0.75]}>
        <mesh position={[0, 1.25, 0]} castShadow><capsuleGeometry args={[0.5, 0.8, 8, 16]} /><meshStandardMaterial color="#22304F" /></mesh>
        <mesh position={[0, 1.62, 0.36]}><boxGeometry args={[0.18, 0.5, 0.05]} /><meshStandardMaterial color="#ECE6D8" /></mesh>
        <mesh position={[0, 1.55, 0.4]}><boxGeometry args={[0.08, 0.36, 0.03]} /><meshStandardMaterial color="#A8261D" /></mesh>
        <group ref={head} position={[0, 2.25, 0]}>
          <mesh castShadow><sphereGeometry args={[0.4, 32, 24]} /><meshStandardMaterial color="#E7B68F" roughness={0.8} /></mesh>
          {/* accountant's green eyeshade */}
          <mesh position={[0, 0.34, 0.02]} rotation={[0.35, 0, 0]}><cylinderGeometry args={[0.4, 0.44, 0.1, 32, 1, true]} /><meshStandardMaterial color="#1F8A4C" transparent opacity={0.85} side={THREE.DoubleSide} /></mesh>
          <mesh position={[0, 0.36, 0.3]} rotation={[0.5, 0, 0]}><cylinderGeometry args={[0.3, 0.3, 0.02, 32, 1, false, -Math.PI / 2, Math.PI]} /><meshStandardMaterial color="#1F8A4C" transparent opacity={0.8} side={THREE.DoubleSide} /></mesh>
          {/* round glasses */}
          {[-0.14, 0.14].map((x) => (
            <group key={x} position={[x, 0.02, 0.37]}>
              <mesh><torusGeometry args={[0.1, 0.018, 8, 24]} /><meshStandardMaterial color="#1A1712" metalness={0.4} /></mesh>
              <mesh position={[0, 0, -0.02]}><sphereGeometry args={[0.035, 12, 12]} /><meshStandardMaterial color="#111" /></mesh>
            </group>
          ))}
          <mesh position={[0, 0.02, 0.38]}><boxGeometry args={[0.08, 0.02, 0.02]} /><meshStandardMaterial color="#1A1712" /></mesh>
          <mesh ref={mouth} position={[0, -0.2, 0.36]}><torusGeometry args={[0.08, 0.016, 8, 16, Math.PI]} /><meshStandardMaterial color="#6B2A22" /></mesh>
          <mesh position={[0, -0.06, 0.4]}><sphereGeometry args={[0.05, 12, 12]} /><meshStandardMaterial color="#D9A07A" /></mesh>
        </group>
        {/* right arm with the rubber stamp */}
        <group ref={armR} position={[0.6, 1.7, 0]}>
          <mesh position={[0, -0.05, 0.38]} rotation={[Math.PI / 2, 0, 0]}><capsuleGeometry args={[0.11, 0.6, 6, 12]} /><meshStandardMaterial color="#22304F" /></mesh>
          <mesh position={[0, -0.05, 0.8]}><sphereGeometry args={[0.12, 16, 12]} /><meshStandardMaterial color="#E7B68F" /></mesh>
          <mesh position={[0, -0.2, 0.86]}><cylinderGeometry args={[0.05, 0.06, 0.22, 12]} /><meshStandardMaterial color="#5A3A26" /></mesh>
          <mesh position={[0, -0.34, 0.86]}><boxGeometry args={[0.28, 0.08, 0.2]} /><meshStandardMaterial color="#B0281C" /></mesh>
        </group>
        {/* left arm */}
        <group ref={armL} position={[-0.6, 1.7, 0]}>
          <mesh position={[-0.05, -0.38, 0.1]}><capsuleGeometry args={[0.11, 0.6, 6, 12]} /><meshStandardMaterial color="#22304F" /></mesh>
          <mesh position={[-0.08, -0.8, 0.14]}><sphereGeometry args={[0.12, 16, 12]} /><meshStandardMaterial color="#E7B68F" /></mesh>
        </group>
      </group>
    </>
  );
}

export default function AuditDesk(props: Props) {
  return (
    <Canvas shadows dpr={[1, 1.6]} camera={{ position: [0, 3.0, 4.7], fov: 42 }} onCreated={({ camera }) => camera.lookAt(0, 1.3, 0)}>
      <Scene {...props} />
    </Canvas>
  );
}
