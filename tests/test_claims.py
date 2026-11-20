"""Every claim of docs/claims.json points to tests that exist (and the check
runs them all, so a claim without a green test cannot pass the check)."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ClaimsTest(unittest.TestCase):
    def test_every_claim_has_existing_tests(self):
        claims = json.loads((ROOT / "docs" / "claims.json").read_text(encoding="utf-8"))
        loader = unittest.TestLoader()
        missing = []
        for claim in claims["claims"]:
            self.assertTrue(claim["tests"], claim["id"])
            for name in claim["tests"]:
                suite = loader.loadTestsFromName(name)
                if any(type(t).__name__ == "_FailedTest" for t in _flatten(suite)):
                    missing.append(f"{claim['id']}: {name}")
        self.assertEqual(missing, [])

    def test_artifacts_named_in_the_readme_exist(self):
        for path in ("Dockerfile", "LICENSE", "docs/DESIGN.md", "docs/REWARD.md",
                     "docs/LIMITATIONS.md", "docs/THREAT_MODEL.md", "schemas/findings.json",
                     "reports/BASELINES.md", "reports/FAILURE_ANALYSIS.md",
                     "reports/LEAK_AUDIT.md", "episodes.jsonl", "trajectories.jsonl"):
            self.assertTrue((ROOT / path).exists(), path)


class ReportsAreFreshTest(unittest.TestCase):
    def test_reports_carry_the_current_versions(self):
        from vouchai.version import ENV_VERSION, GENERATOR_VERSION
        stamp = f"env {ENV_VERSION}, generator {GENERATOR_VERSION}"
        for name in ("BASELINES.md", "FAILURE_ANALYSIS.md"):
            text = (ROOT / "reports" / name).read_text(encoding="utf-8")
            self.assertIn(stamp, text, f"{name} is stale: run python -m vouchai build-dataset "
                                       f"and python -m vouchai report")
        scorecard = (ROOT / "reports" / "SCORECARD.md").read_text(encoding="utf-8")
        self.assertIn(f"'env_version': '{ENV_VERSION}'", scorecard)


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


if __name__ == "__main__":
    unittest.main()
