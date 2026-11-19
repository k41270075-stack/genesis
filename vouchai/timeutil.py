"""ISO-8601 timestamps with explicit fixed offsets, company-local dates, periods.

No zoneinfo, no clocks, no locale: offsets are fixed per episode and every
string is built from integer fields.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

_TS_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"T([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"([+-])([0-9]{2}):([0-9]{2})$"
)
_OFFSET_RE = re.compile(r"^([+-])([0-9]{2}):([0-9]{2})$")
_DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")

MAX_OFFSET_MINUTES = 14 * 60
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
PERIOD_KINDS = ("month", "quarter")


class TimeFormatError(ValueError):
    """A timestamp, date or offset string does not follow the strict format."""


def parse_offset(text: object) -> int:
    """"+05:00" -> 300, "-03:30" -> -210 (minutes east of UTC)."""
    if not isinstance(text, str):
        raise TimeFormatError("offset must be a string like +05:00")
    m = _OFFSET_RE.match(text)
    if not m:
        raise TimeFormatError("offset must look like +05:00")
    sign = -1 if m.group(1) == "-" else 1
    hours, minutes = int(m.group(2)), int(m.group(3))
    if minutes >= 60:
        raise TimeFormatError("offset minutes out of range")
    total = sign * (hours * 60 + minutes)
    if abs(total) > MAX_OFFSET_MINUTES:
        raise TimeFormatError("offset out of range")
    return total


def format_offset(minutes: int) -> str:
    if abs(minutes) > MAX_OFFSET_MINUTES:
        raise TimeFormatError("offset out of range")
    sign = "-" if minutes < 0 else "+"
    h, m = divmod(abs(minutes), 60)
    return f"{sign}{h:02d}:{m:02d}"


def tz(minutes: int) -> timezone:
    if abs(minutes) > MAX_OFFSET_MINUTES:
        raise TimeFormatError("offset out of range")
    return timezone(timedelta(minutes=minutes))


def parse_ts(text: object) -> datetime:
    """Strict YYYY-MM-DDTHH:MM:SS+HH:MM -> aware datetime in the written offset."""
    if not isinstance(text, str):
        raise TimeFormatError("timestamp must be a string")
    m = _TS_RE.match(text)
    if not m:
        raise TimeFormatError("timestamp must look like 2027-03-01T10:00:00+05:00")
    offset = parse_offset(f"{m.group(7)}{m.group(8)}:{m.group(9)}")
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5)), int(m.group(6)),
                        tzinfo=tz(offset))
    except ValueError:
        raise TimeFormatError("timestamp fields out of range") from None


def offset_minutes(dt: datetime) -> int:
    off = dt.utcoffset()
    if off is None:
        raise TimeFormatError("naive datetime")
    return off // timedelta(minutes=1)


def format_ts(dt: datetime) -> str:
    """Aware datetime -> canonical string in its own offset, seconds precision."""
    if dt.microsecond:
        raise TimeFormatError("sub-second timestamps are not allowed")
    off = offset_minutes(dt)
    return (f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T"
            f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}{format_offset(off)}")


def in_offset(dt: datetime, minutes: int) -> datetime:
    """The same instant written in another fixed offset."""
    offset_minutes(dt)
    return dt.astimezone(tz(minutes))


def local_date(dt: datetime, minutes: int) -> date:
    """Calendar date of the instant in a fixed offset (e.g. company time)."""
    return in_offset(dt, minutes).date()


def utc_seconds(dt: datetime) -> int:
    offset_minutes(dt)
    return (dt - EPOCH) // timedelta(seconds=1)


def from_utc_seconds(seconds: int, minutes: int) -> datetime:
    return in_offset(EPOCH + timedelta(seconds=seconds), minutes)


def parse_date(text: object) -> date:
    if not isinstance(text, str):
        raise TimeFormatError("date must be a string")
    m = _DATE_RE.match(text)
    if not m:
        raise TimeFormatError("date must look like 2027-03-01")
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise TimeFormatError("date fields out of range") from None


def format_date(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def add_months(d: date, months: int) -> date:
    """First-of-month arithmetic; d must be the first day of a month."""
    if d.day != 1:
        raise TimeFormatError("add_months expects the first day of a month")
    index = d.year * 12 + (d.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def period_bounds(start: date, kind: str, minutes: int) -> tuple[datetime, datetime]:
    """[start, end) of a reporting period at local midnight in a fixed offset."""
    if kind not in PERIOD_KINDS:
        raise TimeFormatError(f"unknown period kind: {kind!r}")
    if start.day != 1:
        raise TimeFormatError("period must start on the first day of a month")
    if kind == "quarter" and (start.month - 1) % 3:
        raise TimeFormatError("quarter must start in January, April, July or October")
    end = add_months(start, 1 if kind == "month" else 3)
    zone = tz(minutes)
    return (datetime(start.year, start.month, start.day, tzinfo=zone),
            datetime(end.year, end.month, end.day, tzinfo=zone))


def in_interval(dt: datetime, start: datetime, end: datetime) -> bool:
    """Half-open membership: start <= dt < end."""
    return start <= dt < end


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5
