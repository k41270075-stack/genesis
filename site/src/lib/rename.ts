// Paired check in the browser: a one-to-one renaming of every ID in the public
// tables and in the truth, plus a shuffle of every table (like the jury's P-tests).
import type { TruthIssue } from "./matcher";
import type { Row, Tables } from "./sandbox";

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

export interface Renamed { tables: Tables; issues: TruthIssue[]; map: Map<string, string> }

export function renameEpisode(tables: Tables, issues: TruthIssue[], seed: number): Renamed {
  const rnd = mulberry32(seed);
  const map = new Map<string, string>();
  const used = new Set<string>();
  const fresh = () => {
    for (;;) {
      let s = "X";
      for (let i = 0; i < 9; i++) s += ALPHABET[Math.floor(rnd() * ALPHABET.length)];
      if (!used.has(s)) { used.add(s); return s; }
    }
  };
  const r = (v: unknown): unknown => {
    if (typeof v !== "string" || !v) return v;
    let m = map.get(v);
    if (!m) { m = fresh(); map.set(v, m); }
    return m;
  };
  const shuffle = <T,>(xs: T[]): T[] => {
    const a = [...xs];
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j]!, a[i]!]; }
    return a;
  };
  const ledger = tables.ledger.map((x): Row => ({ ...x, row_id: r(x.row_id), entity_id: r(x.entity_id), invoice_id: r(x.invoice_id), payment_id: r(x.payment_id) }));
  const invoices = tables.invoices.map((x): Row => ({ ...x, doc_id: r(x.doc_id), invoice_id: r(x.invoice_id), entity_id: r(x.entity_id),
    credit_for: r(x.credit_for), replaces_invoice_id: r(x.replaces_invoice_id) }));
  const payments = tables.payments.map((x): Row => ({ ...x, doc_id: r(x.doc_id), payment_id: r(x.payment_id),
    invoice_refs: Array.isArray(x.invoice_refs) ? (x.invoice_refs as unknown[]).map(r) : x.invoice_refs,
    allocations: Array.isArray(x.allocations) ? (x.allocations as Row[]).map((a) => ({ ...a, invoice_id: r(a.invoice_id) })) : x.allocations }));
  const fx = tables.fx.map((x): Row => ({ ...x, id: r(x.id) }));
  const ids = (xs: string[] | undefined) => xs?.map((x) => String(r(x)));
  const renamedIssues = issues.map((i) => ({
    ...i, affected_ids: ids(i.affected_ids)!, evidence_ids: ids(i.evidence_ids),
    evidence_slots: i.evidence_slots?.map((s) => ids(s)!), evidence_sets: i.evidence_sets?.map((s) => ids(s)!),
  }));
  return { tables: { ledger: shuffle(ledger), invoices: shuffle(invoices), payments: shuffle(payments), fx: shuffle(fx) }, issues: renamedIssues, map };
}
