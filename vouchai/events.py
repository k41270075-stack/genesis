"""Legitimate business events and their default posting decisions.

Invoices (one-off and monthly subscriptions), customer receipts (full,
partial, split into 2-3 payments, with or without a bank fee) and operating
expenses as noise. Each event gets a posting moment from one shared delay
distribution, clipped so that a legitimate posting always stays in the same
zone (left margin, period, right margin) as its event.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from fractions import Fraction

from .model import Customer, Decisions, Expense, Invoice, LineItem, Payment, World
from .money import exponent, round_fraction
from .rng import Stream
from .timeutil import format_date, in_offset, tz, utc_seconds
from .world import CURRENCY_LEVEL

BOUNDARY_GUARD_S = 600          # events stay this far from period and window edges
MIN_GAP_S = 60                  # no timestamp closer than this to a period edge (I12)

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
    """Seconds from event to posting: one distribution for everything."""
    bucket = stream.weighted(["fast", "day", "slow"], [60, 30, 10])
    if bucket == "fast":
        return stream.randint(60, 7_200)
    if bucket == "day":
        return stream.randint(7_200, 86_400)
    return stream.randint(86_400, 3 * 86_400)


def legit_posting(world: World, stream: Stream, event: datetime) -> datetime:
    """Posting moment in the same zone as the event (I9)."""
    lo, hi = zone_of(world, event)
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


def _nice_price(points: int, currency: str, stream: Stream) -> int:
    exp = exponent(currency)
    step = 10 ** max(exp, 1)
    minor = Fraction(points) / CURRENCY_LEVEL[currency] * (10 ** exp)
    units = max(1, round_fraction(minor / step, "half_even"))  # exact: Fraction
    jitter = stream.randint(0, 9) * step // 10 if exp >= 2 else 0
    return units * step + jitter


def _lines(stream: Stream, customer: Customer, issued: datetime, world: World,
           fixed: list[tuple[str, int, int]] | None) -> list[LineItem]:
    local = in_offset(issued, world.offset)
    if fixed is not None:
        first = local.date().replace(day=1)
        nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = nxt - timedelta(days=1)
        period = (format_date(first), format_date(last))
        items = fixed
    else:
        start = local.date()
        end = start + timedelta(days=stream.randint(0, 6))
        period = (format_date(start), format_date(end))
        items = []
        for _ in range(stream.randint(1, 4)):
            desc, lo, hi = stream.choice(CATALOG)
            items.append((desc, stream.randint(1, 8),
                          _nice_price(stream.randint(lo, hi), customer.currency, stream)))
    return [LineItem(description=d, quantity=q, unit_price_minor=p, amount_minor=q * p,
                     service_period_start=period[0], service_period_end=period[1])
            for d, q, p in items]


def make_invoices(world: World, stream: Stream, count: int) -> list[Invoice]:
    invoices: list[Invoice] = []
    lo = world.window_start + timedelta(hours=2)
    hi = world.window_end - timedelta(days=1)
    subs = [c for c in world.customers if c.subscription]

    def add(customer: Customer, issued: datetime, fixed) -> None:
        key = f"inv{len(invoices):03d}"
        lines = _lines(stream.child(key), customer, issued, world, fixed)
        due = issued + timedelta(days=stream.choice([14, 30, 45]))
        invoices.append(Invoice(key=key, customer=customer.key, currency=customer.currency,
                                issued_at=issued, due_at=due, lines=lines,
                                total=sum(li.amount_minor for li in lines)))

    # Monthly subscriptions: same lines every month, different service periods (D1).
    for customer in subs:
        cs = stream.child(f"sub.{customer.key}")
        day, hour = cs.randint(1, 27), cs.randint(9, 17)
        desc, plo, phi = cs.choice(CATALOG)
        fixed = [(desc, cs.randint(1, 3), _nice_price(cs.randint(plo, phi), customer.currency, cs))]
        month = in_offset(world.window_start, world.offset).date().replace(day=1)
        while len(invoices) < count:
            issued = datetime(month.year, month.month, day, hour, cs.randint(0, 59),
                              cs.randint(0, 59), tzinfo=tz(world.offset))
            if issued >= hi:
                break
            if issued >= lo and not near_edge(world, issued, BOUNDARY_GUARD_S):
                add(customer, issued, fixed)
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

    while len(invoices) < count:
        customer = stream.choice(world.customers)
        issued = _random_moment(world, stream, lo, hi, world.offset, business_hours=True)
        add(customer, issued, None)
    invoices.sort(key=lambda inv: (utc_seconds(inv.issued_at), inv.key))
    return invoices


def _split(stream: Stream, total: int, parts: int, step: int) -> list[int]:
    if parts == 1 or total < parts * step * 2:
        return [total]
    cuts = sorted(stream.sample(range(1, total // step), parts - 1))
    points = [0] + [c * step for c in cuts] + [total]
    amounts = [b - a for a, b in zip(points, points[1:])]
    return amounts if all(a > 0 for a in amounts) else [total]


def make_payments(world: World, stream: Stream, invoices: list[Invoice]) -> list[Payment]:
    payments: list[Payment] = []
    last_moment = world.window_end - timedelta(days=1)
    for inv in invoices:
        s = stream.child(inv.key)
        plan = s.weighted(["open", "full", "partial", "split"], [25, 45, 10, 20])
        if plan == "open":
            continue
        step = 10 ** exponent(inv.currency)
        if plan == "full":
            amounts = [inv.total]
        elif plan == "partial":   # D3: legitimately partial, the rest stays open
            share = Fraction(s.randint(30, 70), 100)
            units = round_fraction(inv.total * share / step, "half_even")  # exact
            amounts = [max(step, units * step)]
            if amounts[0] >= inv.total:
                amounts = [inv.total]
        else:                     # D2: 2-3 payments that close the invoice
            amounts = _split(s, inv.total, s.randint(2, 3), step)
        moment = inv.issued_at
        for amount in amounts:
            # >= 4 days: the invoice posting (delay <= 3 days) always comes first.
            moment = moment + timedelta(days=s.randint(4, 20), seconds=s.randbelow(86_400))
            moment = in_offset(moment, world.bank_offset)
            if moment >= last_moment or near_edge(world, moment, BOUNDARY_GUARD_S):
                break
            fee = 0
            if inv.currency != world.base_currency and s.chance(Fraction(1, 3)):   # D5
                fee = max(1, amount * s.randint(2, 15) // 1000)
                if fee >= amount:
                    fee = 0
            key = f"pay{len(payments):03d}"
            payments.append(Payment(key=key, customer=inv.customer, currency=inv.currency,
                                    timestamp=moment, amount=amount, fee=fee,
                                    allocations=[(inv.key, amount)]))
    payments.sort(key=lambda p: (utc_seconds(p.timestamp), p.key))
    return payments


def make_expenses(world: World, stream: Stream, count: int) -> list[Expense]:
    expenses = []
    lo = world.window_start + timedelta(hours=2)
    hi = world.window_end - timedelta(hours=2)
    for i in range(count):
        ts = _random_moment(world, stream, lo, hi, world.offset, business_hours=True)
        amount = _nice_price(stream.randint(5_000, 300_000), world.base_currency, stream)
        expenses.append(Expense(key=f"exp{i:03d}", timestamp=ts,
                                account=stream.choice(EXPENSE_ACCOUNTS), amount=amount))
    return expenses


def default_decisions(world: World, stream: Stream, clock: Clock, invoices: list[Invoice],
                      payments: list[Payment]) -> Decisions:
    decisions = Decisions()
    for inv in invoices:
        ts = clock.take(legit_posting(world, stream.child(inv.key), inv.issued_at))
        decisions.invoice_postings[inv.key] = [ts]
    for pay in payments:
        ts = clock.take(legit_posting(world, stream.child(pay.key), pay.timestamp))
        decisions.payment_posting[pay.key] = ts
    return decisions
