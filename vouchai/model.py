"""Internal model of the hidden company history.

Everything here uses internal keys ("inv007", "pay012/recv"). Public IDs and
row order are assigned only by the renderer, after all mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction


@dataclass(frozen=True)
class Customer:
    key: str
    name: str
    currency: str
    subscription: bool


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: int
    unit_price_minor: int
    amount_minor: int
    service_period_start: str
    service_period_end: str


@dataclass
class Invoice:
    key: str
    customer: str
    currency: str
    issued_at: datetime          # company offset
    due_at: datetime             # company offset
    lines: list[LineItem]
    total: int
    copy_of: str | None = None   # provenance only: an injected or legitimate copy
    credit_for: str | None = None    # credit note: key of the cancelled invoice (full)
    replaces: str | None = None      # re-issued invoice: key of the cancelled one

    @property
    def is_credit_note(self) -> bool:
        return self.credit_for is not None


@dataclass
class Payment:
    key: str
    customer: str
    currency: str
    timestamp: datetime          # bank offset
    amount: int                  # gross, what the customer sent; negative = refund
    fee: int                     # bank fee withheld from amount, doc currency
    allocations: list[tuple[str, int]]   # (invoice key, amount in payment currency)
    mode: str = "direct"         # direct | two_step (via 2150, D17)
    public_refs: bool = True     # False: allocated without a reference (D13)
    excess_account: str = "2150"  # where an unallocated amount goes: 2150 or 2200


@dataclass
class Expense:
    key: str
    timestamp: datetime          # company offset
    account: str
    amount: int                  # base currency


@dataclass
class Decisions:
    """The parameters the engine posts from. Errors change these, nothing else."""

    invoice_postings: dict[str, list[datetime]] = field(default_factory=dict)
    payment_posting: dict[str, datetime] = field(default_factory=dict)
    # two-step receipts: moment of the reclassification 2150 -> 1200
    reclass_posting: dict[str, datetime] = field(default_factory=dict)
    # storno and re-posting (D14): (wrong posting, mirror reversal) before the right one
    invoice_storno: dict[str, tuple[datetime, datetime]] = field(default_factory=dict)
    # amounts actually applied to invoices (E2 lowers them); default = allocations
    applied: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    # FX errors (E3): the rate actually used, as (rate date, source currency)
    rate_override: dict[str, tuple[date, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Row:
    key: str
    account: str
    debit: int
    credit: int
    entity: str | None
    invoice: str | None
    payment: str | None


@dataclass(frozen=True)
class Entry:
    key: str
    timestamp: datetime          # company offset; unique per entry
    kind: str                    # invoice | storno | credit | receipt | reclass | refund | expense
    doc: str | None              # invoice or payment key
    rows: tuple[Row, ...]


@dataclass
class FxGrid:
    """Full grid of business-day rates: (date, source, target) -> rate."""

    rates: dict[tuple[date, str, str], Fraction] = field(default_factory=dict)

    def pairs(self) -> list[tuple[str, str]]:
        return sorted({(s, t) for (_d, s, t) in self.rates})


@dataclass
class World:
    company: str
    base_currency: str
    offset: int                  # company offset, minutes
    bank_offset: int
    period: str
    period_start: datetime
    period_end: datetime
    window_start: datetime
    window_end: datetime
    rate_rule: str
    max_lookback_days: int
    rounding: str
    customers: list[Customer]
    fx: FxGrid
    # Diagnostics only: cap of the D23 lead before the document (None = the real
    # distribution). Re-creates the behaviour before 1.2.0 for the failure analysis.
    d23_max_lead_s: int | None = None
