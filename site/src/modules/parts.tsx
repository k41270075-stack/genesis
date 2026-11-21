// Small pieces shared by the pictures; every one is a pure function of progress.
import type { CSSProperties, ReactNode } from "react";
import { backOut, clamp01, easeOut, seg } from "../engine/clock";

export function Appear({ p, at, dur = 0.06, dy = 14, dx = 0, className = "", style, children }:
  { p: number; at: number; dur?: number; dy?: number; dx?: number; className?: string; style?: CSSProperties; children: ReactNode }) {
  const x = easeOut(seg(p, at, at + dur));
  return (
    <div className={className} style={{ ...style, opacity: x, transform: `translate(${(1 - x) * dx}px, ${(1 - x) * dy}px)` }}>
      {children}
    </div>
  );
}

export function StampMark({ p, at, children, color = "#FF4D3D", className = "", size = 34, rotate = -12 }:
  { p: number; at: number; children: ReactNode; color?: string; className?: string; size?: number; rotate?: number }) {
  const x = seg(p, at, at + 0.035);
  if (x <= 0) return null;
  const s = 2.8 - 1.8 * backOut(x);
  return (
    <div className={`pointer-events-none select-none ${className}`}
      style={{ transform: `rotate(${rotate}deg) scale(${s})`, opacity: clamp01(x * 3) }}>
      <div className="stamp" style={{ color, fontSize: size, lineHeight: 1, mixBlendMode: "normal", background: "rgba(5,6,10,.35)" }}>{children}</div>
    </div>
  );
}

export function Ripple({ p, at, color = "#FF4D3D", className = "" }: { p: number; at: number; color?: string; className?: string }) {
  const x = seg(p, at, at + 0.12);
  if (x <= 0 || x >= 1) return null;
  return (
    <div className={`pointer-events-none absolute rounded-full border-2 ${className}`}
      style={{ borderColor: color, transform: `translate(-50%,-50%) scale(${0.2 + easeOut(x) * 5})`, opacity: 1 - x, width: 80, height: 80 }} />
  );
}

/** Semicircle gauge from -1 to +1 with a needle. */
export function Gauge({ value, size = 220, label }: { value: number; size?: number; label?: ReactNode }) {
  const v = Math.max(-1, Math.min(1, value));
  const a = Math.PI * (1 - (v + 1) / 2);
  const r = size / 2 - 14, cx = size / 2, cy = size / 2;
  const arc = (from: number, to: number) => {
    const p = (t: number) => [cx + r * Math.cos(Math.PI * (1 - t)), cy - r * Math.sin(Math.PI * (1 - t))];
    const [x1, y1] = p(from), [x2, y2] = p(to);
    return `M${x1} ${y1} A${r} ${r} 0 0 1 ${x2} ${y2}`;
  };
  const color = v >= 0.5 ? "#3DDC97" : v >= 0 ? "#FFC34D" : "#FF4D3D";
  return (
    <div className="relative" style={{ width: size, height: size / 2 + 66 }}>
      <svg width={size} height={size / 2 + 8} className="overflow-visible">
        <path d={arc(0, 1)} stroke="#1D2231" strokeWidth={12} fill="none" strokeLinecap="round" />
        <path d={arc(0, 0.5)} stroke="#FF4D3D" strokeOpacity={0.35} strokeWidth={12} fill="none" />
        <path d={arc(0.5, 0.75)} stroke="#FFC34D" strokeOpacity={0.35} strokeWidth={12} fill="none" />
        <path d={arc(0.75, 1)} stroke="#3DDC97" strokeOpacity={0.35} strokeWidth={12} fill="none" strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={cx + (r - 6) * Math.cos(a)} y2={cy - (r - 6) * Math.sin(a)} stroke={color} strokeWidth={4} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 8px ${color})` }} />
        <circle cx={cx} cy={cy} r={7} fill={color} />
        <line x1={cx - r} y1={cy + 1} x2={cx + r} y2={cy + 1} stroke="#1D2231" strokeWidth={1} />
        <text x={14} y={cy + 22} fill="#8B93A7" fontSize={11} fontFamily="JetBrains Mono Variable">−1</text>
        <text x={size - 26} y={cy + 22} fill="#8B93A7" fontSize={11} fontFamily="JetBrains Mono Variable">+1</text>
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="h-display tabnum text-[34px]" style={{ color }}>{(v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(3).replace(".", ",")}</div>
        {label && <div className="text-[11px] text-mute">{label}</div>}
      </div>
    </div>
  );
}

/** Rolling digits. */
export function Odometer({ value, digits = 3, className = "", h = 44 }: { value: number; digits?: number; className?: string; h?: number }) {
  const s = String(Math.max(0, Math.round(value))).padStart(digits, "0").split("");
  return (
    <div className={`flex gap-[3px] ${className}`}>
      {s.map((d, i) => (
        <div key={i} className="overflow-hidden rounded-md bg-paper text-paperInk" style={{ height: h, width: h * 0.7 }}>
          <div style={{ transform: `translateY(${-Number(d) * h}px)`, transition: "transform .35s cubic-bezier(.2,.8,.2,1)" }}>
            {Array.from({ length: 10 }, (_, k) => (
              <div key={k} className="grid place-items-center font-mono font-bold" style={{ height: h, fontSize: h * 0.55 }}>{k}</div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export const Label = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`font-mono text-[10.5px] uppercase tracking-[0.18em] text-mute ${className}`}>{children}</div>
);

/** Running count from 0 to `to` between progress a..b. */
export const countUp = (p: number, a: number, b: number, to: number) => Math.round(to * easeOut(seg(p, a, b)));
