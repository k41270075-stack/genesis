import decimal
import unittest

from vouchai.env.calculator import evaluate
from vouchai.env.errors import ActionError


class CalculatorTest(unittest.TestCase):
    def test_arithmetic(self):
        cases = {
            "1+1": "2",
            "507000 * 546.0921": "276868694.7",
            "507000*457343237/845000": "274405942.2",
            "2*(3+4)": "14",
            "-5 + 2": "-3",
            "--5": "5",
            "10/4": "2.5",
            "1/3": "0.3333333333333333333333333333333333",
            "0.10 + 0.20": "0.3",
            "1 - 1": "0",
            "-0": "0",
            "0 * -5": "0",
            "1000000 * 1000": "1000000000",
            "  7  ": "7",
        }
        for expr, expected in cases.items():
            self.assertEqual(evaluate(expr), expected, expr)

    def test_rejects_code_and_tricks(self):
        bad = [
            "__import__('os')", "9**9**9", "2**3", "1e999999", "1E5", "1_000", "１２",
            "((((1", "1)", "1/0", "1/(2-2)", "", " ", "abs(1)", "1,5", "1.", ".5", "NaN",
            "Infinity", "1 2", "+", "1+", "x", "0x10", "١", "1;2", None, 5, ["1"],
            "(" * 33 + "1" + ")" * 33, "1" * 31, "1" + "+1" * 64,
            "9" * 30 + ("*" + "9" * 30) * 3,
        ]
        for expr in bad:
            with self.assertRaises(ActionError, msg=repr(expr)[:60]) as ctx:
                evaluate(expr)
            self.assertEqual(ctx.exception.code, "CALC_ERROR")

    def test_limits_boundary(self):
        self.assertEqual(evaluate("(" * 32 + "1" + ")" * 32), "1")
        self.assertEqual(evaluate("1" * 30), "1" * 30)
        with self.assertRaises(ActionError):
            evaluate("1" * 257)

    def test_global_context_untouched(self):
        before = decimal.getcontext().prec
        evaluate("1/7")
        self.assertEqual(decimal.getcontext().prec, before)


if __name__ == "__main__":
    unittest.main()
