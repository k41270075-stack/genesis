"""Metrics and the shared terminal reward, computed exactly.

    P  = TP / (TP + FP)          0 if the denominator is 0
    R  = TP / (TP + FN)          0 if the denominator is 0
    F1 = 2TP / (2TP + FP + FN)   1 if truth and findings are both empty
    reward = clip(2*F1 - 1 - 0.002 * inspection_steps, -1, 1)

Everything is a Fraction; floats appear only at the output boundary.
"""

from __future__ import annotations

from fractions import Fraction

STEP_COST = Fraction(2, 1000)


def precision(tp: int, fp: int) -> Fraction:
    return Fraction(tp, tp + fp) if tp + fp else Fraction(0)


def recall(tp: int, fn: int) -> Fraction:
    return Fraction(tp, tp + fn) if tp + fn else Fraction(0)


def f1(tp: int, fp: int, fn: int) -> Fraction:
    denominator = 2 * tp + fp + fn
    if denominator == 0:
        return Fraction(1)  # nothing to find and nothing claimed
    return Fraction(2 * tp, denominator)


def clip(x: Fraction, lo: Fraction = Fraction(-1), hi: Fraction = Fraction(1)) -> Fraction:
    return max(lo, min(hi, x))


def shared_reward(f1_value: Fraction, inspection_steps: int) -> Fraction:
    if type(inspection_steps) is not int or inspection_steps < 0:
        raise ValueError("inspection_steps must be a non-negative int")
    return clip(2 * Fraction(f1_value) - 1 - STEP_COST * inspection_steps)


def invalid_reward() -> Fraction:
    return Fraction(-1)


def to_float(x: Fraction) -> float:
    """The single place where an exact value becomes a float (output only)."""
    return x.numerator / x.denominator  # float-ok: true division of ints, correctly rounded
