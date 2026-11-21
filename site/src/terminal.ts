// Recordings of the real terminal output (python site/capture_terminal.py).
// Each line keeps the moment it appeared; the site replays them sped up.
import termJson from "../data/terminal.json";

export interface Run { command: string; exit: number; ms: number; lines: [number, string][]; sha256?: string }
export interface TerminalDoc { recorded_on: string; note: string; runs: Record<string, Run> }

export const terminal = termJson as unknown as TerminalDoc;
export const runOf = (key: string): Run | null => terminal.runs[key] ?? null;

/** Concatenate several runs into one session (the commands are shown as prompts). */
export function session(keys: string[]): Run | null {
  const runs = keys.map(runOf).filter((r): r is Run => !!r);
  if (!runs.length) return null;
  if (runs.length === 1) return runs[0]!;
  let offset = 0;
  const lines: [number, string][] = [];
  runs.forEach((r, i) => {
    if (i > 0) { lines.push([offset, ""]); lines.push([offset + 1, `$ ${r.command}`]); }
    r.lines.forEach(([ms, s]) => lines.push([offset + ms, s]));
    offset += r.ms + 200;
  });
  return { command: runs[0]!.command, exit: Math.max(...runs.map((r) => r.exit)), ms: offset, lines };
}
