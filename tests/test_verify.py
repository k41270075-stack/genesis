"""The independent verifier: reports A/B/C on generated episodes, and it must
notice tampering (otherwise it would prove nothing)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from vouchai.episode import generate_episode, save_episode
from vouchai_verify.__main__ import main as verify_main
from vouchai_verify.checks import report
from vouchai_verify.core import load

FULL = os.environ.get("VOUCHAI_CHECK_FULL") == "1"
SEEDS = range(120) if FULL else range(16)


def verified(seed, preset, tamper=None):
    ep = generate_episode(seed, preset)
    with tempfile.TemporaryDirectory() as tmp:
        save_episode(ep, tmp)
        if tamper:
            tamper(Path(tmp), ep)
        return report(load(tmp)), ep


class VerifierAgreesWithTruthTest(unittest.TestCase):
    def test_reports_are_green(self):
        for preset in ("jury_like", "L5", "clean"):
            for seed in SEEDS:
                result, ep = verified(seed, preset)
                with self.subTest(preset=preset, seed=seed):
                    self.assertTrue(result["A"]["ok"], result["A"]["problems"][:3])
                    self.assertTrue(result["B"]["ok"], result["B"]["problems"][:3])
                    self.assertTrue(result["C"]["ok"], result["C"]["problems"][:3])
                    self.assertEqual(result["B"]["declared"], len(ep.issues))

    def test_cli_and_passport(self):
        ep = generate_episode(3, "L5")
        with tempfile.TemporaryDirectory() as tmp:
            save_episode(ep, tmp)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(verify_main([tmp, "--passport", "--json"]), 0)
            self.assertTrue(json.loads(out.getvalue())["ok"])
            text = (Path(tmp) / "PASSPORT.md").read_text(encoding="utf-8")
        self.assertIn("**Answer.**", text)
        self.assertEqual(text.count("**Given.**"), len(ep.issues))


class VerifierCatchesTamperingTest(unittest.TestCase):
    def test_changed_amount_breaks_b(self):
        def tamper(folder, ep):
            path = folder / "public" / "ledger.csv"
            lines = path.read_text(encoding="utf-8").splitlines()
            # change one invoice issuing debit and its credit pair consistently
            target = next(r for r in ep.tables["ledger"] if r["account"] == "4000")
            out = []
            for line in lines:
                cells = line.split(",")
                if cells[0] != "row_id" and cells[1] == target["timestamp"] \
                        and cells[2] in ("1200", "4000") and cells[7] == target["invoice_id"]:
                    if cells[3]:
                        cells[3] = str(int(cells[3]) + 500)
                    if cells[4]:
                        cells[4] = str(int(cells[4]) + 500)
                out.append(",".join(cells))
            path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")

        result, _ = verified(5, "clean", tamper)
        self.assertFalse(result["B"]["ok"])
        self.assertTrue(any("undeclared" in p for p in result["B"]["problems"]))

    def test_dropped_issue_breaks_b(self):
        def tamper(folder, ep):
            path = folder / "private" / "truth.json"
            truth = json.loads(path.read_text(encoding="utf-8"))
            truth["issues"] = truth["issues"][1:]
            path.write_text(json.dumps(truth), encoding="utf-8")

        result, ep = verified(2, "L3", tamper)
        self.assertTrue(ep.issues)
        self.assertFalse(result["B"]["ok"])

    def test_insufficient_evidence_breaks_c(self):
        def tamper(folder, ep):
            path = folder / "private" / "truth.json"
            truth = json.loads(path.read_text(encoding="utf-8"))
            for issue in truth["issues"]:
                issue["evidence_sets"] = [s[:1] for s in issue["evidence_sets"]]
            path.write_text(json.dumps(truth), encoding="utf-8")

        result, _ = verified(2, "L3", tamper)
        self.assertFalse(result["C"]["ok"])

    def test_wrong_declared_amount_breaks_b_and_c(self):
        def tamper(folder, ep):
            path = folder / "private" / "truth.json"
            truth = json.loads(path.read_text(encoding="utf-8"))
            truth["issues"][0]["expected_amount_minor"] += 100
            path.write_text(json.dumps(truth), encoding="utf-8")

        result, _ = verified(2, "L3", tamper)
        self.assertFalse(result["B"]["ok"])
        self.assertFalse(result["C"]["ok"])


if __name__ == "__main__":
    unittest.main()
