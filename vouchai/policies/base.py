"""Building blocks for scripted policies.

A policy sees only observations: reset(seed) then act(observation) -> action.
`TableReader` pages through the four public tables, then calls decide() and
submits. Policies never import the grader or the generator.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from typing import Protocol

TABLES = ("invoices", "payments", "fx", "ledger")


class Policy(Protocol):
    name: str

    def reset(self, *, seed: int | None = None) -> None: ...

    def act(self, observation: dict) -> dict: ...


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def offset(text: str) -> timezone:
    sign = -1 if text[0] == "-" else 1
    return timezone(sign * timedelta(hours=int(text[1:3]), minutes=int(text[4:6])))


def round_policy(x: Fraction, mode: str) -> int:
    floor = x.numerator // x.denominator
    rest = x - floor
    if rest != Fraction(1, 2):
        return floor + (1 if rest > Fraction(1, 2) else 0)
    if mode == "half_even":
        return floor if floor % 2 == 0 else floor + 1
    return floor + 1 if x > 0 else floor


class View:
    """Everything a policy has read, with simple indexes."""

    def __init__(self, manifest: dict, policy: dict, data: dict[str, list[dict]]):
        self.manifest, self.policy, self.data = manifest, policy, data
        self.base = manifest["base_currency"]
        self.exp = manifest["currency_exponents"]
        self.zone = offset(manifest["timezone"])
        self.start, self.end = parse(manifest["period_start"]), parse(manifest["period_end"])
        self.rounding = policy["rounding"]["mode"]
        self.entries: dict[datetime, list[dict]] = defaultdict(list)
        for r in data["ledger"]:
            self.entries[parse(r["timestamp"])].append(r)
        self.rates = {(r["date"], r["source_currency"]): Fraction(r["rate"]) for r in data["fx"]}
        self.fx_rows = {(r["date"], r["source_currency"]): r for r in data["fx"]}
        self.invoices = {d["invoice_id"]: d for d in data["invoices"]}
        self.payments = {d["payment_id"]: d for d in data["payments"]}

    def period(self, ts: datetime) -> int:
        return -1 if ts < self.start else (0 if ts < self.end else 1)

    def conv(self, amount: int, currency: str, rate: Fraction) -> int:
        shift = self.exp[self.base] - self.exp.get(currency, 2)
        return round_policy(abs(amount) * rate * Fraction(10) ** shift, self.rounding)

    def rate_on(self, currency: str, day: date, back: int = 5) -> tuple[Fraction, str] | None:
        if currency == self.base:
            return Fraction(1), ""
        for k in range(back + 1):
            d = (day - timedelta(days=k)).isoformat()
            if (d, currency) in self.rates:
                return self.rates[(d, currency)], f"{d}:{currency}:{self.base}"
        return None

    def issuing_rows(self, invoice_id: str) -> list[dict]:
        return [r for r in self.data["ledger"] if r["invoice_id"] == invoice_id
                and r["account"] == "1200" and r["debit_minor"] and not r["payment_id"]]

    def payment_rows(self, payment_id: str) -> list[dict]:
        return [r for r in self.data["ledger"] if r["payment_id"] == payment_id]


def finding(etype: str, affected: list[str], amount: int, currency: str,
            evidence: list[str], why: str) -> dict:
    return {"type": etype, "affected_ids": affected, "claimed_amount_minor": int(amount),
            "currency": currency, "evidence_ids": list(dict.fromkeys(e for e in evidence if e))[:10],
            "explanation": why[:1000]}


class TableReader:
    """Read every table page by page (within the step budget), then submit."""

    name = "reader"
    reserve = 1                       # steps kept for the submit

    def reset(self, *, seed: int | None = None) -> None:
        self.seed = seed
        self.manifest: dict | None = None

    def act(self, observation: dict) -> dict:
        if "manifest" in observation:
            self.manifest, self.policy = observation["manifest"], observation["policy"]
            self.data = {t: [] for t in TABLES}
            self.queue = list(TABLES)
            self.cursor = None
        else:
            result = observation.get("result") or {}
            if "rows" in result:
                self.data[result["table"]].extend(result["rows"])
                self.cursor = result["next_cursor"]
                if self.cursor is None:
                    self.queue.pop(0)
            elif observation.get("error"):
                self.queue = self.queue[1:]
                self.cursor = None
        if self.queue and observation["steps_remaining"] > self.reserve:
            return {"action": "list_records", "table": self.queue[0], "cursor": self.cursor,
                    "limit": 50}
        try:
            findings = self.decide(View(self.manifest, self.policy, self.data))
        except Exception:             # a broken heuristic must still submit
            findings = []
        return {"action": "submit", "findings": {"episode_id": self.manifest["episode_id"],
                                                 "findings": findings[:30]}}

    def decide(self, view: View) -> list[dict]:
        return []
