"""Reproducibility and generalization: golden hashes, other processes, paired
transformations (rename, hostile rename, shuffle, re-offset), replay."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vouchai.episode import generate_episode, load_episode, oracle_findings, save_episode
from vouchai.harness.replay import replay
from vouchai.harness.runner import make_policy, run
from vouchai.harness.transform import transform
from vouchai.render import fx_csv, jsonl, ledger_csv
from vouchai.server.local import LocalEnv
from vouchai_verify.checks import report
from vouchai_verify.core import load

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((ROOT / "tests" / "golden.json").read_text(encoding="utf-8"))
FULL = os.environ.get("VOUCHAI_CHECK_FULL") == "1"
PAIR_SEEDS = range(3000, 3020) if FULL else range(3000, 3006)


def tables_sha(ep):
    return hashlib.sha256(ledger_csv(ep.tables["ledger"]) + jsonl(ep.tables["invoices"])
                          + jsonl(ep.tables["payments"]) + fx_csv(ep.tables["fx"])).hexdigest()


class GoldenTest(unittest.TestCase):
    def test_golden_hashes(self):
        """Same seed, config and version -> the same bytes on every OS and Python."""
        for case in GOLDEN:
            ep = generate_episode(case["seed"], case["config"])
            with self.subTest(seed=case["seed"], config=case["config"]):
                self.assertEqual(ep.episode_id, case["episode_id"])
                self.assertEqual(tables_sha(ep), case["tables_sha256"])
                self.assertEqual(len(ep.issues), case["issues"])

    def test_other_process_other_hash_seed(self):
        case = GOLDEN[0]
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from vouchai.episode import generate_episode; "
                f"print(generate_episode({case['seed']}, {case['config']!r}).episode_id)")
        for hash_seed in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            out = subprocess.run([sys.executable, "-c", code, str(ROOT)], env=env,
                                 capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(out, case["episode_id"])


class PairedTransformTest(unittest.TestCase):
    def test_oracle_verifier_and_policy_survive_transformations(self):
        for seed in PAIR_SEEDS:
            ep = generate_episode(seed, "jury_like")
            with tempfile.TemporaryDirectory() as tmp:
                a = save_episode(ep, Path(tmp) / "a")
                folder_a = {"episode_dir": str(a)}
                base = run(make_policy("simple_reconciler"), [(0, None)],
                           options_for=lambda s, c, o=folder_a: o)["summary"]
                for hostile in (False, True):
                    with self.subTest(seed=seed, hostile=hostile):
                        b = transform(a, Path(tmp) / f"b{hostile}", seed=seed, hostile=hostile)
                        self.assertTrue(report(load(b))["ok"])
                        env = LocalEnv(mode="train", time_limit_s=None)
                        env.reset(options={"episode_dir": str(b)})
                        _, reward, *_ = env.step({"action": "submit",
                                                  "findings": oracle_findings(load_episode(b))})
                        self.assertEqual(reward, 1.0)
                        # the jury's pair: rename + shuffle, the same reward with new IDs
                        c = transform(a, Path(tmp) / f"c{hostile}", seed=seed, hostile=hostile,
                                      reoffset=False)
                        folder_c = {"episode_dir": str(c)}
                        other = run(make_policy("simple_reconciler"), [(0, None)],
                                    options_for=lambda s, c_, o=folder_c: o)["summary"]
                        self.assertEqual(other["mean_return"], base["mean_return"])
                        self.assertEqual((other["TP"], other["FP"]), (base["TP"], base["FP"]))

    def test_render_seeds_pair(self):
        for seed in PAIR_SEEDS:
            plain = generate_episode(seed, "jury_like")
            moved = generate_episode(seed, {"preset": "jury_like",
                                            "overrides": {"render": {"id_seed": 5,
                                                                     "order_seed": 6}}})
            self.assertNotEqual(plain.episode_id, moved.episode_id)
            for ep in (plain, moved):
                env = LocalEnv(mode="train", time_limit_s=None)
                env.reset(seed, {"preset": "jury_like", "overrides": {"render": {
                    "id_seed": 0 if ep is plain else 5, "order_seed": 0 if ep is plain else 6}}})
                _, reward, *_ = env.step({"action": "submit", "findings": oracle_findings(ep)})
                self.assertEqual(reward, 1.0)


class ReplayTest(unittest.TestCase):
    def test_replay_reproduces_every_step(self):
        schedule = [(4000 + s, "jury_like") for s in range(3)]
        result = run(make_policy("simple_reconciler"), schedule, record=True)
        index = {}
        for (seed, config), ep_result in zip(schedule, result["episodes"]):
            index[ep_result["episode_id"]] = {"seed": seed, "config": config}
        self.assertEqual(replay(result["trajectories"], index), [])
        tampered = [dict(r) for r in result["trajectories"]]
        tampered[3] = dict(tampered[3], reward=0.5)
        self.assertTrue(replay(tampered, index))

    def test_published_trajectories_match_the_index(self):
        path = ROOT / "trajectories.jsonl"
        if not path.is_file():
            self.skipTest("dataset not built")
        index = {}
        with open(ROOT / "episodes.jsonl", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                index[row["episode_id"]] = row
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        fields = {"episode_id", "step", "action", "observation", "reward", "terminated",
                  "truncated"}
        self.assertTrue(all(fields <= set(r) for r in rows))
        self.assertFalse(any(r.get("policy") == "oracle" for r in rows))
        sample_ids = sorted(index)[:2]
        sample = [r for r in rows if r["episode_id"] in sample_ids]
        self.assertEqual(replay(sample, index), [])


if __name__ == "__main__":
    unittest.main()
