import unittest

from vouchai.jsonsafe import (
    MAX_DEPTH,
    MAX_INPUT_BYTES,
    JsonInputError,
    dumps_canonical,
    loads_untrusted,
    roundtrips,
)


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
        self.assertEqual(self.reason("x" * (MAX_INPUT_BYTES + 1)), "too_large")
        self.assertEqual(self.reason(b"1" * (MAX_INPUT_BYTES + 1)), "too_large")
        # multi-byte characters count as bytes
        self.assertEqual(self.reason('"' + "ж" * (MAX_INPUT_BYTES // 2) + '"'), "too_large")

    def test_deep_nesting(self):
        self.assertIn(self.reason("[" * 100_000 + "]" * 100_000), ("too_deep", "malformed"))
        # an explicit bound, not the interpreter's recursion limit (3.12 parses 5000 levels)
        self.assertEqual(self.reason("[" * (MAX_DEPTH + 1) + "]" * (MAX_DEPTH + 1)), "too_deep")
        self.assertIsInstance(loads_untrusted("[" * MAX_DEPTH + "]" * MAX_DEPTH), list)

    def test_deep_action_is_malformed_on_every_python(self):
        from vouchai.server.local import LocalEnv
        deep = node = {"action": "calculator", "expression": "1"}
        for _ in range(MAX_DEPTH + 5):
            node["x"] = {}
            node = node["x"]
        env = LocalEnv(mode="train")
        env.reset(3, "smoke")
        for action in (deep, dumps_canonical(deep)):
            obs, *_ = env.step(action)
            self.assertEqual(obs["error"]["code"], "MALFORMED_ACTION")
        obs, reward, terminated, *_ = env.step({"action": "submit", "findings": deep})
        self.assertTrue(terminated)
        self.assertEqual(reward, -1)

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
