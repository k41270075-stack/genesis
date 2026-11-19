"""Statistical leak audit: can an "empty" feature tell error targets apart?

For every error type, the documents it affects (positives) are compared with
all other documents of the same kind in the same episodes (controls). For each
feature that carries no accounting meaning we compute the Mann-Whitney AUC.
A value near 0.5 means the feature says nothing; the self-check bound is
|AUC - 0.5| <= 0.1 with the sample size reported next to it.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from typing import Any

from ..env.sandbox import notes
from ..episode import generate_episode
from ..timeutil import parse_ts

FEATURES = {
    "seconds_of_minute": lambda d, ts, amount, pos: ts.second,
    "minute_of_hour": lambda d, ts, amount, pos: ts.minute,
    "weekday": lambda d, ts, amount, pos: ts.weekday(),
    "id_first_symbol": lambda d, ts, amount, pos: ord(d["doc_id"][1]),
    "id_last_symbol": lambda d, ts, amount, pos: ord(d["doc_id"][-1]),
    "round_amount": lambda d, ts, amount, pos: int(amount % 1000 == 0),
    "amount_last_digit": lambda d, ts, amount, pos: amount % 10,
    "position_in_table": lambda d, ts, amount, pos: pos,
    "notes_text": lambda d, ts, amount, pos: len(d["_notes"]),
    # look-alikes around the object: a cluster of doubles must not mark an error
    # (what "phantom targets" guard against)
    "lookalikes_nearby": lambda d, ts, amount, pos: d["_neighbours"],
}


def auc(pos: list[Any], neg: list[Any]) -> Fraction | None:
    if not pos or not neg:
        return None
    ordered = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    # ranks with ties averaged
    ranks: list[Fraction] = [Fraction(0)] * len(ordered)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = Fraction(i + j + 2, 2)
        i = j + 1
    rank_sum = sum(r for r, (_v, label) in zip(ranks, ordered) if label)
    n1, n0 = len(pos), len(neg)
    return (rank_sum - Fraction(n1 * (n1 + 1), 2)) / (n1 * n0)


def _eligible(ep, etype: str, kind: str):
    """Matched controls: documents that satisfy the preconditions of the error type."""
    m = ep.manifest
    start, end = parse_ts(m["period_start"]), parse_ts(m["period_end"])
    base = m["base_currency"]
    paid_in_period = {a["invoice_id"] for p in ep.tables["payments"]
                      if start <= parse_ts(p["timestamp"]) < end for a in p["allocations"]}

    def in_period(ts: str) -> bool:
        return start <= parse_ts(ts) < end

    if etype == "period_cutoff":
        # a cut-off error needs an event within 3 days of a period edge
        def near_edge(d):
            ts = parse_ts(d["issued_at"] if kind == "invoice" else d["timestamp"])
            return min(abs((ts - e).total_seconds()) for e in (start, end)) <= 3 * 86_400
        return near_edge
    if kind == "invoice":
        if etype == "duplicate_invoice":
            return lambda d: in_period(d["issued_at"]) and not d.get("credit_for")
        if etype == "fx_conversion":
            return lambda d: in_period(d["issued_at"]) and d["currency"] != base
        return lambda d: d["invoice_id"] in paid_in_period
    if etype == "fx_conversion":
        return lambda d: (in_period(d["timestamp"]) and d["currency"] != base
                          and d["amount_minor"] > 0 and not d["fee_minor"])
    return lambda d: in_period(d["timestamp"]) and bool(d["allocations"])


def collect(seeds: range, config: str = "jury_like") -> dict[str, dict[str, list]]:
    """values[type:kind][feature] = (positives, matched controls)"""
    data: dict[str, dict[str, tuple[list, list]]] = defaultdict(
        lambda: defaultdict(lambda: ([], [])))
    for seed in seeds:
        ep = generate_episode(seed, config)
        targets: dict[str, set[str]] = defaultdict(set)
        for issue in ep.issues:
            for ident in issue["affected_ids"]:
                targets[issue["type"]].add(ident)
        for kind, table, id_field, time_field, amount_field in (
                ("invoice", "invoices", "invoice_id", "issued_at", "total_minor"),
                ("payment", "payments", "payment_id", "timestamp", "amount_minor")):
            rows = ep.tables[table]
            stamps = [parse_ts(r[time_field]) for r in rows]
            key = "entity_id" if kind == "invoice" else "currency"
            for etype, ids in targets.items():
                if not any(r[id_field] in ids for r in rows):
                    continue
                eligible = _eligible(ep, etype, kind)
                for pos, d in enumerate(rows):
                    label = d[id_field] in ids
                    if not label and not eligible(d):
                        continue
                    ts = stamps[pos]
                    # a look-alike, not the duplicate itself: an identical copy IS the
                    # error of a duplicate document, so it is not counted
                    near = sum(1 for k, r in enumerate(rows) if k != pos and r[key] == d[key]
                               and abs((stamps[k] - ts).total_seconds()) <= 3 * 86_400
                               and r.get("line_items") != d.get("line_items", 0))
                    d = dict(d, _notes=notes(kind, d), _neighbours=near)
                    position = Fraction(pos, max(1, len(rows) - 1))
                    for name, fn in FEATURES.items():
                        value = fn(d, ts, abs(d[amount_field]), position)
                        data[f"{etype}:{kind}"][name][0 if label else 1].append(value)
    return data


def audit(seeds: range, config: str = "jury_like") -> list[dict[str, Any]]:
    out = []
    for group, features in sorted(collect(seeds, config).items()):
        for name, (pos, neg) in sorted(features.items()):
            value = auc(pos, neg)
            if value is None or len(pos) < 10:
                continue
            out.append({"group": group, "feature": name, "positives": len(pos),
                        "controls": len(neg), "auc": value})
    return out


def leak_audit_md(seeds: range = range(7000, 7120)) -> str:
    rows = audit(seeds)
    lines = [
        "# Leak audit",
        "",
        f"What: Mann-Whitney AUC of features without accounting meaning, error targets vs "
        f"matched controls (documents of the same kind that satisfy the preconditions of "
        f"the error type), {len(seeds)} `jury_like` episodes "
        f"(seeds {seeds.start}-{seeds.stop - 1}).",
        "Command: `python -m vouchai report`. Bound of the self-check: |AUC - 0.5| <= 0.1.",
        "",
        "| Error type : document | Feature | Positives | Controls | AUC |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        mark = "" if abs(r["auc"] - Fraction(1, 2)) <= Fraction(1, 10) else " **(!)**"
        lines.append(f"| {r['group']} | {r['feature']} | {r['positives']} | {r['controls']} | "
                     f"{r['auc'].numerator / r['auc'].denominator:.3f}{mark} |")  # float-ok
    lines += ["", "Excluded by design: the position of a cut-off entry relative to the period "
                  "edge carries real signal (that is the error itself).", ""]
    return "\n".join(lines)
