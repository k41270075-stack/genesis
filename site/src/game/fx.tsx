// Particles (confetti for TP, pixel explosions for FP), screen shake and flash.
// One canvas over the whole screen; the loop runs only while particles live.
import { useEffect, useRef } from "react";
import { palette } from "../../tailwind.config";

interface P { x: number; y: number; vx: number; vy: number; life: number; max: number; size: number; color: string; spin: boolean }

let particles: P[] = [];
let wake: (() => void) | null = null;
let calm = false;
let stage: HTMLElement | null = null;

const CONFETTI = [palette.gold, palette.leaf, palette.lime, palette.sky, palette.carbon, palette.paper, palette.amber];
const FIRE = [palette.ember, palette.stamp, palette.gold, palette.amber, palette.paper];

function center(): [number, number] { return [window.innerWidth / 2, window.innerHeight / 3]; }
function at(el?: Element | null): [number, number] {
  if (!el) return center();
  const r = el.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2];
}

export const fx = {
  setCalm(v: boolean) { calm = v; if (v) particles = []; },
  setStage(el: HTMLElement | null) { stage = el; },
  confetti(target?: Element | null, n = 90) {
    if (calm) return;
    const [x, y] = at(target);
    for (let i = 0; i < n; i++) {
      particles.push({ x, y, vx: (Math.random() - 0.5) * 9, vy: -Math.random() * 11 - 3, life: 0, max: 70 + Math.random() * 50,
        size: 4 + Math.floor(Math.random() * 3) * 2, color: CONFETTI[i % CONFETTI.length]!, spin: true });
    }
    wake?.();
  },
  burst(target?: Element | null, color?: string, n = 60) {
    if (calm) return;
    const [x, y] = at(target);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, s = 2 + Math.random() * 7;
      particles.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 1, life: 0, max: 30 + Math.random() * 30,
        size: 4 + Math.floor(Math.random() * 2) * 4, color: color ?? FIRE[i % FIRE.length]!, spin: false });
    }
    wake?.();
  },
  sparkle(target?: Element | null, n = 24) {
    if (calm) return;
    const [x, y] = at(target);
    for (let i = 0; i < n; i++) {
      particles.push({ x: x + (Math.random() - 0.5) * 80, y: y + (Math.random() - 0.5) * 40, vx: 0, vy: -0.6 - Math.random(),
        life: 0, max: 40 + Math.random() * 30, size: 4, color: i % 2 ? palette.gold : palette.white, spin: false });
    }
    wake?.();
  },
  shake() {
    if (calm || !stage) return;
    stage.classList.remove("shake");
    void stage.offsetWidth;
    stage.classList.add("shake");
  },
  flash(color: string = palette.white) {
    if (calm) return;
    const el = document.createElement("div");
    el.className = "flash";
    el.style.background = color;
    document.body.appendChild(el);
    window.setTimeout(() => el.remove(), 400);
  },
};

export function FxLayer() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const g = canvas.getContext("2d");
    if (!g) return;
    let raf = 0, running = false;
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);
    const tick = () => {
      g.clearRect(0, 0, canvas.width, canvas.height);
      particles = particles.filter((p) => p.life < p.max && p.y < canvas.height + 40);
      for (const p of particles) {
        p.life++;
        p.x += p.vx; p.y += p.vy;
        p.vy += p.spin ? 0.28 : 0.18;
        p.vx *= p.spin ? 0.985 : 0.95;
        const fade = 1 - p.life / p.max;
        g.globalAlpha = Math.max(0, Math.min(1, fade * 1.6));
        g.fillStyle = p.color;
        const w = p.spin && p.life % 8 < 4 ? p.size / 2 : p.size;
        g.fillRect(Math.round(p.x / 2) * 2, Math.round(p.y / 2) * 2, w, p.size);
      }
      g.globalAlpha = 1;
      if (particles.length) raf = requestAnimationFrame(tick);
      else running = false;
    };
    wake = () => { if (!running) { running = true; raf = requestAnimationFrame(tick); } };
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); wake = null; };
  }, []);
  return <canvas ref={ref} className="pointer-events-none fixed inset-0 z-50" aria-hidden="true" />;
}
