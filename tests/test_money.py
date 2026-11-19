import unittest
from fractions import Fraction

from vouchai.money import (
    MoneyError,
    conv,
    format_minor,
    format_rate,
    parse_rate,
    pro_rata,
    round_fraction,
)


class RoundingTest(unittest.TestCase):
    def test_half_even_ties(self):
        cases = {Fraction(5, 2): 2, Fraction(7, 2): 4, Fraction(-5, 2): -2, Fraction(-7, 2): -4,
                 Fraction(1, 2): 0, Fraction(3, 2): 2}
        for x, expected in cases.items():
            self.assertEqual(round_fraction(x, "half_even"), expected, x)

    def test_half_up_ties_away_from_zero(self):
        cases = {Fraction(5, 2): 3, Fraction(7, 2): 4, Fraction(-5, 2): -3, Fraction(1, 2): 1}
        for x, expected in cases.items():
            self.assertEqual(round_fraction(x, "half_up"), expected, x)

    def test_non_ties(self):
        for mode in ("half_even", "half_up"):
            self.assertEqual(round_fraction(Fraction(249, 100), mode), 2)
            self.assertEqual(round_fraction(Fraction(251, 100), mode), 3)
            self.assertEqual(round_fraction(Fraction(-251, 100), mode), -3)
            self.assertEqual(round_fraction(Fraction(7), mode), 7)

    def test_unknown_mode(self):
        with self.assertRaises(MoneyError):
            round_fraction(Fraction(1, 2), "bankers")


class RateTest(unittest.TestCase):
    def test_parse_exact(self):
        self.assertEqual(parse_rate("541.2346"), Fraction(5412346, 10000))
        self.assertEqual(parse_rate("0.00000001"), Fraction(1, 10**8))
        self.assertEqual(parse_rate("3"), Fraction(3))

    def test_parse_rejects(self):
        for bad in ["", "1e3", "1.", ".5", "-1", "0", "0.0", "1.123456789", "01.5", " 1.5",
                    "1,5", "NaN", "Infinity", "１.５", 1.5, None, True]:
            with self.assertRaises(MoneyError, msg=repr(bad)):
                parse_rate(bad)

    def test_format_roundtrip(self):
        for text in ["541.2346", "0.00000001", "3", "1650.5", "12.34567891"]:
            self.assertEqual(format_rate(parse_rate(text)), text)
        self.assertEqual(format_rate(Fraction(54123460, 100000)), "541.2346")

    def test_format_rejects_too_precise(self):
        with self.assertRaises(MoneyError):
            format_rate(Fraction(1, 3))


class ConversionTest(unittest.TestCase):
    """Numbers of the X1 worked example (docs/DESIGN.md)."""

    def test_x1_booked_invoice(self):
        self.assertEqual(conv(845_000, parse_rate("541.2346"), "EUR", "KZT", "half_even"),
                         457_343_237)

    def test_x1_payment_at_local_and_utc_date(self):
        right = conv(507_000, parse_rate("546.0921"), "EUR", "KZT", "half_even")
        wrong = conv(507_000, parse_rate("543.1187"), "EUR", "KZT", "half_even")
        self.assertEqual(right, 276_868_695)
        self.assertEqual(wrong, 275_361_181)
        self.assertEqual(right - wrong, 1_507_514)  # E3 amount

    def test_x1_relief_and_e2_amount(self):
        relief = pro_rata(507_000, 457_343_237, 845_000, "half_even")
        self.assertEqual(relief, 274_405_942)
        applied = pro_rata(300_000, 457_343_237, 845_000, "half_even")
        self.assertEqual(applied, 162_370_380)
        self.assertEqual(relief - applied, 112_035_562)  # E2 amount

    def test_x1_unapplied_and_fx_lines(self):
        friday = parse_rate("543.1187")
        booked_cash = conv(507_000, friday, "EUR", "KZT", "half_even")
        applied_relief = pro_rata(300_000, 457_343_237, 845_000, "half_even")
        unapplied = conv(207_000, friday, "EUR", "KZT", "half_even")
        self.assertEqual(unapplied, 112_425_571)
        fx_after = booked_cash - applied_relief - unapplied
        self.assertEqual(fx_after, 565_230)  # Cr 7100 after X1
        # The posting balances: Dr 1010 = Cr 1200 + Cr 2150 + Cr 7100
        self.assertEqual(booked_cash, applied_relief + unapplied + fx_after)
        self.assertEqual(276_868_695 - 274_405_942, 2_462_753)  # Cr 7100 in clean books
        # Traps listed in the plan
        self.assertEqual(booked_cash - applied_relief, 112_990_801)  # naive "cash - relief"
        self.assertNotEqual(unapplied, 112_035_562)  # 2150 balance is not the E2 amount

    def test_exponent_shift(self):
        # 1000 JPY (exp 0) at 3.1234 KZT/JPY -> 3123.40 KZT = 312340 minor
        self.assertEqual(conv(1000, parse_rate("3.1234"), "JPY", "KZT", "half_even"), 312_340)
        # 1.500 KWD (exp 3) at 1650.25 -> 2475.375 KZT -> 247537.5 minor -> tie -> even
        self.assertEqual(conv(1500, parse_rate("1650.25"), "KWD", "KZT", "half_even"), 247_538)
        self.assertEqual(conv(1500, parse_rate("1650.25"), "KWD", "KZT", "half_up"), 247_538)
        self.assertEqual(conv(1500, parse_rate("1650.23"), "KWD", "KZT", "half_even"), 247_534)

    def test_sign_symmetry(self):
        rate = parse_rate("1.5")
        for mode in ("half_even", "half_up"):
            for amount in (1, 3, 5, 7, 12345):
                self.assertEqual(conv(-amount, rate, "USD", "EUR", mode),
                                 -conv(amount, rate, "USD", "EUR", mode))

    def test_rejects_bad_input(self):
        with self.assertRaises(MoneyError):
            conv(True, Fraction(1), "USD", "KZT", "half_even")
        with self.assertRaises(MoneyError):
            conv(100, Fraction(1), "XXX", "KZT", "half_even")
        with self.assertRaises(MoneyError):
            conv(100, Fraction(0), "USD", "KZT", "half_even")

    def test_format_minor(self):
        self.assertEqual(format_minor(845_000, "EUR"), "8450.00")
        self.assertEqual(format_minor(-5, "KZT"), "-0.05")
        self.assertEqual(format_minor(1234, "JPY"), "1234")
        self.assertEqual(format_minor(1500, "KWD"), "1.500")


if __name__ == "__main__":
    unittest.main()
