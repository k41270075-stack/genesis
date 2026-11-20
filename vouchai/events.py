"""Legitimate business events, legitimate look-alikes ("doubles") and the
default posting decisions.

Every feature that an error produces also occurs in clean books:

  D1  monthly subscriptions: same lines, different service periods
  D2  an invoice paid by 2-3 payments          D3  a legitimately partial payment
  D4  overpayment to 2200 and a later refund    D5  bank fee withheld (gross amount)
  D6  weekend rate: the previous business day   D7  near-midnight payments at period
                                                     edges, UTC date in the other period
  D9  same amount, other customer, same day     D10 cancelled by a credit note, re-issued
  D12 due date in the next period               D13 allocated without a reference
  D14 storno and re-posting                     D16 advance without an invoice
  D17 two-step receipt via 2150                 D18 unidentified receipt left on 2150
  D19 one payment for 2-3 invoices              D20 a copy cancelled by a credit note
  D21 same customer, day and amount, other lines
  D23 posting a little before the document time D24 batch invoicing in one second
  D25 a long but legitimate posting delay

Each event gets a posting moment from one shared delay distribution, clipped
so a legitimate posting always stays in the zone (left margin, period, right
margin) of its event.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from datetime import datetime, timedelta
from fractions import Fraction

from .model import Customer, Decisions, Expense, Invoice, LineItem, Payment, World
from .money import exponent, round_fraction
from .rng import Stream
from .timeutil import format_date, in_offset, tz, utc_seconds

BOUNDARY_GUARD_S = 600          # events stay this far from period and window edges
MIN_GAP_S = 60                  # no timestamp closer than this to a period edge (I12)
MAX_DELAY_S = 3 * 86_400

CATALOG = (
    ("Cloud hosting", 40_000, 250_000),
    ("Support plan", 20_000, 120_000),
    ("Consulting hours", 15_000, 60_000),
    ("Software license", 60_000, 400_000),
    ("Data storage", 8_000, 50_000),
    ("Maintenance service", 25_000, 150_000),
    ("Training session", 30_000, 180_000),
    ("Analytics module", 50_000, 300_000),
    ("API usage", 5_000, 40_000),
    ("Design work", 20_000, 200_000),
)
EXPENSE_ACCOUNTS = ("6200", "6300", "6400", "6500", "6600", "6700", "6800", "6900")


def zones(world: World) -> list[tuple[datetime, datetime]]:
    return [(world.window_start, world.period_start), (world.period_start, world.period_end),
            (world.period_end, world.window_end)]


def zone_of(world: World, ts: datetime) -> tuple[datetime, datetime]:
    for lo, hi in zones(world):
        if lo <= ts < hi:
            return lo, hi
    raise ValueError("timestamp outside the export window")


def edges(world: World) -> list[datetime]:
    return [world.window_start, world.period_start, world.period_end, world.window_end]


def near_edge(world: World, ts: datetime, guard: int) -> bool:
    return any(abs(utc_seconds(ts) - utc_seconds(e)) < guard for e in edges(world))


class Clock:
    """Hands out unique posting moments that keep away from period edges."""

    def __init__(self, world: World):
        self.world = world
        self.used: set[int] = set()

    def take(self, ts: datetime) -> datetime:
        ts = in_offset(ts, self.world.offset)
        while utc_seconds(ts) in self.used or near_edge(self.world, ts, MIN_GAP_S):
            ts += timedelta(seconds=1)
        self.used.add(utc_seconds(ts))
        return ts

    def release(self, ts: datetime) -> None:
        self.used.discard(utc_seconds(ts))


def sample_delay(stream: Stream) -> int:
    """Seconds from event to posting: one distribution for everything (D25)."""
    bucket = stream.weighted(["fast", "day", "slow"], [60, 30, 10])
    if bucket == "fast":
        return stream.randint(60, 7_200)
    if bucket == "day":
        return stream.randint(7_200, 86_400)
    return stream.randint(86_400, MAX_DELAY_S)


def legit_posting(world: World, stream: Stream, event: datetime) -> datetime:
    """Posting moment in the same zone as the event (I9); sometimes a little
    before the document time (D23)."""
    lo, hi = zone_of(world, event)
    if stream.chance(Fraction(1, 8)):
        early = stream.randint(60, 7_200)
        if utc_seconds(event) - early > utc_seconds(lo) + MIN_GAP_S + 61:
            return event - timedelta(seconds=early)
    room = utc_seconds(hi) - utc_seconds(event) - MIN_GAP_S - 61
    delay = sample_delay(stream)
    if delay > room:
        delay = stream.randint(60, max(60, room))
    return event + timedelta(seconds=delay)


def _random_moment(world: World, stream: Stream, lo: datetime, hi: datetime,
                   offset: int, business_hours: bool) -> datetime:
    span = utc_seconds(hi) - utc_seconds(lo)
    while True:
        ts = in_offset(lo + timedelta(seconds=stream.randbelow(span)), offset)
        if business_hours and not 9 <= in_offset(ts, world.offset).hour < 19:
            continue
        if not near_edge(world, ts, BOUNDARY_GUARD_S):
            return ts


def nice_price(points: int, currency: str, stream: Stream) -> int:
    from .world import CURRENCY_LEVEL
    exp = exponent(currency)
    step = 10 ** max(exp, 1)
    minor = Fraction(points) / CURRENCY_LEVEL[currency] * (10 ** exp)
    units = max(1, round_fraction(minor / step, "half_even"))  # exact: Fraction
    jitter = stream.randint(0, 9) * step // 10 if exp >= 2 else 0
    return units * step + jitter


def _service_period(world: World, issued: datetime, stream: Stream | None,
                    monthly: bool) -> tuple[str, str]:
    local = in_offset(issued, world.offset).date()
    if monthly:
        first = local.replace(day=1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return format_date(first), format_date(last)
    end = local + timedelta(days=stream.randint(0, 6))   # may cross the period edge (D15)
    return format_date(local), format_date(end)


def _make_lines(items, period) -> list[LineItem]:
    return [LineItem(description=d, quantity=q, unit_price_minor=p, amount_minor=q * p,
                     service_period_start=period[0], service_period_end=period[1])
            for d, q, p in items]


class InvoiceBook:
    def __init__(self, world: World, stream: Stream):
        self.world = world
        self.stream = stream
        self.invoices: list[Invoice] = []

    def add(self, customer: Customer, issued: datetime, items, period, **extra) -> Invoice:
        key = extra.pop("key", None) or f"inv{len(self.invoices):03d}"
        lines = _make_lines(items, period)
        due_days = self.stream.child(key).choice([14, 30, 45])   # D12 when it crosses
        inv = Invoice(key=key, customer=customer.key, currency=customer.currency,
                      issued_at=issued, due_at=issued + timedelta(days=due_days), lines=lines,
                      total=sum(li.amount_minor for li in lines), **extra)
        self.invoices.append(inv)
        return inv

    def random_items(self, customer: Customer, stream: Stream):
        items = []
        for _ in range(stream.randint(1, 4)):
            desc, lo, hi = stream.choice(CATALOG)
            items.append((desc, stream.randint(1, 8),
                          nice_price(stream.randint(lo, hi), customer.currency, stream)))
        return items


def make_invoices(world: World, stream: Stream, count: int) -> list[Invoice]:
    book = InvoiceBook(world, stream)
    lo = world.window_start + timedelta(hours=2)
    hi = world.window_end - timedelta(days=1)
    customers = {c.key: c for c in world.customers}
    # D1: monthly subscriptions, same lines every month.
    for customer in [c for c in world.customers if c.subscription]:
        cs = stream.child(f"sub.{customer.key}")
        day, hour = cs.randint(1, 27), cs.randint(9, 17)
        desc, plo, phi = cs.choice(CATALOG)
        items = [(desc, cs.randint(1, 3), nice_price(cs.randint(plo, phi), customer.currency, cs))]
        month = in_offset(world.window_start, world.offset).date().replace(day=1)
        while len(book.invoices) < count * 2 // 3:
            issued = datetime(month.year, month.month, day, hour, cs.randint(0, 59),
                              cs.randint(0, 59), tzinfo=tz(world.offset))
            if issued >= hi:
                break
            if issued >= lo and not near_edge(world, issued, BOUNDARY_GUARD_S):
                book.add(customer, issued, items, _service_period(world, issued, None, True))
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

    s = stream.child("one-off")
    while len(book.invoices) < count:
        customer = s.choice(world.customers)
        issued = _random_moment(world, s, lo, hi, world.offset, business_hours=True)
        kind = s.weighted(["plain", "batch", "same_amount", "same_customer"], [64, 8, 8, 20])
        if kind == "batch":                    # D24: several invoices in one second
            for other in s.sample(world.customers, min(len(world.customers), s.randint(2, 4))):
                book.add(other, issued, book.random_items(other, s),
                         _service_period(world, issued, s, False))
            continue
        inv = book.add(customer, issued, book.random_items(customer, s),
                       _service_period(world, issued, s, False))
        if kind == "same_amount":              # D9: another customer, same day and amount
            twins = [c for c in world.customers
                     if c.key != customer.key and c.currency == customer.currency]
            if twins:
                other = s.choice(twins)
                later = issued + timedelta(minutes=s.randint(5, 120))
                if not near_edge(world, later, BOUNDARY_GUARD_S) and later < hi:
                    book.add(other, later, [(s.choice(CATALOG)[0], 1, inv.total)],
                             _service_period(world, later, s, False))
        elif kind == "same_customer":          # D21: same customer, day, amount; other lines
            later = issued + timedelta(minutes=s.randint(5, 120))
            desc = s.choice([c[0] for c in CATALOG if c[0] != inv.lines[0].description])
            if not near_edge(world, later, BOUNDARY_GUARD_S) and later < hi:
                book.add(customers[inv.customer], later, [(desc, 1, inv.total)],
                         _service_period(world, later, s, False))
    book.invoices.sort(key=lambda inv: (utc_seconds(inv.issued_at), inv.key))
    return book.invoices


def _split(stream: Stream, total: int, parts: int, step: int) -> list[int]:
    if parts == 1 or total < parts * step * 2:
        return [total]
    cuts = sorted(stream.sample(range(1, total // step), parts - 1))
    points = [0] + [c * step for c in cuts] + [total]
    amounts = [b - a for a, b in zip(points, points[1:])]
    return amounts if all(a > 0 for a in amounts) else [total]


def _partial(stream: Stream, total: int, step: int) -> int | None:
    share = Fraction(stream.randint(30, 70), 100)
    units = round_fraction(total * share / step, "half_even")  # exact
    amount = max(step, units * step)
    return amount if amount < total else None


def _trap_moments(world: World, stream: Stream) -> list[datetime]:
    """Bank moments whose UTC date lies in the neighbouring period (D7/D7b, X1 targets)."""
    off = world.offset
    if off == 0:
        return []
    guard = BOUNDARY_GUARD_S
    if off > 0:     # first hours of the period: UTC is still in the previous period
        lo, hi = utc_seconds(world.period_start) + guard, utc_seconds(world.period_start) + \
            off * 60 - guard
    else:           # last hours of the period: UTC is already in the next period
        lo, hi = utc_seconds(world.period_end) + off * 60 + guard, \
            utc_seconds(world.period_end) - guard
    if hi <= lo:
        return []
    base = world.period_start if off > 0 else world.period_end
    return [in_offset(base + timedelta(seconds=stream.randint(lo, hi) - utc_seconds(base)),
                      world.bank_offset) for _ in range(4)]


def make_payments(world: World, stream: Stream, invoices: list[Invoice]) -> list[Payment]:
    payments: list[Payment] = []
    last_moment = world.window_end - timedelta(days=1)
    base = world.base_currency
    counter = itertools.count()

    def add(customer: str, currency: str, moment: datetime, amount: int, fee: int,
            allocations, **extra) -> Payment:
        p = Payment(key=f"pay{next(counter):03d}", customer=customer, currency=currency,
                    timestamp=in_offset(moment, world.bank_offset), amount=amount, fee=fee,
                    allocations=allocations, **extra)
        payments.append(p)
        return p

    def ok(moment: datetime) -> bool:
        return moment < last_moment and not near_edge(world, moment, BOUNDARY_GUARD_S)

    regular = [inv for inv in invoices if not inv.is_credit_note]
    # D7/D7b traps: a partial two-step payment at the edge, UTC date in the other period.
    s_trap = stream.child("traps")
    trap_targets = [inv for inv in regular if inv.currency != base and inv.copy_of is None
                    and inv.replaces is None]
    planned_open: set[str] = set()
    for moment in _trap_moments(world, s_trap):
        options = [inv for inv in trap_targets if inv.key not in planned_open
                   and utc_seconds(inv.issued_at) + 5 * 86_400 < utc_seconds(moment)]
        if not options:
            continue
        inv = s_trap.choice(options)
        amount = _partial(s_trap, inv.total, 10 ** exponent(inv.currency))
        if amount and ok(moment):
            add(inv.customer, inv.currency, moment, amount, 0, [(inv.key, amount)],
                mode="two_step")
            planned_open.add(inv.key)

    s_plan = stream.child("plans")
    full_single: list[Payment] = []
    for inv in regular:
        if inv.key in planned_open:
            continue
        s = s_plan.child(inv.key)
        plan = s.weighted(["open", "full", "partial", "split", "overpay"], [24, 44, 10, 17, 5])
        step = 10 ** exponent(inv.currency)
        if plan == "overpay" and inv.currency != base:
            plan = "full"
        if plan == "open":
            continue
        if plan in ("full", "overpay"):
            amounts = [inv.total]
        elif plan == "partial":                # D3
            amounts = [_partial(s, inv.total, step) or inv.total]
        else:                                  # D2
            amounts = _split(s, inv.total, s.randint(2, 3), step)
        moment = inv.issued_at
        for amount in amounts:
            # >= 4 days: the invoice posting (delay <= 3 days) always comes first.
            moment = moment + timedelta(days=s.randint(4, 20), seconds=s.randbelow(86_400))
            if not ok(moment):
                break
            fee = 0
            if inv.currency != base and s.chance(Fraction(1, 3)):   # D5
                fee = max(1, amount * s.randint(2, 15) // 1000)
            if plan == "overpay":              # D4: overpayment to 2200, refunded later
                extra = nice_price(s.randint(2_000, 30_000), base, s)
                add(inv.customer, base, moment, amount + extra, 0, [(inv.key, amount)],
                    excess_account="2200")
                # >= 4 days: the overpayment (delay <= 3 days) is always posted first (I18)
                refund_at = moment + timedelta(days=s.randint(4, 10), seconds=s.randbelow(86_400))
                if ok(refund_at):
                    add(inv.customer, base, refund_at, -extra, 0, [], excess_account="2200")
                break
            mode = "two_step" if s.chance(Fraction(7, 20)) else "direct"     # D17
            p = add(inv.customer, inv.currency, moment, amount, fee, [(inv.key, amount)],
                    mode=mode)
            if plan == "full" and fee == 0 and mode == "direct":
                full_single.append(p)

    # D19: merge some single full payments of one customer into one payment.
    s_merge = stream.child("merge")
    groups: dict[tuple[str, str], list[Payment]] = defaultdict(list)
    for p in full_single:
        groups[(p.customer, p.currency)].append(p)
    for (_cust, _cur), group in sorted(groups.items()):
        if len(group) >= 2 and s_merge.chance(Fraction(1, 2)):
            chosen = group[: s_merge.randint(2, min(3, len(group)))]
            latest = max(chosen, key=lambda p: utc_seconds(p.timestamp))
            latest.allocations = [a for p in chosen for a in p.allocations]
            latest.amount = sum(a for _, a in latest.allocations)
            for p in chosen:
                if p is not latest:
                    payments.remove(p)

    # D13: allocated without a reference when the amount equals the only open invoice.
    s13 = stream.child("noref")
    per_customer: dict[tuple[str, str], list[Invoice]] = defaultdict(list)
    for inv in regular:
        per_customer[(inv.customer, inv.currency)].append(inv)
    for p in payments:
        if (len(p.allocations) == 1 and p.amount == p.allocations[0][1] and p.fee == 0
                and len(per_customer[(p.customer, p.currency)]) == 1
                and p.amount == per_customer[(p.customer, p.currency)][0].total
                and s13.chance(Fraction(1, 2))):
            p.public_refs = False
            p.mode = "two_step"

    # D16 advances (base currency, to 2200) and D18 unidentified receipts (stay on 2150).
    s_misc = stream.child("misc")
    lo, hi = world.window_start + timedelta(hours=2), last_moment
    base_customers = [c for c in world.customers if c.currency == base]
    for _ in range(s_misc.randint(0, 2)):
        if base_customers:
            c = s_misc.choice(base_customers)
            moment = _random_moment(world, s_misc, lo, hi, world.bank_offset, False)
            add(c.key, base, moment, nice_price(s_misc.randint(10_000, 200_000), base, s_misc),
                0, [], excess_account="2200")
    for _ in range(s_misc.randint(0, 2)):
        c = s_misc.choice(world.customers)
        moment = _random_moment(world, s_misc, lo, hi, world.bank_offset, False)
        add(c.key, c.currency, moment,
            nice_price(s_misc.randint(10_000, 200_000), c.currency, s_misc), 0, [],
            excess_account="2150")
    payments.sort(key=lambda p: (utc_seconds(p.timestamp), p.key))
    return payments


def add_cancellations(world: World, stream: Stream, invoices: list[Invoice],
                      payments: list[Payment]) -> list[Invoice]:
    """D10 (cancel + re-issue) and D20 (a copy cancelled by a credit note)."""
    paid = {k for p in payments for k, _ in p.allocations}
    last = world.window_end - timedelta(days=1)
    out = list(invoices)
    n_cn = 0
    candidates = [inv for inv in invoices if inv.key not in paid and not inv.is_credit_note]
    for kind in ("reissue", "copy"):
        if not candidates or not stream.child(kind).chance(Fraction(2, 3)):
            continue
        s = stream.child(kind)
        inv = s.choice(candidates)
        candidates.remove(inv)
        when = inv.issued_at + timedelta(days=s.randint(4, 8), minutes=s.randint(0, 600))
        if when >= last or near_edge(world, when, BOUNDARY_GUARD_S):
            continue
        if kind == "copy" and zone_of(world, when) != zone_of(world, inv.issued_at):
            # a copy cancelled only in the next period is a real misstatement at period
            # end (IAS 10.9(e)); a legitimate D20 cancels in the same period
            continue
        target = inv
        if kind == "copy":                     # D20: the copy is cancelled, net zero
            target = Invoice(key=f"{inv.key}c", customer=inv.customer, currency=inv.currency,
                             issued_at=inv.issued_at, due_at=inv.due_at, lines=list(inv.lines),
                             total=inv.total, copy_of=inv.key)
            out.append(target)
        out.append(Invoice(key=f"cn{n_cn:03d}", customer=inv.customer, currency=inv.currency,
                           issued_at=when, due_at=when, lines=list(target.lines),
                           total=target.total, credit_for=target.key))
        n_cn += 1
        if kind == "reissue":                  # D10: re-issued with changed quantities
            first = inv.lines[0]
            items = [(first.description, first.quantity + 1, first.unit_price_minor)] + \
                [(li.description, li.quantity, li.unit_price_minor) for li in inv.lines[1:]]
            period = _service_period(world, when, s, False)
            lines = _make_lines(items, period)
            out.append(Invoice(key=f"{inv.key}r", customer=inv.customer, currency=inv.currency,
                               issued_at=when + timedelta(minutes=5),
                               due_at=when + timedelta(days=30), lines=lines,
                               total=sum(li.amount_minor for li in lines), replaces=inv.key))
    out.sort(key=lambda inv: (utc_seconds(inv.issued_at), inv.key))
    return out


def make_expenses(world: World, stream: Stream, count: int) -> list[Expense]:
    expenses = []
    lo = world.window_start + timedelta(hours=2)
    hi = world.window_end - timedelta(hours=2)
    for i in range(count):
        ts = _random_moment(world, stream, lo, hi, world.offset, business_hours=True)
        amount = nice_price(stream.randint(5_000, 300_000), world.base_currency, stream)
        expenses.append(Expense(key=f"exp{i:03d}", timestamp=ts,
                                account=stream.choice(EXPENSE_ACCOUNTS), amount=amount))
    return expenses


def default_decisions(world: World, stream: Stream, clock: Clock, invoices: list[Invoice],
                      payments: list[Payment]) -> Decisions:
    decisions = Decisions()
    s_storno = stream.child("storno")
    paid = {k for p in payments for k, _ in p.allocations}
    cancelled = {i.credit_for for i in invoices if i.credit_for}
    for inv in invoices:
        s = stream.child(inv.key)
        if (not inv.is_credit_note and inv.copy_of is None and inv.key not in paid
                and inv.key not in cancelled and world.period_start
                <= inv.issued_at < world.period_end and s_storno.chance(Fraction(1, 25))):
            lo, hi = zone_of(world, inv.issued_at)
            wrong = inv.issued_at + timedelta(seconds=s.randint(60, 3_600))
            reverse = wrong + timedelta(seconds=s.randint(600, 86_400))
            right = reverse + timedelta(seconds=s.randint(60, 7_200))
            if utc_seconds(right) < utc_seconds(hi) - MIN_GAP_S - 121:   # D14
                decisions.invoice_storno[inv.key] = (clock.take(wrong), clock.take(reverse))
                decisions.invoice_postings[inv.key] = [clock.take(right)]
                continue
        decisions.invoice_postings[inv.key] = [clock.take(legit_posting(world, s, inv.issued_at))]
    for pay in payments:
        s = stream.child(pay.key)
        ts = clock.take(legit_posting(world, s, pay.timestamp))
        decisions.payment_posting[pay.key] = ts
        if pay.mode == "two_step" and pay.allocations:
            reclass = ts + timedelta(seconds=s.randint(600, MAX_DELAY_S))
            limit = world.window_end - timedelta(seconds=BOUNDARY_GUARD_S)
            if reclass >= limit:
                room = (utc_seconds(limit) - utc_seconds(ts)) // 2
                reclass = ts + timedelta(seconds=max(61, room))
            decisions.reclass_posting[pay.key] = clock.take(reclass)
    return decisions
