"""VouchAIEnv: the jury's entry point, zone B in a child process."""

import unittest

from vouchai import VouchAIEnv
from vouchai.episode import generate_episode, oracle_findings
from vouchai.jsonsafe import dumps_canonical
from vouchai.server.local import LocalEnv


class ProcessEnvTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = VouchAIEnv()          # no argument is required

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_contract_and_oracle_through_finalize(self):
        env = self.env
        seeds = (31, 32, 33)
        for seed in seeds:
            obs, info = env.reset(seed, "jury_like")
            self.assertEqual(obs["steps_remaining"], 100)
            step = env.step({"action": "list_records", "table": "fx", "limit": 2})
            self.assertEqual(len(step), 5)
            self.assertEqual(step[1], 0.0)
            findings = oracle_findings(generate_episode(seed, "jury_like"))
            obs, reward, term, trunc, info = env.step({"action": "submit", "findings": findings})
            self.assertEqual((reward, term, trunc), (0.0, True, False))
        results = env.finalize()["episodes"]
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r["F1"], 1.0)
            self.assertAlmostEqual(r["return"], 0.998, places=12)
            self.assertEqual(r["termination"], "submit")

    def test_same_observations_as_in_process(self):
        actions = [{"action": "list_records", "table": "ledger", "limit": 3},
                   {"action": "get_document", "doc_id": "missing"}, "[]",
                   {"action": "calculator", "expression": "10/4"}]
        with VouchAIEnv(mode="eval") as remote:
            local = LocalEnv(mode="eval")
            a = [remote.reset(41, "default")[0]] + [remote.step(x)[0] for x in actions]
            b = [local.reset(41, "default")[0]] + [local.step(x)[0] for x in actions]
        self.assertEqual(dumps_canonical(a), dumps_canonical(b))

    def test_bad_inputs(self):
        with VouchAIEnv(mode="train") as env:
            with self.assertRaises(ValueError):
                env.reset(True, None)
            with self.assertRaises(ValueError):
                env.reset(1, {"preset": "nope"})
            env.reset(1, "smoke")
            obs, *_ = env.step({"action": "calculator", "expression": object()})
            self.assertEqual(obs["error"]["code"], "MALFORMED_ACTION")
            obs, *_ = env.step({"action": "calculator", "x": float("nan")})
            self.assertEqual(obs["error"]["code"], "MALFORMED_ACTION")
        with self.assertRaises(ValueError):
            VouchAIEnv(mode="eval", isolation="inproc")
        for bad in (-1, 1.5, True, "60"):
            with self.assertRaises(ValueError):
                VouchAIEnv(time_limit_s=bad)

    def test_hostile_reset_and_step_do_not_kill_the_run(self):
        from vouchai.server.client import EnvProtocolError
        with VouchAIEnv(mode="train") as env:
            env.reset(3, "smoke")
            for bad in ({"company": 5}, {"size": {"customers": {"range": 5}}}, [1], 7):
                with self.assertRaises(ValueError):
                    env.reset(1, bad)
            env.reset(3, {"preset": "smoke", "mix": "clean"})     # preset next to overrides
            deep = {"action": "calculator", "expression": "1"}
            node = deep
            for _ in range(5000):
                node["x"] = {}
                node = node["x"]
            for action in (deep, "x" * 1_100_000, "ж" * 200_000):
                obs, *_ = env.step(action)
                self.assertEqual(obs["error"]["code"], "MALFORMED_ACTION")
            huge = {"action": "submit", "findings": {"episode_id": "x", "findings": [
                {"affected_ids": ["a"] * 80_000}]}}
            _, reward, term, trunc, _ = env.step(huge)
            self.assertEqual((reward, term, trunc), (-1.0, True, False))
            self.assertEqual(len(env.finalize()["episodes"]), 2)
        with self.assertRaises(EnvProtocolError):
            env.step({"action": "calculator", "expression": "1"})

    def test_flat_submit_form(self):
        ep = generate_episode(51, "smoke")
        flat = {"action": "submit", **oracle_findings(ep)}
        with VouchAIEnv(mode="train") as env:
            env.reset(51, "smoke")
            _, reward, term, _, _ = env.step(flat)
        self.assertTrue(term)
        self.assertEqual(reward, 1.0)


if __name__ == "__main__":
    unittest.main()
