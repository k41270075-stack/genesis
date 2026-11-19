import unittest

from vouchai.env.cursor import decode, encode, episode_tag
from vouchai.env.errors import ActionError


class CursorTest(unittest.TestCase):
    def setUp(self):
        self.tag = episode_tag("ep_7Q2KM4XA9C1B3D5F")

    def test_roundtrip_and_determinism(self):
        c = encode("ledger", 50, self.tag)
        self.assertEqual(c, encode("ledger", 50, self.tag))
        self.assertEqual(decode(c, "ledger", self.tag, 120), 50)
        self.assertRegex(c, r"^[A-Z2-7]+$")

    def assertInvalid(self, cursor, table="ledger", tag=None, rows=120):
        with self.assertRaises(ActionError) as ctx:
            decode(cursor, table, tag or self.tag, rows)
        self.assertEqual(ctx.exception.code, "INVALID_CURSOR")

    def test_other_table_and_episode(self):
        c = encode("ledger", 50, self.tag)
        self.assertInvalid(c, table="payments")
        self.assertInvalid(c, tag=episode_tag("ep_OTHER"))

    def test_tampering(self):
        c = encode("ledger", 50, self.tag)
        flipped = ("A" if c[5] != "A" else "B")
        self.assertInvalid(c[:5] + flipped + c[6:])
        self.assertInvalid(c[:-1])
        self.assertInvalid(c + "A")

    def test_out_of_range(self):
        self.assertInvalid(encode("ledger", 120, self.tag), rows=120)
        self.assertInvalid(encode("ledger", 0, self.tag))

    def test_garbage(self):
        for bad in ["", "abc", "!!!!!!!!", 5, None, ["x"], "A" * 500, "ЖЖЖЖЖЖЖЖ"]:
            self.assertInvalid(bad)

    def test_pages_cover_table_without_gaps(self):
        rows, limit = 123, 50
        offsets, cursor = [], None
        while True:
            offset = 0 if cursor is None else decode(cursor, "fx", self.tag, rows)
            offsets.append(offset)
            nxt = offset + limit
            cursor = encode("fx", nxt, self.tag) if nxt < rows else None
            if cursor is None:
                break
        covered = [i for o in offsets for i in range(o, min(o + limit, rows))]
        self.assertEqual(covered, list(range(rows)))


if __name__ == "__main__":
    unittest.main()
