"""Block 3 of the jury's check definitions (20.11.2026): 20 matcher and reward
tests plus the open examples M01-M12, run through judge_adapter.score_episode
on the hand-made fixture examples/matcher_fixture (error A on R1, 10000 KZT,
evidence {D1, D2}, tolerance 0; D3 exists, U does not).
"""

import copy
import json
import shutil
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import judge_adapter as ja
from vouchai.grader import Issue, grade
from vouchai.grader.match import jury_matching

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "matcher_fixture"
EP = "ep_FIXTURE_A"
A = {"issue_id": "A", "type": "duplicate_invoice", "affected_ids": ["R1"],
     "expected_amount_minor": 10000, "currency": "KZT", "tolerance_minor": 0,
     "evidence_ids": ["D1", "D2"]}
B = {"issue_id": "B", "type": "period_cutoff", "affected_ids": ["R3"],
     "expected_amount_minor": 10000, "currency": "KZT", "tolerance_minor": 0,
     "evidence_ids": ["D2", "D3"]}
TYPES = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")


def finding(issue=A, **changes):
    f = {"type": issue["type"], "affected_ids": list(issue["affected_ids"]),
         "claimed_amount_minor": issue["expected_amount_minor"], "currency": issue["currency"],
         "evidence_ids": list(issue["evidence_ids"]), "explanation": "posted twice"}
    f.update(changes)
    return f


class JuryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vouchai-matcher-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def episode(self, issues):
        d = self.tmp / f"ep{len(list(self.tmp.iterdir()))}"
        shutil.copytree(FIXTURE, d)
        (d / "private" / "truth.json").write_text(
            json.dumps({"episode_id": EP, "issues": issues}), encoding="utf-8")
        return str(d)

    def score(self, issues, findings, steps=10):
        return ja.score_episode(self.episode(issues), {"episode_id": EP, "findings": findings},
                                steps)

    def expect(self, r, tp, fp, fn, reward, p=None, rc=None, f1=None):
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (tp, fp, fn))
        self.assertLessEqual(abs(r["return"] - reward), 1e-9)
        for key, value in (("precision", p), ("recall", rc), ("f1", f1)):
            if value is not None:
                self.assertLessEqual(abs(r[key] - value), 1e-9, key)

    def expect_invalid(self, r):
        self.assertEqual(r["return"], -1)
        for key in ("tp", "fp", "fn", "precision", "recall", "f1"):
            self.assertIsNone(r[key])


class BlockThreeTest(JuryFixture):
    def test_01_correct(self):
        self.expect(self.score([A], [finding()]), 1, 0, 0, Fraction(98, 100), 1, 1, 1)

    def test_02_empty_answer(self):
        self.expect(self.score([A], []), 0, 0, 1, -1, 0, 0, 0)

    def test_03_clean_and_empty(self):
        self.expect(self.score([], []), 0, 0, 0, Fraction(98, 100), 0, 0, 1)

    def test_04_clean_and_one_false(self):
        self.expect(self.score([], [finding()]), 0, 1, 0, -1, f1=0)

    def test_05_two_identical(self):
        r = self.score([A], [finding(), finding()])
        self.expect(r, 1, 1, 0, Fraction(47, 150), Fraction(1, 2), 1, Fraction(2, 3))
        self.assertLess(r["return"], self.score([A], [finding()])["return"])

    def test_06_wrong_type(self):
        self.expect(self.score([A], [finding(type="payment_allocation")]), 0, 1, 1, -1, f1=0)

    def test_07_other_existing_record(self):
        self.expect(self.score([A], [finding(affected_ids=["R2"])]), 0, 1, 1, -1)

    def test_08_amount_off_by_one(self):
        self.expect(self.score([A], [finding(claimed_amount_minor=10001)]), 0, 1, 1, -1)

    def test_09_other_currency(self):
        self.expect(self.score([A], [finding(currency="USD")]), 0, 1, 1, -1)

    def test_10_incomplete_evidence(self):
        self.expect(self.score([A], [finding(evidence_ids=["D1"])]), 0, 1, 1, -1)

    def test_11_missing_evidence_id(self):
        self.expect(self.score([A], [finding(evidence_ids=["D1", "U"])]), 0, 1, 1, -1)

    def test_12_mass_flagging(self):
        flags = [finding(type=t, affected_ids=[r]) for r in ("R1", "R2", "R3", "R4", "R5")
                 for t in TYPES]
        self.assertEqual(len(flags), 20)
        self.expect(self.score([A], flags), 1, 19, 0, Fraction(-871, 1050),
                    Fraction(1, 20), 1, Fraction(2, 21))

    def test_13_two_errors_one_found(self):
        self.expect(self.score([A, B], [finding()]), 1, 0, 1, Fraction(47, 150),
                    1, Fraction(1, 2), Fraction(2, 3))

    def test_14_two_errors_one_found_one_false(self):
        r = self.score([A, B], [finding(), finding(affected_ids=["R5"])])
        self.expect(r, 1, 1, 1, Fraction(-2, 100), Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))

    def test_15_16_17_step_cost(self):
        for steps, reward in ((0, 1), (50, Fraction(90, 100)), (100, Fraction(80, 100))):
            self.expect(self.score([A], [finding()], steps), 1, 0, 0, reward)

    def test_18_31_findings(self):
        self.expect_invalid(self.score([A], [finding()] * 31))
        self.expect(self.score([A], [finding()] * 30), 1, 29, 0,
                    2 * Fraction(2, 31) - 1 - Fraction(2, 100))

    def test_19_eleven_evidence_ids(self):
        ids = ["D1", "D2", "D3", "R1", "R2", "R3", "R4", "R5", "INV-1", "INV-2", "INV-3"]
        self.expect_invalid(self.score([A], [finding(evidence_ids=ids)]))
        self.expect(self.score([A], [finding(evidence_ids=ids[:10])]), 1, 0, 0,
                    Fraction(98, 100))

    def test_20_explanation_1001(self):
        self.expect_invalid(self.score([A], [finding(explanation="x" * 1001)]))
        self.expect(self.score([A], [finding(explanation="x" * 1000)]), 1, 0, 0,
                    Fraction(98, 100))

    def test_journal_records_the_reason(self):
        journal = self.tmp / "journal.jsonl"
        import os
        old = os.environ.get(ja.JOURNAL_ENV)
        os.environ[ja.JOURNAL_ENV] = str(journal)
        try:
            self.score([A], [finding()] * 31)
        finally:
            if old is None:
                del os.environ[ja.JOURNAL_ENV]
            else:
                os.environ[ja.JOURNAL_ENV] = old
        entry = json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])
        self.assertFalse(entry["valid"])
        self.assertEqual(entry["errors"][0]["code"], "TOO_MANY_FINDINGS")


AB = dict(A, affected_ids=["R1", "R2"])     # the M examples: affected {R1, R2}


class OpenExamplesTest(JuryFixture):
    def test_m01_repeated_affected_id(self):
        self.expect(self.score([AB], [finding(AB, affected_ids=["R2", "R1", "R1"])]),
                    1, 0, 0, Fraction(98, 100))

    def test_m02_extra_affected_id(self):
        self.expect(self.score([AB], [finding(AB, affected_ids=["R1", "R2", "R3"])]),
                    0, 1, 1, -1)

    def test_m03_extra_existing_evidence(self):
        self.expect(self.score([AB], [finding(AB, evidence_ids=["D2", "D1", "D3"])]),
                    1, 0, 0, Fraction(98, 100))

    def test_m04_unknown_evidence(self):
        self.expect(self.score([AB], [finding(AB, evidence_ids=["D1", "D2", "U"])]),
                    0, 1, 1, -1)

    def test_m05_eleven_with_repeats(self):
        self.expect_invalid(self.score([AB], [finding(AB, evidence_ids=["D2"] + ["D1"] * 10)]))

    def test_m06_currency_case_and_space(self):
        for cur in ("kzt", " KZT", "KZT ", "Kzt"):
            self.expect(self.score([AB], [finding(AB, currency=cur)]), 0, 1, 1, -1)

    def test_m07_amount_tau_zero(self):
        self.expect(self.score([AB], [finding(AB, claimed_amount_minor=10001)]), 0, 1, 1, -1)

    def test_m08_public_tau_one(self):
        tau1 = dict(AB, tolerance_minor=1)
        self.expect(self.score([tau1], [finding(tau1, claimed_amount_minor=10001)]),
                    1, 0, 0, Fraction(98, 100))
        self.expect(self.score([tau1], [finding(tau1, claimed_amount_minor=9999)]),
                    1, 0, 0, Fraction(98, 100))
        self.expect(self.score([tau1], [finding(tau1, claimed_amount_minor=10002)]),
                    0, 1, 1, -1)

    def test_m09_amount_string_or_bool(self):
        for bad in ("10000", True, 10000.0):
            self.expect_invalid(self.score([AB], [finding(AB, claimed_amount_minor=bad)]))

    def _graph(self):
        # A and B share type and affected_ids; F0 cites both evidence sets, F1 only A's
        a = dict(AB, issue_id="A", evidence_ids=["D1", "D2"])
        b = dict(AB, issue_id="B", evidence_ids=["D3"])
        both = finding(AB, evidence_ids=["D1", "D2", "D3"])
        only_a = finding(AB, evidence_ids=["D1", "D2"])
        return a, b, both, only_a

    def _pairs(self, issues, findings):
        r = grade({"episode_id": EP, "findings": findings}, episode_id=EP,
                  issues=[Issue.from_json(i) for i in issues],
                  public_ids={"R1", "R2", "R3", "R4", "R5", "D1", "D2", "D3"},
                  inspection_steps=10)
        return {m["issue_id"]: m["finding_index"] for m in r["matching"] if m["issue_id"]}, r

    def test_m10_maximum_not_greedy(self):
        a, b, both, only_a = self._graph()
        pairs, r = self._pairs([a, b], [both, only_a])
        self.assertEqual((r["TP"], r["FP"], r["FN"]), (2, 0, 0))
        self.assertEqual(pairs, {"A": 1, "B": 0})
        self.expect(self.score([a, b], [both, only_a]), 2, 0, 0, Fraction(98, 100))

    def test_m11_deterministic_choice(self):
        a, b, both, _ = self._graph()
        pairs, r = self._pairs([a, b], [both, copy.deepcopy(both)])
        self.assertEqual((r["TP"], pairs), (2, {"A": 0, "B": 1}))
        pairs, _ = self._pairs([b, a], [both, copy.deepcopy(both)])   # truth order irrelevant
        self.assertEqual(pairs, {"A": 0, "B": 1})

    def test_m12_two_identical_correct(self):
        self.expect(self.score([AB], [finding(AB), finding(AB)]), 1, 1, 0, Fraction(47, 150))

    def test_matching_rule_on_raw_graphs(self):
        # issues sorted by code points: "B" < "a"; smallest index first; maximum cardinality
        self.assertEqual(jury_matching([[0, 1], [0]], ["A", "B"]), [1, 0])
        self.assertEqual(jury_matching([[0, 1], [0, 1]], ["a", "B"]), [1, 0])
        self.assertEqual(jury_matching([[0], [0], [1]], ["A", "B"]), [0, None, 1])
        self.assertEqual(jury_matching([], []), [])


if __name__ == "__main__":
    unittest.main()
