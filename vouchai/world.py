"""The fictional company: name, customers, calendar and a synthetic FX grid.

All names are built from syllables and checked against a stop-list; rates are
a seeded random walk around synthetic levels. Nothing is real.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from fractions import Fraction
from typing import Any

from .model import Customer, FxGrid, World
from .money import round_fraction
from .rng import Stream
from .timeutil import parse_date, parse_offset, period_bounds, tz

EXPORT_MARGIN_DAYS = 10
MAX_LOOKBACK_DAYS = 5
FX_HISTORY_DAYS = 45      # grid starts this many days before the window

# Synthetic value of one major unit, in abstract points. Not market data.
CURRENCY_LEVEL = {
    "KZT": Fraction(1), "USD": Fraction(4713, 10), "EUR": Fraction(5129, 10),
    "GBP": Fraction(6047, 10), "CNY": Fraction(653, 10), "JPY": Fraction(317, 100),
    "KWD": Fraction(15412, 10),
}

_SYLLABLES = ("ka", "lor", "ven", "tri", "mo", "sal", "dar", "en", "qu", "bel", "tor", "ris",
              "na", "vel", "zan", "or", "mi", "tal", "ber", "sen", "ul", "rak", "fen", "do")
_SUFFIXES = ("Systems", "Cloud", "Digital", "Studio", "Partners", "Labs", "Group", "Software",
             "Works", "Tech", "Media", "Data")
# Names that must never be produced (well-known brands); extend when needed.
STOP_LIST = {"Tesla", "Kaspi", "Halyk", "Apple", "Amazon", "Visa", "Oracle", "Sber", "Samsung",
             "Toyota", "Nike", "Zara", "Uber", "Bolt", "Kolesa"}


def make_name(stream: Stream) -> str:
    while True:
        parts = [stream.choice(_SYLLABLES) for _ in range(stream.randint(2, 3))]
        stem = "".join(parts).capitalize()
        if stem not in STOP_LIST and len(stem) >= 4:
            return f"{stem} {stream.choice(_SUFFIXES)}"


def rate_digits(rate: Fraction) -> int:
    return 4 if rate >= 1 else 8


def quantize_rate(rate: Fraction) -> Fraction:
    scale = 10 ** rate_digits(rate)
    return Fraction(round_fraction(rate * scale, "half_even"), scale)


def build_fx(stream: Stream, base: str, currencies: list[str], start: date, end: date) -> FxGrid:
    """Business-day grid for every (currency -> base) pair over [start, end]."""
    grid = FxGrid()
    for cur in currencies:
        s = stream.child(f"pair.{cur}")
        level = CURRENCY_LEVEL[cur] / CURRENCY_LEVEL[base]  # exact: Fraction
        rate = level * (1 + Fraction(s.randint(-500, 500), 10_000))
        d = start
        while d <= end:
            if d.weekday() < 5:
                rate = rate * (1 + Fraction(s.randint(-400, 400), 100_000))
                grid.rates[(d, cur, base)] = quantize_rate(rate)
            d += timedelta(days=1)
    return grid


def build_world(cfg: dict[str, Any], stream: Stream) -> World:
    company = cfg["company"]
    offset = parse_offset(company["timezone"])
    bank_offset = parse_offset(company["bank_timezone"])
    period_start, period_end = period_bounds(parse_date(company["period_start"]),
                                             company["period"], offset)
    margin = timedelta(days=EXPORT_MARGIN_DAYS)
    window_start, window_end = period_start - margin, period_end + margin
    base = company["base_currency"]

    s_names = stream.child("names")
    company_name = make_name(s_names)
    foreign = list(cfg["size"]["currencies"])
    share = Fraction(cfg["size"]["foreign_share"])
    s_cust = stream.child("customers")
    n = cfg["size"]["customers"]
    customers = []
    used_names = {company_name}
    for i in range(n):
        name = make_name(s_names)
        while name in used_names:
            name = make_name(s_names)
        used_names.add(name)
        currency = s_cust.choice(foreign) if foreign and s_cust.chance(share) else base
        customers.append(Customer(key=f"cus{i:03d}", name=name, currency=currency,
                                  subscription=s_cust.chance(Fraction(2, 5))))
    # With foreign currencies configured, at least two customers use one of them.
    if foreign and share > 0 and len(customers) >= 3:
        for i in range(len(customers)):
            if sum(1 for c in customers if c.currency != base) >= 2:
                break
            c = customers[i]
            if c.currency == base:
                customers[i] = Customer(key=c.key, name=c.name, currency=s_cust.choice(foreign),
                                        subscription=c.subscription)
    # The grid covers every configured currency, used or not (full grid, no "on demand").
    used = sorted(({c.currency for c in customers} | set(foreign)) - {base})
    fx_start = window_start.date() - timedelta(days=FX_HISTORY_DAYS)
    fx_end = window_end.date()
    fx = build_fx(stream.child("fx"), base, used, fx_start, fx_end)
    return World(company=company_name, base_currency=base, offset=offset,
                 bank_offset=bank_offset, period=company["period"],
                 period_start=period_start, period_end=period_end,
                 window_start=window_start, window_end=window_end,
                 rate_rule=cfg["policy"]["fx_rate_date"], max_lookback_days=MAX_LOOKBACK_DAYS,
                 rounding=cfg["policy"]["rounding"], customers=customers, fx=fx)


def rate_date(world: World, source: str, local_day: date, rule: str | None = None) -> date | None:
    """Date of the rate the policy allows for an event on local_day, or None."""
    rule = rule or world.rate_rule
    first = local_day if rule == "same_day_or_previous" else local_day - timedelta(days=1)
    for back in range(world.max_lookback_days + 1):
        d = first - timedelta(days=back)
        if (d, source, world.base_currency) in world.fx.rates:
            return d
    return None


def rate_for(world: World, source: str, local_day: date) -> tuple[Fraction, date | None]:
    """Policy rate to the base currency; 1 for the base currency itself."""
    if source == world.base_currency:
        return Fraction(1), None
    d = rate_date(world, source, local_day)
    if d is None:
        raise LookupError("no rate within max_lookback_days")
    return world.fx.rates[(d, source, world.base_currency)], d


def local_midnight(world: World, d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz(world.offset))
