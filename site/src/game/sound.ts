// 8-bit sound effects synthesized with WebAudio. Off by default; one switch.
type Note = [freq: number, dur: number];

let ctx: AudioContext | null = null;
let enabled = false;
const listeners = new Set<(on: boolean) => void>();

try { enabled = localStorage.getItem("vouchai-sound") === "on"; } catch { /* storage off */ }

export const sound = {
  get on() { return enabled; },
  set(on: boolean) {
    enabled = on;
    try { localStorage.setItem("vouchai-sound", on ? "on" : "off"); } catch { /* storage off */ }
    if (on) ensure();
    listeners.forEach((f) => f(on));
    if (on) play("coin");
  },
  subscribe(f: (on: boolean) => void) { listeners.add(f); return () => { listeners.delete(f); }; },
};

function ensure(): AudioContext | null {
  if (!ctx) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
  }
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

function tones(notes: Note[], type: OscillatorType = "square", gain = 0.06) {
  const a = ensure();
  if (!a) return;
  let t = a.currentTime;
  for (const [f, d] of notes) {
    const o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f, t);
    g.gain.setValueAtTime(gain, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + d);
    o.connect(g).connect(a.destination);
    o.start(t);
    o.stop(t + d);
    t += d * 0.9;
  }
}

function noise(dur: number, gain = 0.12) {
  const a = ensure();
  if (!a) return;
  const len = Math.floor(a.sampleRate * dur);
  const buf = a.createBuffer(1, len, a.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
  const src = a.createBufferSource(), g = a.createGain();
  src.buffer = buf;
  g.gain.value = gain;
  src.connect(g).connect(a.destination);
  src.start();
}

export type Sfx = "blip" | "coin" | "hit" | "boom" | "win" | "lose" | "stamp" | "type" | "step" | "laugh";

export function play(s: Sfx) {
  if (!enabled) return;
  switch (s) {
    case "blip": return tones([[660, 0.05]], "square", 0.04);
    case "type": return tones([[1200, 0.02]], "square", 0.015);
    case "step": return tones([[220, 0.04]], "triangle", 0.05);
    case "coin": return tones([[988, 0.07], [1319, 0.18]]);
    case "hit": noise(0.12, 0.1); return tones([[180, 0.08], [120, 0.1]], "sawtooth", 0.05);
    case "boom": noise(0.45, 0.16); return tones([[110, 0.2], [70, 0.3]], "sawtooth", 0.05);
    case "stamp": noise(0.08, 0.2); return tones([[90, 0.12]], "square", 0.08);
    case "win": return tones([[523, 0.1], [659, 0.1], [784, 0.1], [1047, 0.28]]);
    case "lose": return tones([[392, 0.14], [330, 0.14], [262, 0.3]], "triangle", 0.08);
    case "laugh": return tones([[440, 0.07], [523, 0.07], [440, 0.07], [523, 0.07], [392, 0.16]], "sawtooth", 0.04);
  }
}
