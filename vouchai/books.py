"""Posting engine and accounting invariants.

The engine turns documents plus posting decisions into ledger entries in the
base currency. Errors never edit rows: they change a decision and the engine
re-posts, so every consequence stays consistent and each error has exactly one
carrier row (or one carrier equation).

Rules (PLAN 5.3):
  invoice T        Dr 1200 A / Cr 4000 A,  A = conv(T, policy rate of the issue date)
  storno (D14)     wrong posting, mirror reversal, right posting - all in one period
  credit note      Dr 4100 / Cr 1200 of the remaining booked amount (full cancellation)
  receipt, direct  Dr 1010 (conv(P) - conv(fee)), Dr 6100 conv(fee)
                   / Cr 1200 relief per applied allocation, Cr 2150 conv(unapplied part),
                   Cr 2150|2200 conv(excess), +/- one 7100 line (none if zero)
  receipt, 2-step  1) Dr 1010, Dr 6100 / Cr 2150 conv(P)
                   2) Dr 2150 X / Cr 1200 reliefs +/- 7100,  X = conv(P) if all of P is
                      applied, otherwise conv(applied part)
  refund           Dr 2200 / Cr 1010 (base currency only)
  relief of a      round(a * A / T); the closing relief (the event that makes the
                   applied sum reach T, ordered by event time) takes A - prior reliefs
  expense E        Dr 62xx / Cr 1010 (base currency)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from fractions import Fraction

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


class _Rows:
    def __init__(self, entry_key: str):
        self.key = entry_key
        self.rows: list[Row] = []

    def add(self, account: str, debit: int, credit: int, entity=None, invoice=None,
            payment=None) -> None:
        if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
            raise PostingError(f"row {self.key}/{len(self.rows)}: one positive side required")
        self.rows.append(Row(key=f"{self.key}/{len(self.rows)}", account=account, debit=debit,
                             credit=credit, entity=entity, invoice=invoice, payment=payment))

    def side(self, account: str, amount: int, **refs) -> None:
        """Credit a positive amount, debit a negative one; nothing for zero."""
        if amount > 0:
            self.add(account, 0, amount, **refs)
        elif amount < 0:
            self.add(account, -amount, 0, **refs)


def doc_rate(world: World, decisions: Decisions | None, key: str, currency: str,
             event: datetime) -> Fraction:
    if currency == world.base_currency:
        return Fraction(1)
    if decisions is not None and key in decisions.rate_override:
        d, source = decisions.rate_override[key]
        return world.fx.rates[(d, source, world.base_currency)]
    return rate_for(world, currency, local_date(event, world.offset))[0]


def booked_amount(world: World, inv: Invoice, decisions: Decisions | None = None) -> int:
    rate = doc_rate(world, decisions, inv.key, inv.currency, inv.issued_at)
    return conv(inv.total, rate, inv.currency, world.base_currency, world.rounding)


def receipt_amounts(world: World, pay: Payment,
                    decisions: Decisions | None = None) -> tuple[int, int, Fraction]:
    """(conv(gross), conv(fee), rate) at the rate the books use for this payment."""
    rate = doc_rate(world, decisions, pay.key, pay.currency, pay.timestamp)
    gross = conv(pay.amount, rate, pay.currency, world.base_currency, world.rounding)
    fee = conv(pay.fee, rate, pay.currency, world.base_currency, world.rounding)
    return gross, fee, rate


def post(world: World, invoices: Iterable[Invoice], payments: Iterable[Payment],
         expenses: Iterable[Expense], decisions: Decisions) -> list[Entry]:
    invoices = list(invoices)
    by_key = {inv.key: inv for inv in invoices}
    entries: list[Entry] = []

    booked: dict[str, int] = {}
    for inv in invoices:
        if inv.is_credit_note:
            continue
        amount = booked_amount(world, inv, decisions)
        booked[inv.key] = amount
        if inv.key in decisions.invoice_storno:
            wrong, reverse = decisions.invoice_storno[inv.key]
            for key, ts, kind, dr, cr in ((f"{inv.key}/wrong", wrong, "invoice", "1200", "4000"),
                                          (f"{inv.key}/storno", reverse, "storno", "4000", "1200")):
                r = _Rows(key)
                r.add(dr, amount, 0, inv.customer, inv.key)
                r.add(cr, 0, amount, inv.customer, inv.key)
                entries.append(Entry(key, ts, kind, inv.key, tuple(r.rows)))
        for n, ts in enumerate(decisions.invoice_postings[inv.key]):
            key = f"{inv.key}/post{n}"
            r = _Rows(key)
            r.add("1200", amount, 0, inv.customer, inv.key)
            r.add("4000", 0, amount, inv.customer, inv.key)
            entries.append(Entry(key, ts, "invoice", inv.key, tuple(r.rows)))

    applied_doc: dict[str, int] = defaultdict(int)
    relieved: dict[str, int] = defaultdict(int)

    def relief(inv_key: str, amount: int, who: str) -> int:
        inv = by_key[inv_key]
        if amount <= 0 or applied_doc[inv_key] + amount > inv.total:
            raise PostingError(f"{who}: application exceeds the open amount of {inv_key}")
        applied_doc[inv_key] += amount
        if applied_doc[inv_key] == inv.total:
            value = booked[inv_key] - relieved[inv_key]
        else:
            value = pro_rata(amount, booked[inv_key], inv.total, world.rounding)
        relieved[inv_key] += value
        return value

    events: list[tuple[int, str, object]] = []
    for inv in invoices:
        if inv.is_credit_note:
            events.append((utc_seconds(inv.issued_at), inv.key, inv))
    for pay in payments:
        events.append((utc_seconds(pay.timestamp), pay.key, pay))
    events.sort(key=lambda e: (e[0], e[1]))

    for _, _, obj in events:
        if isinstance(obj, Invoice):           # credit note: full cancellation
            cn = obj
            target = cn.credit_for
            value = relief(target, cn.total, cn.key)
            key = f"{cn.key}/post0"
            r = _Rows(key)
            r.add("4100", value, 0, cn.customer, cn.key)
            r.add("1200", 0, value, cn.customer, target)
            entries.append(Entry(key, decisions.invoice_postings[cn.key][0], "credit", cn.key,
                                 tuple(r.rows)))
            continue
        pay = obj
        entries.extend(_post_payment(world, pay, decisions, relief))

    for exp in expenses:
        r = _Rows(exp.key)
        r.add(exp.account, exp.amount, 0)
        r.add("1010", 0, exp.amount)
        entries.append(Entry(exp.key, in_offset(exp.timestamp, world.offset), "expense", None,
                             tuple(r.rows)))
    entries.sort(key=lambda e: (utc_seconds(e.timestamp), e.key))
    return entries


def _post_payment(world: World, pay: Payment, decisions: Decisions, relief) -> list[Entry]:
    key = f"{pay.key}/recv"
    ts = decisions.payment_posting[pay.key]
    refs = {"entity": pay.customer, "payment": pay.key}
    gross, fee, rate = receipt_amounts(world, pay, decisions)

    if pay.amount < 0:                         # refund of an advance or overpayment
        if pay.currency != world.base_currency or pay.allocations:
            raise PostingError(f"{pay.key}: refunds are base-currency only, without allocations")
        r = _Rows(key)
        r.add("2200", -gross, 0, **refs)
        r.add("1010", 0, -gross, **refs)
        return [Entry(key, ts, "refund", pay.key, tuple(r.rows))]

    applied = decisions.applied.get(pay.key, pay.allocations)
    alloc_total = sum(a for _, a in pay.allocations)
    applied_total = sum(a for _, a in applied)
    excess = pay.amount - alloc_total
    shortfall = alloc_total - applied_total
    if excess < 0 or shortfall < 0:
        raise PostingError(f"{pay.key}: allocations exceed the payment")
    if excess and pay.excess_account == "2200" and pay.currency != world.base_currency:
        raise PostingError(f"{pay.key}: advances and overpayments are base-currency only")

    def part(amount: int) -> int:
        return conv(amount, rate, pay.currency, world.base_currency, world.rounding)

    r = _Rows(key)
    r.add("1010", gross - fee, 0, **refs)
    if fee:
        r.add("6100", fee, 0, **refs)
    if pay.mode == "direct":
        credits = 0
        for inv_key, amount in applied:
            value = relief(inv_key, amount, pay.key)
            r.add("1200", 0, value, pay.customer, inv_key, pay.key)
            credits += value
        if shortfall:
            r.add("2150", 0, part(shortfall), **refs)
            credits += part(shortfall)
        if excess:
            r.add(pay.excess_account, 0, part(excess), **refs)
            credits += part(excess)
        r.side("7100", gross - credits, **refs)
        return [Entry(key, ts, "receipt", pay.key, tuple(r.rows))]

    if excess:
        raise PostingError(f"{pay.key}: two-step receipts cannot carry an excess")
    r.add("2150", 0, gross, **refs)
    out = [Entry(key, ts, "receipt", pay.key, tuple(r.rows))]
    if applied_total:
        rkey = f"{pay.key}/reclass"
        x = gross if applied_total == pay.amount else part(applied_total)
        rr = _Rows(rkey)
        rr.add("2150", x, 0, **refs)
        credits = 0
        for inv_key, amount in applied:
            value = relief(inv_key, amount, pay.key)
            rr.add("1200", 0, value, pay.customer, inv_key, pay.key)
            credits += value
        rr.side("7100", x - credits, **refs)
        out.append(Entry(rkey, decisions.reclass_posting[pay.key], "reclass", pay.key,
                         tuple(rr.rows)))
    return out


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
    if sum(r.debit for e in entries for r in e.rows) != sum(r.credit for e in entries
                                                            for r in e.rows):
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
    by_key = {inv.key: inv for inv in invoices}
    for inv in invoices:
        if inv.total != sum(li.amount_minor for li in inv.lines) or any(
                li.amount_minor != li.quantity * li.unit_price_minor for li in inv.lines):
            problems.append(f"I13: invoice {inv.key} totals")
        posts = by_doc.get(inv.key, [])
        if not posts:
            problems.append(f"I15: document {inv.key} is not posted")
            continue
        for e in posts:
            if period_index(world, e.timestamp) != period_index(world, inv.issued_at):
                problems.append(f"I9: {e.key} posted in another period")
        if inv.is_credit_note:
            continue
        net = sum(r.debit - r.credit for e in posts for r in e.rows
                  if r.account == "1200" and e.kind in ("invoice", "storno"))
        if net != booked_amount(world, inv):
            problems.append(f"I3: invoice {inv.key} net booked {net}")

    relieved: dict[str, int] = defaultdict(int)
    applied: dict[str, int] = defaultdict(int)
    for e in entries:
        if e.kind in ("receipt", "reclass", "credit"):
            for r in e.rows:
                if r.account == "1200":
                    relieved[r.invoice] += r.credit
    for inv in invoices:
        if inv.is_credit_note:
            applied[inv.credit_for] += inv.total
    for pay in payments:
        posts = [e for e in by_doc.get(pay.key, []) if e.kind in ("receipt", "refund")]
        if len(posts) != 1:
            problems.append(f"I15: payment {pay.key} posted {len(posts)} times")
            continue
        gross, _fee, _ = receipt_amounts(world, pay)
        if pay.amount > 0:
            cash = sum(r.debit for r in posts[0].rows if r.account in ("1010", "6100"))
            if cash != gross:
                problems.append(f"I4: payment {pay.key}")
        if period_index(world, posts[0].timestamp) != period_index(world, pay.timestamp):
            problems.append(f"I9: payment {pay.key} posted in another period")
        for inv_key, amount in pay.allocations:
            applied[inv_key] += amount
            if by_key[inv_key].currency != pay.currency:
                problems.append(f"I17: payment {pay.key} currency")
        if pay.allocations:
            on_2150 = sum(r.credit - r.debit for e in by_doc[pay.key] for r in e.rows
                          if r.account == "2150")
            if on_2150 != 0:
                problems.append(f"I8: payment {pay.key} leaves {on_2150} on 2150")
    for inv_key, amount in applied.items():
        inv = by_key[inv_key]
        if amount > inv.total:
            problems.append(f"I17: invoice {inv_key} over-applied")
        remaining = booked_amount(world, inv) - relieved[inv_key]
        if remaining < 0 or (amount == inv.total and remaining != 0):
            problems.append(f"I6: invoice {inv_key} AR balance {remaining}")

    balance: dict[str, int] = defaultdict(int)
    for e in entries:
        for r in e.rows:
            if r.account == "2200":
                balance[r.entity] += r.credit - r.debit
                if balance[r.entity] < 0:
                    problems.append(f"I18: customer {r.entity} advances below zero")
    return problems
