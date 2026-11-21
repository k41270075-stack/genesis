// Types of site/data/episode.json (written by site/build_data.py) and helpers.
import type { FindingIn, Payload, TruthIssue } from "./matcher";
import type { Row, TableName, Tables } from "./sandbox";

export interface Columnar { columns: string[]; rows: unknown[][] }

export interface Invoice {
  doc_id: string; invoice_id: string; entity_id: string; issued_at: string; due_at: string;
  currency: string; total_minor: number; credit_for: string | null; replaces_invoice_id: string | null;
  line_items: { description: string; quantity: number; unit_price_minor: number; amount_minor: number;
    service_period_start: string; service_period_end: string }[];
}
export interface Payment {
  doc_id: string; payment_id: string; timestamp: string; currency: string; amount_minor: number;
  invoice_refs: string[] | null; allocations: { invoice_id: string; amount_minor: number }[]; fee_minor: number;
}
export interface LedgerRow {
  row_id: string; timestamp: string; account: string; debit_minor: number | null; credit_minor: number | null;
  currency: string; entity_id: string | null; invoice_id: string | null; payment_id: string | null;
}
export interface FxRow { id: string; date: string; source_currency: string; target_currency: string; rate: string }

export interface Manifest {
  episode_id: string; company: string; base_currency: string; currency_exponents: Record<string, number>;
  period_start: string; period_end: string; timezone: string; rounding: string; env_version: string;
  generator_version: string; time_conventions: { bank_timezone: string };
  counts: Record<string, number>;
  [k: string]: unknown;
}

export interface EpisodeData {
  episode_id: string;
  folder: string;
  tables_sha256: string;
  passport_verifier?: string | null;
  sha256_recipe: string;
  manifest: Manifest;
  policy: {
    fx: Record<string, string | number>;
    findings: { types: Record<string, Record<string, unknown>>; legitimate_rules?: Record<string, string>; [k: string]: unknown };
    [k: string]: unknown;
  };
  tables: Record<TableName, Columnar>;
  truth: { episode_id: string; issues: (TruthIssue & { variant?: string; interaction_group?: string | null;
    carrier_row_ids?: string[]; derivation?: Record<string, string> })[] };
  auditor: null | { policy: string; split: string; actions: number; inspection_steps: number;
    tools: Record<string, number>; findings: Payload; reward: number; source: string };
  hall: null | { invoices: Invoice[]; ledger_rows: LedgerRow[] };
  life: null | {
    issue_id: string; interaction_group: string | null; payment: Payment; carrier_rows: LedgerRow[];
    rate_used: FxRow | null; rate_correct: FxRow | null; expected_amount_minor: number; tolerance_minor: number;
    partner_issues: { issue_id: string; type: string; affected_ids: string[]; expected_amount_minor: number }[];
    rule: Record<string, string | number>;
    period: { start: string; end: string; timezone: string; bank_timezone: string };
  };
}

export function rowsOf(t: Columnar): Row[] {
  return t.rows.map((r) => Object.fromEntries(t.columns.map((c, i) => [c, r[i]])));
}

const cache = new WeakMap<EpisodeData, Tables>();
export function tablesOf(ep: EpisodeData): Tables {
  let t = cache.get(ep);
  if (!t) {
    t = { ledger: rowsOf(ep.tables.ledger), invoices: rowsOf(ep.tables.invoices),
      payments: rowsOf(ep.tables.payments), fx: rowsOf(ep.tables.fx) };
    cache.set(ep, t);
  }
  return t;
}

/** Every ID the tools can fetch (row, doc, business and fx IDs; not entity IDs). */
export function publicIds(t: Tables): Set<string> {
  const ids = new Set<string>();
  const add = (v: unknown) => { if (typeof v === "string" && v) ids.add(v); };
  t.ledger.forEach((r) => { add(r.row_id); add(r.invoice_id); add(r.payment_id); });
  t.invoices.forEach((r) => { add(r.doc_id); add(r.invoice_id); });
  t.payments.forEach((r) => { add(r.doc_id); add(r.payment_id); });
  t.fx.forEach((r) => add(r.id));
  return ids;
}

export const payloadOf = (episodeId: string, findings: FindingIn[]): Payload => ({ episode_id: episodeId, findings });

/** Lazy import: the episode (public tables + demo truth) is loaded only by levels that use it. */
let pending: Promise<EpisodeData> | null = null;
export function loadEpisode(): Promise<EpisodeData> {
  pending ??= import("../../data/episode.json").then((m) => m.default as unknown as EpisodeData);
  return pending;
}
