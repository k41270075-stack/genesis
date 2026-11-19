"""Adapters: the four baselines, a foreign Python policy and a policy in another
process all run through the same harness."""

import sys
import unittest

from vouchai.adapters import BASELINE_NAMES, baseline, python_policy, subprocess_policy
from vouchai.harness.runner import run

SCHEDULE = [(8000, "jury_like"), (8001, "clean")]

CHILD = r"""
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg["event"] == "close":
        break
    obs = msg["observation"]
    if msg["event"] == "reset":
        episode = obs["manifest"]["episode_id"]
        print(json.dumps({"action": {"action": "list_records", "table": "fx", "limit": 5}}))
    else:
        print(json.dumps({"action": {"action": "submit",
                                     "findings": {"episode_id": episode, "findings": []}}}))
    sys.stdout.flush()
"""


class GymStyle:
    """A foreign policy with predict() returning (action, state)."""

    def predict(self, observation):
        return {"action": "submit", "findings": {
            "episode_id": observation.get("manifest", {}).get("episode_id", "?"),
            "findings": []}}, None


class AdaptersTest(unittest.TestCase):
    def test_four_baselines(self):
        for name in BASELINE_NAMES:
            r = run(baseline(name, SCHEDULE), SCHEDULE)
            self.assertEqual(r["summary"]["episodes"], 2, name)
        self.assertEqual(run(baseline("oracle", SCHEDULE), SCHEDULE)["summary"]["mean_return"],
                         1.0)

    def test_foreign_python_policy(self):
        r = run(python_policy(GymStyle()), SCHEDULE)
        self.assertEqual(r["summary"]["invalid"], 0)

    def test_subprocess_policy(self):
        policy = subprocess_policy([sys.executable, "-c", CHILD])
        try:
            r = run(policy, SCHEDULE)
        finally:
            policy.close()
        self.assertEqual([e["steps"] for e in r["episodes"]], [2, 2])
        self.assertEqual(r["summary"]["invalid"], 0)


if __name__ == "__main__":
    unittest.main()
