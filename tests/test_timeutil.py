import unittest
from datetime import date

from vouchai.timeutil import (
    TimeFormatError,
    add_months,
    format_offset,
    format_ts,
    in_interval,
    in_offset,
    is_weekend,
    local_date,
    parse_date,
    parse_offset,
    parse_ts,
    period_bounds,
    utc_seconds,
)


class OffsetTest(unittest.TestCase):
    def test_roundtrip(self):
        for text, minutes in [("+05:00", 300), ("-03:30", -210), ("+00:00", 0), ("+14:00", 840),
                              ("-12:00", -720), ("+05:45", 345)]:
            self.assertEqual(parse_offset(text), minutes)
            self.assertEqual(format_offset(minutes), text)

    def test_rejects(self):
        for bad in ["Z", "+5:00", "+05", "+0500", "+15:00", "+05:60", "05:00", "", None]:
            with self.assertRaises(TimeFormatError, msg=repr(bad)):
                parse_offset(bad)


class TimestampTest(unittest.TestCase):
    def test_roundtrip_keeps_written_offset(self):
        for text in ["2027-03-01T02:40:00+05:00", "2027-02-28T21:40:00+00:00",
                     "2026-12-31T23:59:59-08:00"]:
            self.assertEqual(format_ts(parse_ts(text)), text)

    def test_x1_payment_is_march_locally_and_february_in_utc(self):
        bank = parse_ts("2027-02-28T21:40:00+00:00")
        self.assertEqual(local_date(bank, 300), date(2027, 3, 1))
        self.assertEqual(local_date(bank, 0), date(2027, 2, 28))
        self.assertEqual(format_ts(in_offset(bank, 300)), "2027-03-01T02:40:00+05:00")
        start, end = period_bounds(date(2027, 3, 1), "month", 300)
        self.assertTrue(in_interval(bank, start, end))
        self.assertTrue(is_weekend(date(2027, 2, 27)) and is_weekend(date(2027, 2, 28)))
        self.assertEqual(date(2027, 3, 1).weekday(), 0)  # Monday

    def test_same_instant_in_different_offsets(self):
        a = parse_ts("2027-03-01T00:00:00+05:00")
        b = parse_ts("2027-02-28T19:00:00+00:00")
        self.assertEqual(a, b)
        self.assertEqual(utc_seconds(a), utc_seconds(b))

    def test_rejects(self):
        for bad in ["2027-03-01 10:00:00+05:00", "2027-03-01T10:00:00Z", "2027-03-01T10:00:00",
                    "2027-03-01T10:00:00.5+05:00", "2027-02-30T10:00:00+05:00",
                    "2027-03-01T24:00:00+05:00", "２０２７-03-01T10:00:00+05:00", 0, None]:
            with self.assertRaises(TimeFormatError, msg=repr(bad)):
                parse_ts(bad)


class PeriodTest(unittest.TestCase):
    def test_month_and_quarter(self):
        start, end = period_bounds(date(2027, 12, 1), "month", -300)
        self.assertEqual(format_ts(start), "2027-12-01T00:00:00-05:00")
        self.assertEqual(format_ts(end), "2028-01-01T00:00:00-05:00")
        start, end = period_bounds(date(2027, 10, 1), "quarter", 300)
        self.assertEqual(format_ts(end), "2028-01-01T00:00:00+05:00")

    def test_half_open(self):
        start, end = period_bounds(date(2027, 3, 1), "month", 300)
        self.assertTrue(in_interval(start, start, end))
        self.assertFalse(in_interval(end, start, end))

    def test_rejects(self):
        with self.assertRaises(TimeFormatError):
            period_bounds(date(2027, 3, 2), "month", 300)
        with self.assertRaises(TimeFormatError):
            period_bounds(date(2027, 2, 1), "quarter", 300)
        with self.assertRaises(TimeFormatError):
            period_bounds(date(2027, 3, 1), "week", 300)

    def test_add_months_and_dates(self):
        self.assertEqual(add_months(date(2027, 11, 1), 3), date(2028, 2, 1))
        self.assertEqual(add_months(date(2027, 1, 1), -1), date(2026, 12, 1))
        self.assertEqual(parse_date("2027-03-01"), date(2027, 3, 1))
        with self.assertRaises(TimeFormatError):
            parse_date("2027-3-1")


if __name__ == "__main__":
    unittest.main()
