"""The three reports the jury reads (PLAN 5.4):

  A  the clean books satisfy every accounting equality and show no discrepancy;
  B  the public books break exactly the declared equalities, by exactly the
     declared amounts: an independent detector finds the same issues as the truth;
  C  every admissible evidence set is sufficient on its own: the amount is
     re-derived from the cited records only (plus manifest, policy and the fx
     table as a reference), and every absence check holds on the full tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Any

from .core import Book, EpisodeFolder, parse_instant

TOLERANCE = {"duplicate_invoice": 0, "payment_allocation": 1, "fx_conversion": 1,
             "period_cutoff": 0}


@dataclass(frozen=True)
class Detected:
    type: str
    affected: tuple[str, ...]
    amount: int
    note: str

    @property
    def key(self) -> tuple[str, frozenset[str]]:
        return self.type, frozenset(self.affected)


# ---------------------------------------------------------------- detectors

def _live_invoices(book: Book) -> list[dict]:
    return [d for d in book.invoices if not d.get("credit_for")]


def detect(book: Book) -> list[Detected]:
    found: list[Detected] = []
    found += _detect_duplicates(book)
    found += _detect_allocations(book)
    found += _detect_fx(book)
    found += _detect_cutoff(book)
    return found


def _detect_duplicates(book: Book) -> list[Detected]:
    out = []
    for inv in _live_invoices(book):
        issuing = book.issuing_entries(inv["invoice_id"])
        net = len(issuing) - len(book.storno_entries(inv["invoice_id"]))
        if net >= 2:
            amount = next(r["debit_minor"] for r in issuing[-1] if r["account"] == "1200")
            out.append(Detected("duplicate_invoice", (inv["invoice_id"],), amount,
                                f"{net} live issuing entries"))
    groups: dict[tuple, list[dict]] = {}
    for inv in _live_invoices(book):
        if book.credit_notes_for(inv["invoice_id"]):
            continue
        key = (inv["entity_id"], parse_instant(inv["issued_at"]), inv["currency"],
               inv["total_minor"], repr(inv["line_items"]))
        groups.setdefault(key, []).append(inv)
    for docs in groups.values():
        if len(docs) == 2:
            issuing = book.issuing_entries(docs[1]["invoice_id"])
            amount = next(r["debit_minor"] for r in issuing[0] if r["account"] == "1200") \
                if issuing else 0
            out.append(Detected("duplicate_invoice", tuple(d["invoice_id"] for d in docs),
                                amount, "two live copies of one document"))
    return out


def _relief_events(book: Book, inv: dict) -> list[tuple[Any, str, str, int]]:
    """(moment, kind, id, applied amount) of every event that relieves the invoice."""
    events = []
    for p in book.payments:
        refs = {a["invoice_id"]: a["amount_minor"] for a in p.get("allocations") or []}
        if inv["invoice_id"] in refs:
            events.append((parse_instant(p["timestamp"]), "payment", p["payment_id"],
                           refs[inv["invoice_id"]]))
        elif not p.get("invoice_refs") and book.relief(p["payment_id"], inv["invoice_id"]):
            # allocated without a reference: only when the amount closes the invoice
            events.append((parse_instant(p["timestamp"]), "payment", p["payment_id"],
                           p["amount_minor"]))
    for cn in book.credit_notes_for(inv["invoice_id"]):
        events.append((parse_instant(cn["issued_at"]), "credit", cn["invoice_id"],
                       cn["total_minor"]))
    events.sort(key=lambda e: (e[0], e[2]))
    return events


def expected_reliefs(book: Book, inv: dict) -> list[tuple[str, str, int]]:
    issuing = book.issuing_entries(inv["invoice_id"])
    if not issuing:
        return []
    booked = next(r["debit_minor"] for r in issuing[0] if r["account"] == "1200")
    applied = relieved = 0
    out = []
    for _moment, kind, ident, amount in _relief_events(book, inv):
        applied += amount
        value = booked - relieved if applied == inv["total_minor"] else \
            book.pro_rata(amount, booked, inv["total_minor"])
        relieved += value
        out.append((kind, ident, value))
    return out


def _detect_allocations(book: Book) -> list[Detected]:
    out = []
    for inv in _live_invoices(book):
        for kind, ident, expected in expected_reliefs(book, inv):
            if kind != "payment":
                continue
            actual = book.relief(ident, inv["invoice_id"])
            if abs(expected - actual) > TOLERANCE["payment_allocation"]:
                out.append(Detected("payment_allocation", (ident, inv["invoice_id"]),
                                    expected - actual, f"expected relief {expected}, "
                                                       f"actual {actual}"))
    return out


def _detect_fx(book: Book) -> list[Detected]:
    out = []
    for inv in _live_invoices(book):
        if inv["currency"] == book.base:
            continue
        issuing = book.issuing_entries(inv["invoice_id"])
        if not issuing:
            continue
        expected = book.conv_policy(inv["total_minor"], inv["currency"],
                                    parse_instant(inv["issued_at"]))
        booked = next(r["debit_minor"] for r in issuing[0] if r["account"] == "1200")
        if abs(booked - expected) > TOLERANCE["fx_conversion"]:
            out.append(Detected("fx_conversion", (inv["invoice_id"],), abs(booked - expected),
                                f"booked {booked}, policy {expected}"))
    for p in book.payments:
        if p["currency"] == book.base or p["amount_minor"] <= 0:
            continue
        rows = book.receipt_entry(p["payment_id"])
        if rows is None:
            continue
        cash = sum(r["debit_minor"] or 0 for r in rows
                   if r["account"] in ("1010", "6100") and r["payment_id"] == p["payment_id"])
        expected = book.conv_policy(p["amount_minor"], p["currency"], parse_instant(p["timestamp"]))
        if abs(cash - expected) > TOLERANCE["fx_conversion"]:
            out.append(Detected("fx_conversion", (p["payment_id"],), abs(cash - expected),
                                f"booked {cash}, policy {expected}"))
    return out


def _detect_cutoff(book: Book) -> list[Detected]:
    out = []
    for inv in _live_invoices(book):
        event = book.period_of(parse_instant(inv["issued_at"]))
        for rows in book.issuing_entries(inv["invoice_id"]):
            if book.period_of(parse_instant(rows[0]["timestamp"])) != event:
                amount = next(r["debit_minor"] for r in rows if r["account"] == "1200")
                out.append(Detected("period_cutoff", (inv["invoice_id"],), amount,
                                    "issuing entry outside the period of the invoice"))
    for p in book.payments:
        rows = book.receipt_entry(p["payment_id"])
        if rows is None or p["amount_minor"] <= 0:
            continue
        if book.period_of(parse_instant(rows[0]["timestamp"])) != \
                book.period_of(parse_instant(p["timestamp"])):
            cash = sum(r["debit_minor"] or 0 for r in rows if r["account"] in ("1010", "6100"))
            out.append(Detected("period_cutoff", (p["payment_id"],), cash,
                                "receipt entry outside the period of the payment"))
    return out


# ------------------------------------------------------------- equalities

def balance_problems(book: Book) -> list[str]:
    problems = []
    if sum(r["debit_minor"] or 0 for r in book.ledger) != \
            sum(r["credit_minor"] or 0 for r in book.ledger):
        problems.append("total debit != total credit")
    for moment, rows in book.entries.items():
        if sum(r["debit_minor"] or 0 for r in rows) != sum(r["credit_minor"] or 0 for r in rows):
            problems.append(f"entry at {moment.isoformat()} is unbalanced")
        for r in rows:
            if bool(r["debit_minor"]) == bool(r["credit_minor"]):
                problems.append(f"row {r['row_id']} must have exactly one side")
            if r["currency"] != book.base:
                problems.append(f"row {r['row_id']} not in the base currency")
    for inv in book.invoices:
        if inv["total_minor"] != sum(li["amount_minor"] for li in inv["line_items"]):
            problems.append(f"invoice {inv['invoice_id']}: total != sum of lines")
    for p in book.payments:
        if p.get("allocations") and p["amount_minor"] > 0:
            on_2150 = sum((r["credit_minor"] or 0) - (r["debit_minor"] or 0) for r in book.ledger
                          if r["account"] == "2150" and r["payment_id"] == p["payment_id"])
            if on_2150:
                problems.append(f"payment {p['payment_id']} leaves {on_2150} on 2150")
    return problems


# ------------------------------------------------------------------ evidence

class Insufficient(Exception):
    pass


def _resolve(book: Book, ids: list[str]) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    rows, docs, fx = [], {}, {}
    for ident in ids:
        if ident in book.rows_by_id:
            rows.append(book.rows_by_id[ident])
        elif ident in book.docs:
            kind, d = book.docs[ident]
            docs[d["invoice_id"] if kind == "invoice" else d["payment_id"]] = d
        elif ident in book.fx_by_id:
            fx[ident] = book.fx_by_id[ident]
        else:
            raise Insufficient(f"unknown evidence id {ident}")
    return rows, docs, fx


def derive(book: Book, issue: dict, evidence: list[str]) -> int:
    """Amount of an issue computed from the cited records only."""
    rows, docs, fx = _resolve(book, evidence)
    etype, affected = issue["type"], issue["affected_ids"]
    for ident in affected:
        if ident not in docs:
            raise Insufficient(f"document {ident} is not cited")

    if etype == "duplicate_invoice":
        if len(affected) == 1:
            own = [r for r in rows if r["invoice_id"] == affected[0] and not r["payment_id"]
                   and r["account"] in ("1200", "4000")]
            moments = {parse_instant(r["timestamp"]) for r in own}
            if len(moments) < 2:
                raise Insufficient("two issuing entries must be cited")
            return Book.amount(own[-1])
        a, b = (docs[x] for x in affected)
        for f in ("entity_id", "currency", "total_minor", "line_items"):
            if a[f] != b[f]:
                raise Insufficient("the cited copies differ")
        if parse_instant(a["issued_at"]) != parse_instant(b["issued_at"]):
            raise Insufficient("the cited copies were issued at different moments")
        issuing = ("1200", "4000")
        own_b = [r for r in rows if r["invoice_id"] == affected[1] and r["account"] in issuing]
        own_a = [r for r in rows if r["invoice_id"] == affected[0] and r["account"] in issuing]
        if not own_a or not own_b:
            raise Insufficient("an issuing row of each copy must be cited")
        return Book.amount(own_b[0])

    if etype == "payment_allocation":
        pay_id, inv_id = affected
        pay, inv = docs[pay_id], docs[inv_id]
        alloc = {a["invoice_id"]: a["amount_minor"] for a in pay["allocations"]}[inv_id]
        issuing = [r for r in rows if r["invoice_id"] == inv_id and not r["payment_id"]
                   and r["account"] in ("1200", "4000")]
        if not issuing:
            raise Insufficient("the issuing row is not cited")
        booked = Book.amount(issuing[0])
        reliefs = [r for r in rows if r["account"] == "1200" and r["payment_id"] == pay_id
                   and r["invoice_id"] == inv_id and r["credit_minor"]]
        on_2150 = [r for r in rows if r["account"] == "2150" and r["payment_id"] == pay_id]
        if not reliefs and not on_2150:
            raise Insufficient("neither the relief row nor the 2150 row is cited")
        actual = sum(r["credit_minor"] for r in reliefs)
        prior_docs = [d for k, d in docs.items() if k not in affected and "payment_id" in d]
        prior_applied = sum(a["amount_minor"] for d in prior_docs for a in d["allocations"]
                            if a["invoice_id"] == inv_id)
        prior_relief = sum(r["credit_minor"] for r in rows if r["account"] == "1200"
                           and r["invoice_id"] == inv_id and r["payment_id"]
                           and r["payment_id"] != pay_id and r["credit_minor"])
        if alloc + prior_applied == inv["total_minor"]:
            expected = booked - prior_relief
        else:
            expected = book.pro_rata(alloc, booked, inv["total_minor"])
        return expected - actual

    if etype == "fx_conversion":
        doc = docs[affected[0]]
        is_invoice = "invoice_id" in doc and affected[0] == doc.get("invoice_id")
        account, ref = ("1200", "invoice_id") if is_invoice else ("1010", "payment_id")
        carrier = [r for r in rows if r["account"] == account and r[ref] == affected[0]
                   and r["debit_minor"]]
        if not carrier:
            raise Insufficient("the carrier row is not cited")
        event = parse_instant(doc["issued_at"] if is_invoice else doc["timestamp"])
        right = book.rate_date(doc["currency"], book.local_day(event))
        fx_id = f"{right.isoformat()}:{doc['currency']}:{book.base}" if right else None
        if fx_id not in fx:
            raise Insufficient("the fx row of the correct rate is not cited")
        rate = Fraction(fx[fx_id]["rate"])
        value = doc["total_minor"] if is_invoice else doc["amount_minor"]
        return abs(carrier[0]["debit_minor"] - book.conv(value, doc["currency"], rate))

    if etype == "period_cutoff":
        doc = docs[affected[0]]
        is_invoice = affected[0] == doc.get("invoice_id")
        ref = "invoice_id" if is_invoice else "payment_id"
        own = [r for r in rows if r[ref] == affected[0]]
        if not own:
            raise Insufficient("no row of the shifted entry is cited")
        event = parse_instant(doc["issued_at"] if is_invoice else doc["timestamp"])
        if book.period_of(parse_instant(own[0]["timestamp"])) == book.period_of(event):
            raise Insufficient("the cited entry is in the period of the document")
        value = doc["total_minor"] if is_invoice else doc["amount_minor"]
        return book.conv_policy(value, doc["currency"], event)

    raise Insufficient(f"unknown issue type {etype}")


def absence_holds(book: Book, check: dict) -> bool:
    q = check["query"]
    if q == "no_reversal_of_invoice":
        return not book.storno_entries(check["invoice_id"])
    if q == "no_credit_note_for":
        return not book.credit_notes_for(check["invoice_id"])
    if q == "no_relief_by_payment":
        return book.relief(check["payment_id"], check["invoice_id"]) == 0
    if q == "single_reclassification":
        return len(book.reclass_entries(check["payment_id"])) <= 1
    if q == "no_rate_between":
        lo, hi = date.fromisoformat(check["after"]), date.fromisoformat(check["until"])
        return not any(src == check["currency"] and lo < d <= hi
                       for (d, src, _t) in book.rates)
    if q == "no_posting_in_event_period":
        if "invoice_id" in check:
            inv = book.invoice_by_id[check["invoice_id"]]
            event = book.period_of(parse_instant(inv["issued_at"]))
            entries = book.issuing_entries(check["invoice_id"])
        else:
            pay = book.payment_by_id[check["payment_id"]]
            event = book.period_of(parse_instant(pay["timestamp"]))
            rows = book.receipt_entry(check["payment_id"])
            entries = [rows] if rows else []
        return all(book.period_of(parse_instant(e[0]["timestamp"])) != event for e in entries)
    raise ValueError(f"unknown absence query {q}")


def _sample(sets: list[list[str]], limit: int = 8) -> list[list[str]]:
    if len(sets) <= limit:
        return sets
    return [sets[i * (len(sets) - 1) // (limit - 1)] for i in range(limit)]


# --------------------------------------------------------------------- report

def report(folder: EpisodeFolder) -> dict[str, Any]:
    pub = folder.public
    result: dict[str, Any] = {"episode_id": pub.manifest["episode_id"]}

    a_problems: list[str] = []
    if folder.clean is not None:
        a_problems += balance_problems(folder.clean)
        a_problems += [f"clean books show {d.type} {list(d.affected)}: {d.note}"
                       for d in detect(folder.clean)]
    result["A"] = {"ok": folder.clean is not None and not a_problems, "problems": a_problems,
                   "checked": folder.clean is not None}

    issues = (folder.truth or {}).get("issues", [])
    found = detect(pub)
    b_problems = [p for p in balance_problems(pub) if "2150" not in p]
    truth_keys = {(i["type"], frozenset(i["affected_ids"])): i for i in issues}
    found_keys = {d.key: d for d in found}
    for key, issue in truth_keys.items():
        d = found_keys.get(key)
        if d is None:
            b_problems.append(f"declared {issue['issue_id']} {issue['type']} not found")
        elif abs(d.amount - issue["expected_amount_minor"]) > issue["tolerance_minor"]:
            b_problems.append(f"{issue['issue_id']}: amount {d.amount} != declared "
                              f"{issue['expected_amount_minor']}")
    for key, d in found_keys.items():
        if key not in truth_keys:
            b_problems.append(f"undeclared {d.type} {list(d.affected)}: {d.note}")
    result["B"] = {"ok": not b_problems, "problems": b_problems,
                   "declared": len(issues), "found": len(found)}

    c_problems: list[str] = []
    derivations = []
    for issue in issues:
        for evidence in _sample(issue["evidence_sets"]):
            try:
                amount = derive(pub, issue, evidence)
            except (Insufficient, KeyError, LookupError, StopIteration) as exc:
                c_problems.append(f"{issue['issue_id']}: set {evidence} insufficient ({exc})")
                continue
            if abs(amount - issue["expected_amount_minor"]) > issue["tolerance_minor"]:
                c_problems.append(f"{issue['issue_id']}: derived {amount} != declared "
                                  f"{issue['expected_amount_minor']}")
        for check in issue.get("absence_checks", []):
            if not absence_holds(pub, check):
                c_problems.append(f"{issue['issue_id']}: absence check {check} fails")
        derivations.append({"issue_id": issue["issue_id"],
                            "sets_checked": len(_sample(issue["evidence_sets"])),
                            "sets_total": len(issue["evidence_sets"])})
    result["C"] = {"ok": not c_problems, "problems": c_problems, "issues": derivations}
    result["ok"] = result["A"]["ok"] and result["B"]["ok"] and result["C"]["ok"]
    return result
