import hashlib
import os
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

from vouchai.rng import DEFAULT_KEY, SeedError, Stream, check_seed, root_key

REPO_ROOT = Path(__file__).resolve().parent.parent


def fingerprint(seed: int) -> str:
    """Hash of a fixed sequence of draws: golden value across OS and Python."""
    s = Stream.root(seed, "golden")
    draws = [s.randbelow(10**k) for k in range(1, 20)]
    items = list(range(50))
    s.child("shuffle").shuffle(items)
    text = ",".join(map(str, draws + items))
    return hashlib.sha256(text.encode()).hexdigest()


class SeedTest(unittest.TestCase):
    def test_accepts_large_seeds(self):
        for seed in (0, 1, 28112026, 2**64 - 1, 10**300):
            self.assertEqual(check_seed(seed), seed)

    def test_rejects(self):
        for bad in (True, False, -1, 1.0, "1", None, 2**20000):
            with self.assertRaises(SeedError, msg=type(bad).__name__):
                check_seed(bad)

    def test_key_changes_root(self):
        self.assertNotEqual(root_key(1), root_key(1, b"secret"))
        self.assertEqual(root_key(1), root_key(1, DEFAULT_KEY))


class StreamTest(unittest.TestCase):
    def test_same_seed_same_sequence(self):
        self.assertEqual(fingerprint(7), fingerprint(7))
        self.assertNotEqual(fingerprint(7), fingerprint(8))

    def test_named_streams_are_independent(self):
        a1 = Stream.root(5, "world")
        first = [a1.randbelow(1000) for _ in range(10)]
        # Drawing heavily from another stream does not shift "world".
        other = Stream.root(5, "inject.duplicate_invoice")
        for _ in range(1000):
            other.randbelow(97)
        a2 = Stream.root(5, "world")
        self.assertEqual([a2.randbelow(1000) for _ in range(10)], first)

    def test_randbelow_range_and_coverage(self):
        s = Stream.root(1, "t")
        seen = {s.randbelow(7) for _ in range(500)}
        self.assertEqual(seen, set(range(7)))
        self.assertTrue(all(3 <= s.randint(3, 5) <= 5 for _ in range(100)))

    def test_shuffle_sample_choice(self):
        s = Stream.root(2, "t")
        items = list(range(20))
        s.shuffle(items)
        self.assertEqual(sorted(items), list(range(20)))
        sample = s.sample(range(100), 10)
        self.assertEqual(len(set(sample)), 10)
        self.assertIn(s.choice("abc"), "abc")
        self.assertIn(s.weighted(["x", "y"], [0, 5]), ["y"])
        self.assertFalse(s.chance(Fraction(0)))
        self.assertTrue(s.chance(Fraction(1)))

    def test_golden_fingerprint_is_stable_across_processes(self):
        env = dict(os.environ, PYTHONHASHSEED="12345", PYTHONPATH=str(REPO_ROOT))
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from tests.test_rng import fingerprint; print(fingerprint(28112026))")
        out = subprocess.run([sys.executable, "-c", code, str(REPO_ROOT)], env=env,
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, fingerprint(28112026))
        self.assertEqual(out, GOLDEN_28112026)


# Pinned on first implementation; must be identical on Linux and Windows,
# Python 3.10-3.12. Changing it requires a GENERATOR_VERSION bump.
GOLDEN_28112026 = "4ade3627eddea113916fcffae992c82ac02c0ffc85432f0c6ba4553c19cd68eb"


if __name__ == "__main__":
    unittest.main()
