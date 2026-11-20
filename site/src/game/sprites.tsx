// Pixel sprites drawn from character matrices onto <canvas>, scaled with
// image-rendering: pixelated. Frames animate on a shared slow ticker.
import { useEffect, useRef, useState } from "react";
import { palette } from "../../tailwind.config";
import { useGame } from "./store";

const C: Record<string, string> = {
  k: "#000000", n: palette.night, d: palette.dusk, f: palette.fog, p: palette.paper, w: palette.white,
  r: palette.stamp, e: palette.ember, b: palette.carbon, s: palette.sky, g: palette.leaf, l: palette.lime,
  y: palette.gold, a: palette.amber, o: palette.wood, x: "#E9B98F", h: "#3A2416", m: "#5A3A8A", t: palette.slate,
};

type Frames = string[][];

export const SPRITES: Record<string, Frames> = {
  hero: [[
    "......hhhhh.....",
    ".....hhhhhhh....",
    ".....hxxxxxh....",
    ".....kkxkkxx....",
    ".....xxxxxxx....",
    "......xxrxx.....",
    "....bbbxxxbb....",
    "...bbbbpppbbb...",
    "...bxbbpppbbbyy.",
    "...xxbbpppbbykky",
    "....bbbbbbbbykky",
    "....bbbbbbbb.yy.",
    "....ddd..ddd..o.",
    "....ddd..ddd....",
    "...kkkk..kkkk...",
    "................",
  ], [
    "................",
    "......hhhhh.....",
    ".....hhhhhhh....",
    ".....hxxxxxh....",
    ".....kkxkkxx....",
    ".....xxxxxxx....",
    "......xxrxx.....",
    "....bbbxxxbb....",
    "...bbbbpppbbbyy.",
    "...bxbbpppbbykky",
    "...xxbbpppbbykky",
    "....bbbbbbbb.yy.",
    "....ddd..ddd..o.",
    "...kkkk..ddd....",
    ".........kkkk...",
    "................",
  ]],
  boss: [[
    "......kkkkkkkk......",
    "......kkkkkkkk......",
    "......kkkkkkkk......",
    "......krrrrrrk......",
    "....kkkkkkkkkkkk....",
    ".......xxxxxx.......",
    "......xkkxxkkx......",
    "......xxxxxxxx......",
    ".....hhhhxxhhhh.....",
    "......xxkkkkxx......",
    ".......xxxxxx.......",
    "....rrrrwwwwrrrr....",
    "...rrrrrwyywrrrrr...",
    "..rrrrrrwwwwrrrrrr..",
    "..xxrrrrryyrrrrrxx..",
    "..xx.rrrrrrrrrr.xx..",
    ".....rrrrrrrrrr.....",
    ".....mmmm..mmmm.....",
    ".....mmmm..mmmm.....",
    "....kkkkk..kkkkk....",
  ], [
    "......kkkkkkkk......",
    "......kkkkkkkk......",
    "......kkkkkkkk......",
    "......krrrrrrk......",
    "....kkkkkkkkkkkk....",
    ".......xxxxxx.......",
    "......xkkxxkkx......",
    "......xxxxxxxx......",
    ".....hhhhxxhhhh.....",
    "......xkrrrrkx......",
    ".......xkkkkx.......",
    "....rrrrwwwwrrrr....",
    "..xxrrrrwyywrrrrxx..",
    "..xxrrrrwwwwrrrrxx..",
    "....rrrrryyrrrrr....",
    ".....rrrrrrrrrr.....",
    ".....rrrrrrrrrr.....",
    ".....mmmm..mmmm.....",
    ".....mmmm..mmmm.....",
    "....kkkkk..kkkkk....",
  ]],
  enemy: [[
    "...e....e...",
    "....e..e....",
    "...eeeeeee..",
    "..eekeeekee.",
    ".eeeeeeeeeee",
    ".e.eeeeeee.e",
    ".e.e.....e.e",
    "....ee.ee...",
  ], [
    "...e....e...",
    ".e..e..e..e.",
    ".e.eeeeeee.e",
    ".eeekeeekeee",
    ".eeeeeeeeeee",
    "..eeeeeeeee.",
    "...e.....e..",
    "..e.......e.",
  ]],
  coin: [
    ["..yyyy..", ".yaaaay.", "yayyyyay", "yayaayay", "yayaayay", "yayyyyay", ".yaaaay.", "..yyyy.."],
    ["...yy...", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "...yy..."],
    ["...ay...", "...ay...", "...ay...", "...ay...", "...ay...", "...ay...", "...ay...", "...ay..."],
    ["...yy...", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "..yaay..", "...yy..."],
  ],
  chest: [[
    "................",
    "..oooooooooooo..",
    ".oyyyyyyyyyyyyo.",
    ".oooooooooooooo.",
    ".ooooooyyoooooo.",
    ".kkkkkkykykkkkk.",
    ".ooooooyyoooooo.",
    ".oooooooooooooo.",
    ".oyoooooooooyoo.",
    ".oooooooooooooo.",
    ".oyyyyyyyyyyyyo.",
    "..kkkkkkkkkkkk..",
  ]],
  receipt: [[
    "pppppppp",
    "pkkkkkkp",
    "pppppppp",
    "pkkkpkkp",
    "pppppppp",
    "pkkpkkkp",
    "pppppppp",
    "prrrrrrp",
    "pprrrrpp",
    "p.p.p.p.",
  ]],
  star: [[
    "....y....",
    "....y....",
    "...yyy...",
    "yyyyyyyyy",
    ".yyyyyyy.",
    "..yyyyy..",
    "..yy.yy..",
    ".yy...yy.",
    ".y.....y.",
  ]],
  starOff: [[
    "....d....",
    "....d....",
    "...ddd...",
    "ddddddddd",
    ".ddddddd.",
    "..ddddd..",
    "..dd.dd..",
    ".dd...dd.",
    ".d.....d.",
  ]],
  bolt: [["...yy", "..yy.", ".yyy.", "yyyyy", "..yy.", ".yy..", "yy..."]],
  shield: [[
    ".bbbbbbbbbb.",
    "bsssssssssbb",
    "bsbbbbbbbsbb",
    "bsbwwbbbbsbb",
    "bsbwbbbbbsbb",
    "bsbbbbbbbsbb",
    "bsbbbbbbbsbb",
    ".bsbbbbbbsb.",
    ".bsbbbbbbsb.",
    "..bsbbbbsb..",
    "...bsbbsb...",
    "....bssb....",
    ".....bb.....",
  ]],
  invoice: [[
    "pppppppppp",
    "pkkkkkpppp",
    "pppppppppp",
    "pffffffffp",
    "pppppppppp",
    "pffffffppp",
    "pppppppppp",
    "pffffffffp",
    "pppppppppp",
    "ppppppbbbp",
    "ppppppbbbp",
    "pppppppppp",
  ]],
};

const cache = new Map<string, HTMLCanvasElement[]>();
function frames(name: string): HTMLCanvasElement[] {
  const hit = cache.get(name);
  if (hit) return hit;
  const out = (SPRITES[name] ?? []).map((rows) => {
    const h = rows.length, w = rows[0]?.length ?? 0;
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d")!;
    rows.forEach((row, y) => [...row].forEach((ch, x) => {
      const col = C[ch];
      if (col) { g.fillStyle = col; g.fillRect(x, y, 1, 1); }
    }));
    return c;
  });
  cache.set(name, out);
  return out;
}

// one shared ticker for all sprites (6 frames per second)
let tick = 0;
const subs = new Set<(t: number) => void>();
let timer: number | null = null;
function useTick(active: boolean): number {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!active) return;
    subs.add(setT);
    timer ??= window.setInterval(() => { tick++; subs.forEach((f) => f(tick)); }, 170);
    return () => {
      subs.delete(setT);
      if (!subs.size && timer !== null) { window.clearInterval(timer); timer = null; }
    };
  }, [active]);
  return t;
}

export function Sprite({ name, scale = 4, frame, animate = true, flip = false, className = "", title }: {
  name: keyof typeof SPRITES | string; scale?: number; frame?: number; animate?: boolean; flip?: boolean;
  className?: string; title?: string;
}) {
  const { calm } = useGame();
  const fs = SPRITES[name] ?? [];
  const live = animate && !calm && frame === undefined && fs.length > 1;
  const t = useTick(live);
  const ref = useRef<HTMLCanvasElement>(null);
  const idx = frame ?? (live ? t % fs.length : 0);
  const w = fs[0]?.[0]?.length ?? 1, h = fs[0]?.length ?? 1;
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const src = frames(name)[idx % Math.max(1, fs.length)];
    const g = c.getContext("2d");
    if (!g || !src) return;
    g.clearRect(0, 0, c.width, c.height);
    g.drawImage(src, 0, 0);
  }, [name, idx, fs.length]);
  return (
    <canvas ref={ref} width={w} height={h} role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}
      className={`pixelated inline-block ${className}`}
      style={{ width: w * scale, height: h * scale, transform: flip ? "scaleX(-1)" : undefined }} />
  );
}

export function Stars({ n, of = 3, scale = 3 }: { n: number; of?: number; scale?: number }) {
  return (
    <span className="inline-flex gap-1" role="img" aria-label={`звёзд: ${n} из ${of}`}>
      {Array.from({ length: of }, (_, i) => <Sprite key={i} name={i < n ? "star" : "starOff"} scale={scale} animate={false} />)}
    </span>
  );
}
