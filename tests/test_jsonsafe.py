import unittest

from vouchai.jsonsafe import JsonInputError, dumps_canonical, loads_untrusted, roundtrips


class UntrustedJsonTest(unittest.TestCase):
    def reason(self, data):
        with self.assertRaises(JsonInputError) as ctx:
            loads_untrusted(data)
        return ctx.exception.reason

    def test_valid(self):
        self.assertEqual(loads_untrusted('{"action":"calculator","expression":"1+1"}'),
                         {"action": "calculator", "expression": "1+1"})
        self.assertEqual(loads_untrusted(b'[1,2]'), [1, 2])

    def test_duplicate_keys_rejected(self):
        self.assertEqual(self.reason('{"action":"submit","action":"get_record"}'), "duplicate_key")

    def test_non_finite_rejected(self):
        for text in ("NaN", '{"x": Infinity}', "[-Infinity]"):
            self.assertEqual(self.reason(text), "non_finite_number")

    def test_size_limit(self):
        self.assertEqual(self.reason("x" * (256 * 1024 + 1)), "too_large")
        self.assertEqual(self.reason(b"1" * (256 * 1024 + 1)), "too_large")
        # multi-byte characters count as bytes
        self.assertEqual(self.reason('"' + "ж" * (128 * 1024) + '"'), "too_large")

    def test_deep_nesting(self):
        self.assertIn(self.reason("[" * 100_000 + "]" * 100_000), ("too_deep", "malformed"))

    def test_huge_int(self):
        self.assertEqual(self.reason("1" * 5000), "malformed")

    def test_garbage(self):
        for data in ("", "{", "not json", b"\xff\xfe", 42):
            self.assertIn(self.reason(data), ("malformed", "not_utf8", "not_text"))


class CanonicalTest(unittest.TestCase):
    def test_ascii_single_line(self):
        text = dumps_canonical({"a": "Ж\n", "b": [1, None, True]})
        self.assertTrue(text.isascii())
        self.assertNotIn("\n", text)
        self.assertEqual(text, '{"a":"\\u0416\\n","b":[1,null,true]}')

    def test_roundtrip(self):
        self.assertTrue(roundtrips({"rows": [{"id": "R1", "amount": 5}], "next": None}))
        self.assertFalse(roundtrips({1: "int key"}))
        self.assertFalse(roundtrips({"t": (1, 2)}))


if __name__ == "__main__":
    unittest.main()
