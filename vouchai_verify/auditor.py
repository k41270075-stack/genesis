"""A scripted auditor built on the independent detector.

It reads the four public tables through the environment tools (no truth, no
seed), runs the same detectors as the verifier and cites a complete evidence
set for every finding. Its job is to prove that every episode is solvable from
public data within the step budget; it is not the jury's oracle.

    python -m vouchai run --policy vouchai_verify.auditor:Auditor --config jury_like
"""

from __future__ import annotations

from .checks import detect, expected_reliefs
from .core import Book, parse_instant

TABLES = ("invoices", "payments", "fx", "ledger")


class Auditor:
    name = "vouchai_auditor"

    def reset(self, *, seed=None):
        self.manifest = None

    def act(self, observation: dict) -> dict:
        if "manifest" in observation:
            self.manifest, self.policy = observation["manifest"], observation["policy"]
            self.data = {t: [] for t in TABLES}
            self.queue, self.cursor = list(TABLES), None
        else:
            result = observation.get("result") or {}
            if "rows" in result:
                self.data[result["table"]].extend(result["rows"])
                self.cursor = result["next_cursor"]
                if self.cursor is None:
                    self.queue.pop(0)
        if self.queue and observation["steps_remaining"] > 1:
            return {"action": "list_records", "table": self.queue[0], "cursor": self.cursor,
                    "limit": 50}
        try:
            findings = self.findings()
        except Exception:
            findings = []
        return {"action": "submit", "findings": {"episode_id": self.manifest["episode_id"],
                                                 "findings": findings[:30]}}

    def findings(self) -> list[dict]:
        fx = [{k: v for k, v in r.items() if k != "id"} for r in self.data["fx"]]
        book = Book(self.manifest, self.policy, self.data["ledger"], self.data["invoices"],
                    self.data["payments"], fx)
        out = []
        for d in detect(book):
            evidence = self.evidence(book, d.type, list(d.affected))
            out.append({"type": d.type, "affected_ids": list(d.affected),
                        "claimed_amount_minor": abs(d.amount), "currency": book.base,
                        "evidence_ids": evidence[:10], "explanation": d.note})
        return out

    def evidence(self, book: Book, etype: str, affected: list[str]) -> list[str]:
        def doc(ident):
            kind, d = book.docs[ident]
            return d["doc_id"]

        def issuing(inv_id, n=1):
            entries = book.issuing_entries(inv_id)
            return [next(r["row_id"] for r in e if r["account"] == "1200") for e in entries[:n]]

        if etype == "duplicate_invoice" and len(affected) == 1:
            return [doc(affected[0])] + issuing(affected[0], 2)
        if etype == "duplicate_invoice":
            return [doc(affected[0]), doc(affected[1])] + issuing(affected[0]) + \
                issuing(affected[1])
        if etype == "payment_allocation":
            pay_id, inv_id = affected
            ids = [doc(pay_id), doc(inv_id)] + issuing(inv_id)
            relief = [r["row_id"] for r in book.ledger if r["account"] == "1200"
                      and r["payment_id"] == pay_id and r["invoice_id"] == inv_id
                      and r["credit_minor"]]
            held = [r["row_id"] for r in book.ledger if r["account"] == "2150"
                    and r["payment_id"] == pay_id]
            ids += relief[:1] or held[:1]
            inv = book.invoice_by_id[inv_id]
            moment = parse_instant(book.payment_by_id[pay_id]["timestamp"])
            for kind, ident, _value in expected_reliefs(book, inv):
                if kind == "payment" and ident != pay_id and \
                        parse_instant(book.payment_by_id[ident]["timestamp"]) < moment:
                    ids.append(doc(ident))
                    ids += [r["row_id"] for r in book.ledger if r["account"] == "1200"
                            and r["payment_id"] == ident and r["invoice_id"] == inv_id][:1]
            return ids
        if etype == "fx_conversion":
            ident = affected[0]
            if ident in book.invoice_by_id:
                d, account, ref = book.invoice_by_id[ident], "1200", "invoice_id"
                event = parse_instant(d["issued_at"])
            else:
                d, account, ref = book.payment_by_id[ident], "1010", "payment_id"
                event = parse_instant(d["timestamp"])
            rows = [r["row_id"] for r in book.ledger if r["account"] == account
                    and r[ref] == ident and r["debit_minor"]]
            day = book.rate_date(d["currency"], book.local_day(event))
            return [d["doc_id"]] + rows[:1] + [f"{day.isoformat()}:{d['currency']}:{book.base}"]
        if etype == "period_cutoff":
            ident = affected[0]
            if ident in book.invoice_by_id:
                inv = book.invoice_by_id[ident]
                event = book.period_of(parse_instant(inv["issued_at"]))
                rows = [r["row_id"] for e in book.issuing_entries(ident) for r in e
                        if book.period_of(parse_instant(r["timestamp"])) != event
                        and r["account"] in ("1200", "4000")]
                return [inv["doc_id"]] + rows[:1]
            entry = book.receipt_entry(ident) or []
            carriers = [r["row_id"] for r in entry if r["account"] in ("1010", "6100")
                        and r["debit_minor"]]
            return [book.payment_by_id[ident]["doc_id"]] + carriers[:2]
        return []
