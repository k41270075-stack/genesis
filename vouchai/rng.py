"""Deterministic randomness: SHA-256 in counter mode, named sub-streams.

The root of all streams is HMAC-SHA256(key, decimal(seed)). The default key is
a public constant; a private run may pass a secret key so that enumerating
small seeds is useless. The `random` module is banned in the core: its
algorithms are not guaranteed to stay byte-identical across Python versions.

Streams are addressed by name ("world", "events", "inject.fx_conversion", ...),
so drawing more numbers in one stream never shifts another.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import MutableSequence, Sequence
from fractions import Fraction
from typing import TypeVar

T = TypeVar("T")

DEFAULT_KEY = b"vouchai/public-root-key/v1"
# ~3900 decimal digits: any seed of practical size, safely below CPython's
# 4300-digit int->str conversion limit used when hashing decimal(seed).
MAX_SEED_BITS = 13000


class SeedError(ValueError):
    """The seed is not a non-negative int (bool is rejected)."""


def check_seed(seed: object) -> int:
    if type(seed) is not int:
        raise SeedError("seed must be a non-negative int")
    if seed < 0:
        raise SeedError("seed must be a non-negative int")
    if seed.bit_length() > MAX_SEED_BITS:
        raise SeedError("seed is too large")
    return seed


def root_key(seed: int, key: bytes = DEFAULT_KEY) -> bytes:
    check_seed(seed)
    if not isinstance(key, bytes) or not key:
        raise SeedError("key must be non-empty bytes")
    return hmac.new(key, str(seed).encode("ascii"), hashlib.sha256).digest()


def _derive(parent: bytes, name: str) -> bytes:
    if not isinstance(name, str) or not name:
        raise ValueError("stream name must be a non-empty string")
    return hashlib.sha256(b"vouchai/stream\x00" + parent + b"\x00" + name.encode("utf-8")).digest()


class Stream:
    """An independent deterministic bit stream."""

    __slots__ = ("_key", "_counter", "_buffer", "_bits")

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("stream key must be 32 bytes")
        self._key = key
        self._counter = 0
        self._buffer = 0
        self._bits = 0

    @classmethod
    def root(cls, seed: int, name: str, key: bytes = DEFAULT_KEY) -> Stream:
        return cls(_derive(root_key(seed, key), name))

    def child(self, name: str) -> Stream:
        """A sub-stream that depends only on this stream's identity and the name."""
        return Stream(_derive(self._key, name))

    def digest(self, label: str) -> bytes:
        """Keyed hash of a label; used for IDs and tie-breaking order."""
        return hashlib.sha256(self._key + b"\x00digest\x00" + label.encode("utf-8")).digest()

    def _refill(self) -> None:
        block = hashlib.sha256(self._key + self._counter.to_bytes(8, "big")).digest()
        self._counter += 1
        self._buffer = (self._buffer << 256) | int.from_bytes(block, "big")
        self._bits += 256

    def getrandbits(self, k: int) -> int:
        if k < 0:
            raise ValueError("k must be non-negative")
        if k == 0:
            return 0
        while self._bits < k:
            self._refill()
        self._bits -= k
        value = self._buffer >> self._bits
        self._buffer &= (1 << self._bits) - 1
        return value

    def randbelow(self, n: int) -> int:
        """Uniform integer in [0, n) by rejection sampling."""
        if type(n) is not int or n <= 0:
            raise ValueError("n must be a positive int")
        k = n.bit_length()
        while True:
            r = self.getrandbits(k)
            if r < n:
                return r

    def randint(self, a: int, b: int) -> int:
        """Uniform integer in [a, b]."""
        if b < a:
            raise ValueError("empty range")
        return a + self.randbelow(b - a + 1)

    def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise IndexError("choice from an empty sequence")
        return seq[self.randbelow(len(seq))]

    def shuffle(self, seq: MutableSequence[T]) -> None:
        """Fisher-Yates in place."""
        for i in range(len(seq) - 1, 0, -1):
            j = self.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]

    def sample(self, seq: Sequence[T], k: int) -> list[T]:
        if not 0 <= k <= len(seq):
            raise ValueError("sample larger than population")
        pool = list(seq)
        out = []
        for _ in range(k):
            out.append(pool.pop(self.randbelow(len(pool))))
        return out

    def chance(self, p: Fraction) -> bool:
        """True with exact probability p (a Fraction in [0, 1])."""
        p = Fraction(p)
        if not 0 <= p <= 1:
            raise ValueError("probability out of range")
        return self.randbelow(p.denominator) < p.numerator

    def weighted(self, items: Sequence[T], weights: Sequence[int]) -> T:
        """Pick one item with integer weights."""
        if len(items) != len(weights) or not items:
            raise ValueError("items and weights must be non-empty and equal length")
        if any(type(w) is not int or w < 0 for w in weights):
            raise ValueError("weights must be non-negative ints")
        total = sum(weights)
        if total <= 0:
            raise ValueError("weights sum to zero")
        r = self.randbelow(total)
        for item, w in zip(items, weights):
            if r < w:
                return item
            r -= w
        raise AssertionError("unreachable")
