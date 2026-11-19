"""Posting engine and accounting invariants.

The engine turns documents plus posting decisions into ledger entries in the
base currency. Errors never edit rows: they change a decision and the engine
re-posts, so every consequence stays consistent and each error has exactly one
carrier row.

Rules (PLAN 5.3):
  invoice T       Dr 1200 A / Cr 4000 A,  A = conv(T, policy rate of the issue date)
  receipt P       Dr 1010 (conv(P) - conv(fee)), Dr 6100 conv(fee)
                  / Cr 1200 relief per allocation, Cr 2150 conv(unapplied),
                  +/- one 7100 line for the difference (none if zero)
  relief of a     round(a * A / T); the closing relief (the event that makes
                  the applied sum reach T, ordered by event time) takes A - prior reliefs
  expense E       Dr 62xx / Cr 1010 (base currency)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from .model import Decisions, Entry, Expense, Invoice, Payment, Row, World
from .money import conv, pro_rata
from .timeutil import in_offset, local_date, utc_seconds
from .world import rate_for

CHART_OF_ACCOUNTS = {
    "1010": "Bank",
    "1200": "Accounts receivable",
    "2150": "Unapplied receipts",
    "2200": "Customer advances",
    "3000": "Opening balance equity",
    "4000": "Revenue",
    "4100": "Sales returns",
    "6100": "Bank charges",
    "6200": "Rent", "6300": "Salaries", "6400": "Utilities", "6500": "Marketing",
    "6600": "Travel", "6700": "Office supplies", "6800": "Software subscriptions",
    "6900": "Other operating expenses",
    "7100": "Realized FX gain/loss",
}


class PostingError(ValueError):
    """The decisions cannot be posted consistently (a generator bug)."""


def _row(entry_key: str, n: int, account: str, debit: int, credit: int, entity, invoice,
         payment) -> Row:
    if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
        raise PostingError(f"row {entry_key}/{n}: exactly one positive side required")
    return Row(key=f"{entry_key}/{n}", account=account, debit=debit, credit=credit,
               entity=entity, invoice=invoice, payment=payment)


def booked_amount(world: World, inv: Invoice) -> int:
    rate, _ = rate_for(world, inv.currency, local_date(inv.issued_at, world.offset))
    return conv(inv.total, rate, inv.currency, world.base_currency, world.rounding)


def receipt_amounts(world: World, pay: Payment) -> tuple[int, int]:
    """(conv(gross), conv(fee)) at the policy rate of the payment's local date."""
    rate, _ = rate_for(world, pay.currency, local_date(pay.timestamp, world.offset))
    gross = conv(pay.amount, rate, pay.currency, world.base_currency, world.rounding)
    fee = conv(pay.fee, rate, pay.currency, world.base_currency, world.rounding)
    return gross, fee


def post(world: World, invoices: Iterable[Invoice], payments: Iterable[Payment],
         expenses: Iterable[Expense], decisions: Decisions) -> list[Entry]:
    invoices = list(invoices)
    by_key = {inv.key: inv for inv in invoices}
    entries: list[Entry] = []

    booked: dict[str, int] = {}
    for inv in invoices:
        amount = booked_amount(world, inv)
        booked[inv.key] = amount
        for n, ts in enumerate(decisions.invoice_postings[inv.key]):
            key = f"{inv.key}/post{n}"
            entries.append(Entry(key=key, timestamp=ts, kind="invoice", doc=inv.key, rows=(
                _row(key, 0, "1200", amount, 0, inv.customer, inv.key, None),
                _row(key, 1, "4000", 0, amount, inv.customer, inv.key, None),
            )))

    applied: dict[str, int] = defaultdict(int)
    relieved: dict[str, int] = defaultdict(int)
    for pay in sorted(payments, key=lambda p: (utc_seconds(p.timestamp), p.key)):
        key = f"{pay.key}/recv"
        gross, fee = receipt_amounts(world, pay)
        rows: list[Row] = []
        n = 0
        rows.append(_row(key, n, "1010", gross - fee, 0, pay.customer, None, pay.key))
        n += 1
        if fee:
            rows.append(_row(key, n, "6100", fee, 0, pay.customer, None, pay.key))
            n += 1
        credits = 0
        allocated = 0
        for inv_key, amount in pay.allocations:
            inv = by_key[inv_key]
            if amount <= 0 or applied[inv_key] + amount > inv.total:
                raise PostingError(f"{pay.key}: allocation exceeds the open amount of {inv_key}")
            applied[inv_key] += amount
            allocated += amount
            if applied[inv_key] == inv.total:
                relief = booked[inv_key] - relieved[inv_key]
            else:
                relief = pro_rata(amount, booked[inv_key], inv.total, world.rounding)
            relieved[inv_key] += relief
            rows.append(_row(key, n, "1200", 0, relief, pay.customer, inv_key, pay.key))
            n += 1
            credits += relief
        if allocated > pay.amount:
            raise PostingError(f"{pay.key}: allocations exceed the payment")
        unapplied = pay.amount - allocated
        if unapplied:
            rate, _ = rate_for(world, pay.currency, local_date(pay.timestamp, world.offset))
            unapplied_base = conv(unapplied, rate, pay.currency, world.base_currency,
                                  world.rounding)
            rows.append(_row(key, n, "2150", 0, unapplied_base, pay.customer, None, pay.key))
            n += 1
            credits += unapplied_base
        diff = gross - credits
        if diff > 0:
            rows.append(_row(key, n, "7100", 0, diff, pay.customer, None, pay.key))
        elif diff < 0:
            rows.append(_row(key, n, "7100", -diff, 0, pay.customer, None, pay.key))
        entries.append(Entry(key=key, timestamp=decisions.payment_posting[pay.key],
                             kind="receipt", doc=pay.key, rows=tuple(rows)))

    for exp in expenses:
        key = exp.key
        entries.append(Entry(key=key, timestamp=in_offset(exp.timestamp, world.offset),
                             kind="expense", doc=None, rows=(
                                 _row(key, 0, exp.account, exp.amount, 0, None, None, None),
                                 _row(key, 1, "1010", 0, exp.amount, None, None, None),
                             )))
    entries.sort(key=lambda e: (utc_seconds(e.timestamp), e.key))
    return entries


# ---------------------------------------------------------------- invariants

def period_index(world: World, ts: datetime) -> int:
    """-1 left margin, 0 the period, 1 right margin (company time)."""
    if ts < world.period_start:
        return -1
    if ts < world.period_end:
        return 0
    return 1


def check_invariants(world: World, invoices: list[Invoice], payments: list[Payment],
                     entries: list[Entry]) -> list[str]:
    """Return violated invariants of clean books (empty list = all hold)."""
    problems: list[str] = []
    debit = sum(r.debit for e in entries for r in e.rows)
    credit = sum(r.credit for e in entries for r in e.rows)
    if debit != credit:
        problems.append("I1: total debit != total credit")
    moments = [utc_seconds(e.timestamp) for e in entries]
    if len(moments) != len(set(moments)):
        problems.append("I2: two entries share a timestamp")
    for e in entries:
        if sum(r.debit for r in e.rows) != sum(r.credit for r in e.rows):
            problems.append(f"I2: entry {e.key} is unbalanced")
        for r in e.rows:
            if (r.debit > 0) == (r.credit > 0) or r.account not in CHART_OF_ACCOUNTS:
                problems.append(f"I14: row {r.key}")
        if sum(1 for r in e.rows if r.account == "7100") > 1:
            problems.append(f"I5: entry {e.key} has more than one 7100 line")
        if any(abs(utc_seconds(e.timestamp) - utc_seconds(b)) < 60
               for b in (world.period_start, world.period_end)):
            problems.append(f"I12: entry {e.key} within 60 s of a period edge")
        if not world.window_start <= e.timestamp < world.window_end:
            problems.append(f"I15: entry {e.key} outside the export window")

    by_doc: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        if e.doc:
            by_doc[e.doc].append(e)
    for inv in invoices:
        if inv.total != sum(li.amount_minor for li in inv.lines) or any(
                li.amount_minor != li.quantity * li.unit_price_minor for li in inv.lines):
            problems.append(f"I13: invoice {inv.key} totals")
        posts = by_doc.get(inv.key, [])
        if len(posts) != 1:
            problems.append(f"I15: invoice {inv.key} posted {len(posts)} times")
            continue
        dr = sum(r.debit for r in posts[0].rows if r.account == "1200")
        if dr != booked_amount(world, inv):
            problems.append(f"I3: invoice {inv.key} booked {dr}")
        if period_index(world, posts[0].timestamp) != period_index(world, inv.issued_at):
            problems.append(f"I9: invoice {inv.key} posted in another period")
    relieved: dict[str, int] = defaultdict(int)
    applied: dict[str, int] = defaultdict(int)
    for pay in payments:
        posts = by_doc.get(pay.key, [])
        if len(posts) != 1:
            problems.append(f"I15: payment {pay.key} posted {len(posts)} times")
            continue
        gross, _fee = receipt_amounts(world, pay)
        cash = sum(r.debit for r in posts[0].rows if r.account in ("1010", "6100"))
        if cash != gross:
            problems.append(f"I4: payment {pay.key}")
        if period_index(world, posts[0].timestamp) != period_index(world, pay.timestamp):
            problems.append(f"I9: payment {pay.key} posted in another period")
        for r in posts[0].rows:
            if r.account == "1200":
                relieved[r.invoice] += r.credit
        for inv_key, amount in pay.allocations:
            applied[inv_key] += amount
    by_key = {inv.key: inv for inv in invoices}
    for inv_key, amount in applied.items():
        inv = by_key[inv_key]
        if amount > inv.total:
            problems.append(f"I17: invoice {inv_key} over-applied")
        remaining = booked_amount(world, inv) - relieved[inv_key]
        if remaining < 0 or (amount == inv.total and remaining != 0):
            problems.append(f"I6: invoice {inv_key} AR balance {remaining}")
    return problems
