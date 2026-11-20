// Small data of the site (reports, README facts, claims, sources). Everything is
// produced by `python site/build_data.py` from the repository; nothing is typed in.
import metaJson from "../data/meta.json";
import readmeJson from "../data/readme.json";
import claimsJson from "../data/claims.json";
import reportsJson from "../data/reports.json";

export interface Table { headers: string[]; rows: string[][] }
export interface Section { heading: string | null; level: number; text: string[]; tables: Table[] }
export interface Report {
  file: string; kind: "markdown" | "json"; title?: string; intro?: string[];
  sections?: Section[]; meta?: { what?: string; command?: string; versions?: string }; data?: unknown;
}
export interface Prediction {
  episode_id: string | null; sha256: string | null; seed: string | null; config: string | null;
  version: string | null; rewards: { policy: string; reward: string }[]; commands: string[]; hash_command: string | null;
}
export interface Readme {
  file?: string; slogan?: string | null; license?: string | null; uids?: string[];
  prediction?: Prediction | null; isolation_command?: string | null; check_command?: string[] | null; commands?: string[];
}
export interface Claim { id: string; criterion: string; claim: string; tests: string[]; command: string }
export interface Meta {
  generator: string; command: string; check: string; present: Record<string, boolean>;
  judge_adapter?: { file: string; functions: string[]; uses_process_env: boolean } | null;
  sources: { file: string; sha256: string }[];
}

export const meta = metaJson as Meta;
export const readme = readmeJson as Readme;
export const claims = (claimsJson as { claims?: Claim[] } | null)?.claims ?? [];
export const reports = reportsJson as Record<string, Report>;

/** The first table of a report whose headers include `header` (and whose section heading matches). */
export function findTable(name: string, header: string, heading?: RegExp): Table | null {
  const rep = reports[name];
  for (const s of rep?.sections ?? []) {
    if (heading && !(s.heading && heading.test(s.heading))) continue;
    for (const t of s.tables) if (t.headers.some((h) => h.includes(header))) return t;
  }
  return null;
}

export function sectionText(name: string, heading: RegExp): string[] {
  const s = reports[name]?.sections?.find((x) => x.heading && heading.test(x.heading));
  return s?.text ?? [];
}

/** Column accessor by header name. */
export function col(t: Table, header: string): (row: string[]) => string {
  const i = t.headers.findIndex((h) => h === header || h.includes(header));
  return (row) => (i >= 0 ? row[i] ?? "" : "");
}

/** "on 20 fresh `jury_like` episodes (seeds 5000-5019, eval mode)" -> {n, seeds, from, to} */
export function sampleOf(name: string): { n: string; from: string; to: string } | null {
  const what = reports[name]?.meta?.what ?? "";
  const n = /(\d+)\s+(?:fresh\s+)?`?[a-z_]+`?\s+episodes/.exec(what) ?? /(\d+)\s+(?:fresh|dev)\b/.exec(what);
  const s = /seeds\s+(\d+)\s*-\s*(\d+)/.exec(what);
  if (!n) return null;
  return { n: n[1]!, from: s?.[1] ?? "", to: s?.[2] ?? "" };
}

/** The command of a report ("Command: `python -m vouchai report`. ...") without the backticks. */
export function commandOf(name: string): string | null {
  return /`([^`]+)`/.exec(reports[name]?.meta?.command ?? "")?.[1] ?? null;
}

/** The first README command line that contains `needle`. */
export const readmeCommand = (needle: string): string | null => readme.commands?.find((c) => c.includes(needle)) ?? null;
