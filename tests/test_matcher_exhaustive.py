"""The matcher proven on every small case, not on examples.

1. Exhaustive: every bipartite graph with up to 4 findings and 4 issues (74 954
   graphs) against a brute force over all one-to-one assignments with the jury's
   rule: maximum cardinality, then the lexicographically smallest sorted
   sequence of (issue_id, finding index); issue IDs not in index order.
2. Metamorphic properties of grade() on 2 000 random answers (fixed seed):
   the order of findings never changes TP/FP/FN or the reward; k copies of a
   finding are never better than one; adding a false finding never raises the
   reward; the reward never exceeds 1 - 0.002 * inspection_steps.
"""

import itertools
import unittest
from fractions import Fraction

from vouchai.grader import Issue, grade
from vouchai.grader.match import jury_matching
from vouchai.rng import Stream


def brute(edges, issue_ids):
    best_card, best = -1, None
    for assign in itertools.product(*[[None] + list(e) for e in edges]):
        used = [a for a in assign if a is not None]
        if len(used) != len(set(used)):
            continue
        seq = sorted((issue_ids[a], i) for i, a in enumerate(assign) if a is not None)
        if len(used) > best_card or (len(used) == best_card and seq < best):
            best_card, best = len(used), seq
    return best_card, best


class ExhaustiveMatchingTest(unittest.TestCase):
    def test_every_graph_up_to_4x4(self):
        total = mismatches = 0
        ids_pool = ["I3", "I1", "I4", "I2"]          # code-point order != index order
        for nf in range(1, 5):
            for ni in range(1, 5):
                ids = ids_pool[:ni]
                pairs = [(i, j) for i in range(nf) for j in range(ni)]
                for mask in range(1 << len(pairs)):
                    edges = [[] for _ in range(nf)]
                    for b, (i, j) in enumerate(pairs):
                        if mask >> b & 1:
                            edges[i].append(j)
                    got = jury_matching(edges, ids)
                    seq = sorted((ids[a], i) for i, a in enumerate(got) if a is not None)
                    card, want = brute(edges, ids)
                    total += 1
                    mismatches += (len(seq), seq) != (card, want)
        self.assertEqual((total, mismatches), (74954, 0))


TYPES = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")
IDS = ["R1", "R2", "R3", "R4", "D1", "D2", "D3", "INV-1", "PAY-1"]
ISSUES = [Issue.from_json(i) for i in (
    {"issue_id": "A", "type": "duplicate_invoice", "affected_ids": ["R1"],
     "expected_amount_minor": 10000, "currency": "KZT", "evidence_ids": ["D1", "D2"]},
    {"issue_id": "B", "type": "payment_allocation", "affected_ids": ["PAY-1", "INV-1"],
     "expected_amount_minor": 777, "currency": "KZT", "tolerance_minor": 1,
     "evidence_ids": ["D3", "R2"]},
)]
CORRECT = [
    {"type": "duplicate_invoice", "affected_ids": ["R1"], "claimed_amount_minor": 10000,
     "currency": "KZT", "evidence_ids": ["D1", "D2"], "explanation": "a"},
    {"type": "payment_allocation", "affected_ids": ["INV-1", "PAY-1"],
     "claimed_amount_minor": 778, "currency": "KZT", "evidence_ids": ["R2", "D3"],
     "explanation": "b"},
]


def score(findings, steps=0):
    r = grade({"findings": findings}, episode_id=None, issues=ISSUES, public_ids=set(IDS),
              inspection_steps=steps)
    return r["TP"], r["FP"], r["FN"], Fraction(r["reward_exact"])


def random_finding(s: Stream) -> dict:
    if s.chance(Fraction(1, 3)):
        f = dict(s.choice(CORRECT))
        if s.chance(Fraction(1, 2)):
            f["claimed_amount_minor"] += s.randint(-2, 2)
        return f
    return {"type": s.choice(TYPES), "affected_ids": s.sample(IDS, s.randint(1, 2)),
            "claimed_amount_minor": s.randint(0, 20000), "currency": "KZT",
            "evidence_ids": s.sample(IDS, s.randint(1, 3)), "explanation": "x"}


class MetamorphicTest(unittest.TestCase):
    def test_properties_on_random_answers(self):
        s = Stream.root(20261121, "metamorphic")
        for _ in range(2000):
            findings = [random_finding(s) for _ in range(s.randint(0, 6))]
            steps = s.randint(0, 100)
            base = score(findings, steps)
            shuffled = list(findings)
            s.shuffle(shuffled)
            self.assertEqual(score(shuffled, steps), base)
            self.assertLessEqual(base[3], 1 - Fraction(2, 1000) * steps)
            if findings:
                k = s.randint(2, 4)
                once = score(findings[:1], steps)
                self.assertLessEqual(score(findings[:1] * k, steps)[3], once[3])
            false = {"type": "fx_conversion", "affected_ids": ["R4"],
                     "claimed_amount_minor": 1, "currency": "KZT", "evidence_ids": ["R4"],
                     "explanation": "never true"}
            if len(findings) < 30:
                self.assertLessEqual(score(findings + [false], steps)[3], base[3])


if __name__ == "__main__":
    unittest.main()
