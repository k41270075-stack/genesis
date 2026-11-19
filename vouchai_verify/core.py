"""Reading an episode folder and the accounting arithmetic, written from the
published rules only (manifest + policy). Nothing here comes from `vouchai`.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


def parse_instant(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ValueError(f"timestamp without offset: {text}")
    return value


def parse_offset(text: str) -> timezone:
    sign = -1 if text[0] == "-" else 1
    hours, minutes = int(text[1:3]), int(text[4:6])
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def round_half(x: Fraction, mode: str) -> int:
    floor = x.numerator // x.denominator
    rest = x - floor
    if rest < Fraction(1, 2):
        return floor
    if rest > Fraction(1, 2):
        return floor + 1
    if mode == "half_even":
        return floor if floor % 2 == 0 else floor + 1
    if mode == "half_up":
        return floor + 1 if x > 0 else floor
    raise ValueError(f"unknown rounding mode {mode}")


@dataclass
class Book:
    """One set of tables (public or clean) with the episode rules."""

    manifest: dict[str, Any]
    policy: dict[str, Any]
    ledger: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    fx: list[dict[str, Any]]
    entries: dict[datetime, list[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        grouped: dict[datetime, list[dict]] = defaultdict(list)
        for row in self.ledger:
            grouped[parse_instant(row["timestamp"])].append(row)
        self.entries = dict(sorted(grouped.items()))
        self.base = self.manifest["base_currency"]
        self.exponents = self.manifest["currency_exponents"]
        self.zone = parse_offset(self.policy["period"]["timezone"])
        self.period = (parse_instant(self.manifest["period_start"]),
                       parse_instant(self.manifest["period_end"]))
        self.rounding = self.policy["rounding"]["mode"]
        self.rates: dict[tuple[date, str, str], Fraction] = {}
        for r in self.fx:
            self.rates[(date.fromisoformat(r["date"]), r["source_currency"],
                        r["target_currency"])] = Fraction(r["rate"])
        self.invoice_by_id = {d["invoice_id"]: d for d in self.invoices}
        self.payment_by_id = {d["payment_id"]: d for d in self.payments}
        self.docs: dict[str, tuple[str, dict]] = {}
        for d in self.invoices:
            self.docs[d["doc_id"]] = ("invoice", d)
            self.docs.setdefault(d["invoice_id"], ("invoice", d))
        for d in self.payments:
            self.docs[d["doc_id"]] = ("payment", d)
            self.docs.setdefault(d["payment_id"], ("payment", d))
        self.rows_by_id = {r["row_id"]: r for r in self.ledger}
        self.fx_by_id = {f"{r['date']}:{r['source_currency']}:{r['target_currency']}": r
                         for r in self.fx}

    # -------------------------------------------------------- arithmetic

    def local_day(self, instant: datetime) -> date:
        return instant.astimezone(self.zone).date()

    def period_of(self, instant: datetime) -> int:
        if instant < self.period[0]:
            return -1
        return 0 if instant < self.period[1] else 1

    def rate_date(self, currency: str, day: date) -> date | None:
        rule = self.policy["fx"]["rate_date"]
        first = day if rule == "same_day_or_previous" else day - timedelta(days=1)
        for back in range(self.policy["fx"]["max_lookback_days"] + 1):
            d = first - timedelta(days=back)
            if (d, currency, self.base) in self.rates:
                return d
        return None

    def rate(self, currency: str, instant: datetime) -> Fraction:
        if currency == self.base:
            return Fraction(1)
        d = self.rate_date(currency, self.local_day(instant))
        if d is None:
            raise LookupError(f"no {currency} rate for {self.local_day(instant)}")
        return self.rates[(d, currency, self.base)]

    def conv(self, amount: int, currency: str, rate: Fraction) -> int:
        shift = self.exponents[self.base] - self.exponents[currency]
        magnitude = round_half(abs(amount) * rate * Fraction(10) ** shift, self.rounding)
        return -magnitude if amount < 0 else magnitude

    def conv_policy(self, amount: int, currency: str, instant: datetime) -> int:
        return self.conv(amount, currency, self.rate(currency, instant))

    def pro_rata(self, part: int, booked: int, total: int) -> int:
        return round_half(Fraction(part * booked, total), self.rounding)

    # ------------------------------------------------------- entry roles

    @staticmethod
    def amount(row: dict) -> int:
        return row["debit_minor"] or row["credit_minor"] or 0

    def issuing_entries(self, invoice_id: str) -> list[list[dict]]:
        out = []
        for rows in self.entries.values():
            if (any(r["account"] == "1200" and r["debit_minor"] and r["invoice_id"] == invoice_id
                    and not r["payment_id"] for r in rows)
                    and any(r["account"] == "4000" and r["credit_minor"]
                            and r["invoice_id"] == invoice_id for r in rows)):
                out.append(rows)
        return out

    def storno_entries(self, invoice_id: str) -> list[list[dict]]:
        return [rows for rows in self.entries.values()
                if any(r["account"] == "4000" and r["debit_minor"] and r["invoice_id"] == invoice_id
                       for r in rows)
                and any(r["account"] == "1200" and r["credit_minor"]
                        and r["invoice_id"] == invoice_id and not r["payment_id"] for r in rows)]

    def receipt_entry(self, payment_id: str) -> list[dict] | None:
        for rows in self.entries.values():
            if any(r["account"] == "1010" and r["payment_id"] == payment_id for r in rows):
                return rows
        return None

    def reclass_entries(self, payment_id: str) -> list[list[dict]]:
        return [rows for rows in self.entries.values()
                if any(r["account"] == "2150" and r["debit_minor"] and r["payment_id"] == payment_id
                       for r in rows)
                and not any(r["account"] == "1010" for r in rows)]

    def relief(self, payment_id: str, invoice_id: str) -> int:
        return sum(r["credit_minor"] for r in self.ledger
                   if r["account"] == "1200" and r["payment_id"] == payment_id
                   and r["invoice_id"] == invoice_id and r["credit_minor"])

    def credit_notes_for(self, invoice_id: str) -> list[dict]:
        return [d for d in self.invoices if d.get("credit_for") == invoice_id]


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _num(text: str) -> int | None:
    return int(text) if text != "" else None


def _opt(text: str) -> str | None:
    return text if text != "" else None


def read_tables(folder: Path) -> dict[str, list[dict]]:
    ledger = [{"row_id": r["row_id"], "timestamp": r["timestamp"], "account": r["account"],
               "debit_minor": _num(r["debit_minor"]), "credit_minor": _num(r["credit_minor"]),
               "currency": r["currency"], "entity_id": _opt(r["entity_id"]),
               "invoice_id": _opt(r["invoice_id"]), "payment_id": _opt(r["payment_id"])}
              for r in _read_csv(folder / "ledger.csv")]
    return {"ledger": ledger, "invoices": _read_jsonl(folder / "invoices.jsonl"),
            "payments": _read_jsonl(folder / "payments.jsonl"),
            "fx": _read_csv(folder / "fx.csv")}


@dataclass
class EpisodeFolder:
    root: Path
    public: Book
    clean: Book | None
    truth: dict[str, Any] | None


def load(folder: str | Path) -> EpisodeFolder:
    root = Path(folder)
    pub_dir = root / "public" if (root / "public").is_dir() else root
    manifest = json.loads((pub_dir / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((pub_dir / "policy.json").read_text(encoding="utf-8"))
    public = Book(manifest, policy, **read_tables(pub_dir))
    clean = None
    if (root / "private" / "clean" / "ledger.csv").is_file():
        clean = Book(manifest, policy, **read_tables(root / "private" / "clean"))
    truth = None
    if (root / "private" / "truth.json").is_file():
        truth = json.loads((root / "private" / "truth.json").read_text(encoding="utf-8"))
    return EpisodeFolder(root=root, public=public, clean=clean, truth=truth)
