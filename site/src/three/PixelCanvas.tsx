// Pixel-art 3D: render three.js at 1/N resolution and scale it up with
// image-rendering: pixelated; toon materials with three tones posterize it.
import { Canvas } from "@react-three/fiber";
import { useMemo, type ReactNode } from "react";
import * as THREE from "three";

export function PixelCanvas({ children, pixel = 4, camera = [0, 3, 7], fov = 40, className = "", label }: {
  children: ReactNode; pixel?: number; camera?: [number, number, number]; fov?: number; className?: string; label: string;
}) {
  return (
    <div className={`relative ${className}`} role="img" aria-label={label}>
      <Canvas
        dpr={1 / pixel}
        flat
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        camera={{ position: camera, fov }}
        onCreated={({ gl }) => { gl.domElement.style.imageRendering = "pixelated"; }}
        style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden", imageRendering: "pixelated" }}
      >
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 6, 5]} intensity={1.6} />
        <directionalLight position={[-5, 2, -3]} intensity={0.4} color="#8FB2FF" />
        {children}
      </Canvas>
    </div>
  );
}

let ramp: THREE.DataTexture | null = null;
/** 3-step light ramp for MeshToonMaterial (posterized, pixel-friendly shading). */
export function toonRamp(): THREE.DataTexture {
  if (!ramp) {
    ramp = new THREE.DataTexture(new Uint8Array([70, 70, 70, 255, 160, 160, 160, 255, 255, 255, 255, 255]), 3, 1, THREE.RGBAFormat);
    ramp.minFilter = THREE.NearestFilter;
    ramp.magFilter = THREE.NearestFilter;
    ramp.needsUpdate = true;
  }
  return ramp;
}

export function Toon({ color }: { color: string }) {
  const map = useMemo(() => toonRamp(), []);
  return <meshToonMaterial color={color} gradientMap={map} />;
}
