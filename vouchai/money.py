"""Money and FX arithmetic without floats.

Amounts are integers in minor units. Rates are exact fractions parsed from
decimal strings with at most 8 fractional digits: how many units of the target
currency one unit of the source currency buys.

    conv(x, r) = sign(x) * round_policy(|x| * r * 10^(e_base - e_doc))
"""

from __future__ import annotations

import re
from fractions import Fraction

# Minor-unit exponents of every currency the generator may use (manifest copy).
CURRENCY_EXPONENTS: dict[str, int] = {
    "KZT": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CNY": 2,
    "JPY": 0,
    "KWD": 3,
}

ROUNDING_MODES = ("half_even", "half_up")

RATE_DECIMALS = 8
_RATE_SCALE = 10**RATE_DECIMALS
_RATE_RE = re.compile(r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,8})?$")


class MoneyError(ValueError):
    """Invalid currency, rate or rounding mode."""


def exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency]
    except KeyError:
        raise MoneyError(f"unknown currency: {currency!r}") from None


def check_minor(amount: object) -> int:
    """Return amount if it is a real int (bool is rejected)."""
    if type(amount) is not int:
        raise MoneyError("amount must be an int in minor units")
    return amount


def round_fraction(x: Fraction, mode: str) -> int:
    """Round an exact fraction to an integer.

    half_even: ties go to the even neighbour (banker's rounding).
    half_up:   ties go away from zero.
    """
    if mode not in ROUNDING_MODES:
        raise MoneyError(f"unknown rounding mode: {mode!r}")
    q, r = divmod(x.numerator, x.denominator)  # floor division, 0 <= r < d
    twice = 2 * r
    d = x.denominator
    if twice < d:
        return q
    if twice > d:
        return q + 1
    if mode == "half_even":
        return q if q % 2 == 0 else q + 1
    # half_up: away from zero
    return q + 1 if x > 0 else q


def parse_rate(text: object) -> Fraction:
    """Parse a decimal rate string such as "541.2346" into an exact Fraction."""
    if not isinstance(text, str) or not _RATE_RE.match(text):
        raise MoneyError("rate must be a decimal string with at most 8 fractional digits")
    value = Fraction(text)
    if value <= 0:
        raise MoneyError("rate must be positive")
    return value


def format_rate(rate: Fraction) -> str:
    """Canonical decimal string of a rate: no exponent, no trailing zeros."""
    scaled = rate * _RATE_SCALE
    if scaled.denominator != 1 or scaled <= 0:
        raise MoneyError("rate must be positive with at most 8 fractional digits")
    units, frac = divmod(scaled.numerator, _RATE_SCALE)
    if frac == 0:
        return str(units)
    digits = f"{frac:0{RATE_DECIMALS}d}".rstrip("0")
    return f"{units}.{digits}"


def conv(amount_minor: int, rate: Fraction, doc_currency: str, base_currency: str,
         mode: str) -> int:
    """Convert minor units of doc_currency into minor units of base_currency.

    The absolute value is converted and rounded, then the sign is applied, so
    a refund converts to exactly minus the matching receipt.
    """
    check_minor(amount_minor)
    if not isinstance(rate, Fraction) or rate <= 0:
        raise MoneyError("rate must be a positive Fraction")
    shift = exponent(base_currency) - exponent(doc_currency)
    magnitude = Fraction(abs(amount_minor)) * rate * (Fraction(10) ** shift)
    rounded = round_fraction(magnitude, mode)
    return -rounded if amount_minor < 0 else rounded


def pro_rata(part: int, booked: int, total: int, mode: str) -> int:
    """Relief of part `part` of a document total `total` booked at `booked`.

    Used for AR relief at the historical rate: round(part * booked / total).
    """
    for value in (part, booked, total):
        check_minor(value)
    if total <= 0:
        raise MoneyError("document total must be positive")
    return round_fraction(Fraction(part * booked, total), mode)


def format_minor(amount_minor: int, currency: str) -> str:
    """Human-readable amount for passports and reports: 845000 EUR -> 8450.00."""
    check_minor(amount_minor)
    exp = exponent(currency)
    sign = "-" if amount_minor < 0 else ""
    units, frac = divmod(abs(amount_minor), 10**exp)
    if exp == 0:
        return f"{sign}{units}"
    return f"{sign}{units}.{frac:0{exp}d}"
