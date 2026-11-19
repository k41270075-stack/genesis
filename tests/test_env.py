"""Environment contract: reset/step, tools, limits, termination, modes, leaks."""

import json
import tempfile
import unittest

from vouchai.episode import generate_episode, oracle_findings, save_episode
from vouchai.jsonsafe import dumps_canonical, roundtrips
from vouchai.server.local import LocalEnv, RunFinalized

TABLES = ("ledger", "invoices", "payments", "fx")
ID_FIELD = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id", "fx": "id"}
PRIVATE_TOKENS = ("iss_", "mutation", "provenance", "expected_amount", "carrier_row",
                  "evidence_slots", "copy_of", "attempt")


def act(name, **params):
    return dict(action=name, **params)


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


class ResetTest(unittest.TestCase):
    def test_first_observation(self):
        env = LocalEnv(mode="eval")
        obs, info = env.reset(3, "smoke")
        self.assertEqual(set(obs), {"task", "manifest", "policy", "tools", "limits",
                                    "steps_remaining"})
        self.assertEqual(obs["steps_remaining"], 100)
        self.assertEqual(obs["tools"], ["list_records", "get_record", "get_document",
                                        "calculator", "submit"])
        self.assertEqual(info["episode_id"], obs["manifest"]["episode_id"])
        self.assertIn("findings", obs["policy"])
        self.assertTrue(roundtrips(obs) and roundtrips(info))
        text = dumps_canonical([obs, info])
        self.assertNotIn('"seed"', text)
        self.assertNotIn('"config"', text)
        for token in PRIVATE_TOKENS:
            self.assertNotIn(token, text)

    def test_seed_handling(self):
        env = LocalEnv(mode="train")
        for bad in (True, -1, "5", 1.0):
            with self.assertRaises(ValueError):
                env.reset(bad, "smoke")
        env.reset(2 ** 64 - 1, "smoke")
        a, _ = env.reset(None, None)
        b, _ = env.reset(None, None)
        self.assertNotEqual(a["manifest"]["episode_id"], b["manifest"]["episode_id"])

    def test_reset_isolates_and_closes_previous_episode(self):
        env = LocalEnv(mode="eval")
        env.reset(1, "smoke")
        env.step(act("calculator", expression="1+1"))
        env.reset(2, "smoke")
        obs, *_ = env.step(act("calculator", expression="2"))
        self.assertEqual(obs["steps_remaining"], 99)
        self.assertEqual(env.results[0]["termination"], "reset")
        self.assertEqual(env.finalize()["episodes"][1]["termination"], "finalize")
        with self.assertRaises(RunFinalized):
            env.reset(3, "smoke")

    def test_episode_dir(self):
        ep = generate_episode(4, "smoke")
        with tempfile.TemporaryDirectory() as tmp:
            save_episode(ep, tmp)
            env = LocalEnv(mode="train")
            obs, info = env.reset(options={"episode_dir": tmp})
        self.assertEqual(info["episode_id"], ep.episode_id)
        _, reward, terminated, *_ = env.step(act("submit", findings=oracle_findings(ep)))
        self.assertTrue(terminated)
        self.assertEqual(reward, 1.0)


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.env = LocalEnv(mode="eval")
        self.obs, self.info = self.env.reset(11, "default")
        self.episode = generate_episode(11, "default")

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.assertEqual(reward, 0.0)
        self.assertFalse(terminated and truncated)
        self.assertTrue(roundtrips(obs))
        self.assertEqual(set(obs), {"result", "error", "steps_remaining"})
        return obs

    def test_pages_cover_tables_without_gaps(self):
        for table in TABLES:
            seen, token = [], None
            while True:
                obs = self.step(act("list_records", table=table, cursor=token, limit=50))
                self.assertIsNone(obs["error"])
                self.assertLessEqual(len(obs["result"]["rows"]), 50)
                seen += obs["result"]["rows"]
                token = obs["result"]["next_cursor"]
                if token is None:
                    break
            self.assertEqual(seen, self.episode.tables[table])
            ids = [r[ID_FIELD[table]] for r in seen]
            self.assertEqual(len(ids), len(set(ids)))

    def test_table_file_names_and_cursor_stability(self):
        a = self.step(act("list_records", table="ledger.csv", limit=5))
        b = self.step(act("list_records", table="ledger", limit=5))
        self.assertEqual(a["result"], b["result"])

    def test_records_and_documents(self):
        inv = self.episode.tables["invoices"][0]
        pay = self.episode.tables["payments"][0]
        row = self.episode.tables["ledger"][0]
        fx = self.episode.tables["fx"][0]
        self.assertEqual(self.step(act("get_record", table="ledger", id=row["row_id"]))
                         ["result"]["record"], row)
        self.assertEqual(self.step(act("get_record", table="fx", id=fx["id"]))
                         ["result"]["record"], fx)
        self.assertEqual(self.step(act("get_record", table="invoices", id=inv["invoice_id"]))
                         ["result"]["record"], inv)
        for ident in (inv["doc_id"], inv["invoice_id"]):
            doc = self.step(act("get_document", doc_id=ident))["result"]["document"]
            self.assertEqual(doc["invoice_id"], inv["invoice_id"])
            self.assertEqual(doc["document_type"], "invoice")
            self.assertTrue(doc["notes"])
        doc = self.step(act("get_document", doc_id=pay["payment_id"]))["result"]["document"]
        self.assertEqual(doc["document_type"], "payment")

    def test_bounded_errors_spend_a_step(self):
        cases = [
            (None, "MALFORMED_ACTION"), ([], "MALFORMED_ACTION"), ("nope", "MALFORMED_ACTION"),
            ('{"action":"submit","action":"calculator"}', "MALFORMED_ACTION"),
            ({"action": 5}, "MALFORMED_ACTION"),
            (act("rm -rf"), "UNKNOWN_ACTION"),
            (act("list_records", table="truth"), "UNKNOWN_TABLE"),
            (act("list_records", table="../private/truth.json"), "UNKNOWN_TABLE"),
            (act("list_records"), "INVALID_ARGUMENT"),
            (act("get_record", table="ledger", id="R000000000"), "UNKNOWN_ID"),
            (act("get_record", table="ledger", id=5), "INVALID_ARGUMENT"),
            (act("get_document", doc_id="iss_01"), "UNKNOWN_ID"),
            (act("list_records", table="ledger", cursor="AAAAAAAA"), "INVALID_CURSOR"),
            (act("calculator", expression="__import__('os')"), "CALC_ERROR"),
        ]
        for limit in (0, 51, "50", True, 50.0, -1):
            cases.append((act("list_records", table="fx", limit=limit), "LIMIT_OUT_OF_RANGE"))
        remaining = 100
        for action, code in cases:
            obs = self.step(action)
            remaining -= 1
            self.assertEqual(obs["error"]["code"], code, repr(action))
            self.assertEqual(obs["steps_remaining"], remaining)
            self.assertIsNone(obs["result"])
            self.assertNotIn("Traceback", json.dumps(obs))

    def test_cursor_of_another_episode_is_rejected(self):
        token = self.step(act("list_records", table="ledger", limit=10))["result"]["next_cursor"]
        self.env.reset(12, "default")
        obs = self.step(act("list_records", table="ledger", cursor=token))
        self.assertEqual(obs["error"]["code"], "INVALID_CURSOR")


class TerminationTest(unittest.TestCase):
    def test_step_before_reset(self):
        env = LocalEnv()
        obs, reward, term, trunc, info = env.step(act("calculator", expression="1"))
        self.assertEqual(obs["error"]["code"], "RESET_REQUIRED")
        self.assertEqual((reward, term, trunc), (0.0, False, False))

    def test_submit_terminates_and_flags_stick(self):
        env = LocalEnv(mode="eval")
        env.reset(5, "smoke")
        obs, reward, term, trunc, info = env.step(act("submit", findings={"episode_id": "x"}))
        self.assertEqual((reward, term, trunc), (0.0, True, False))
        self.assertTrue(info["reward_withheld"])
        for _ in range(3):
            obs, reward, term, trunc, info = env.step(act("calculator", expression="1"))
            self.assertEqual(obs["error"]["code"], "EPISODE_ENDED")
            self.assertEqual((reward, term, trunc), (0.0, True, False))
        self.assertEqual(env.results[0]["steps"], 1)

    def test_eval_terminal_observation_is_identical_for_valid_and_invalid(self):
        outs = []
        for findings in (oracle_findings(generate_episode(5, "smoke")), "garbage"):
            env = LocalEnv(mode="eval")
            env.reset(5, "smoke")
            outs.append(env.step(act("submit", findings=findings)))
            results = env.finalize()["episodes"][0]
            self.assertEqual(results["valid"], findings != "garbage")
        self.assertEqual(dumps_canonical(outs[0]), dumps_canonical(outs[1]))

    def test_train_returns_terminal_reward(self):
        for seed in range(6):
            ep = generate_episode(seed, "jury_like")
            env = LocalEnv(mode="train")
            env.reset(seed, "jury_like")
            env.step(act("list_records", table="ledger"))
            _, reward, term, trunc, info = env.step(act("submit", findings=oracle_findings(ep)))
            self.assertTrue(term and not trunc)
            self.assertAlmostEqual(reward, 1 - 0.002 * 1, places=12)
            self.assertEqual(info["grade"]["F1"], 1.0)

    def test_hundred_steps_truncate_with_empty_answer(self):
        env = LocalEnv(mode="train")
        env.reset(2, "clean")
        for i in range(99):
            _, reward, term, trunc, _ = env.step(act("calculator", expression="1"))
            self.assertEqual((reward, term, trunc), (0.0, False, False))
        obs, reward, term, trunc, info = env.step(act("calculator", expression="1"))
        self.assertEqual((term, trunc, info["termination"]), (False, True, "max_steps"))
        self.assertEqual(obs["result"], {"value": "1"})
        self.assertAlmostEqual(reward, 0.8, places=12)   # clean books, empty answer, 100 steps
        self.assertEqual(env.results[0]["inspection_steps"], 100)

    def test_submit_on_the_hundredth_action(self):
        env = LocalEnv(mode="train")
        env.reset(2, "clean")
        for _ in range(99):
            env.step(act("calculator", expression="1"))
        _, reward, term, trunc, _ = env.step(act("submit", findings={
            "episode_id": env.results and "" or env._episode.episode_id, "findings": []}))
        self.assertEqual((term, trunc), (True, False))
        self.assertAlmostEqual(reward, 1 - 0.002 * 99, places=12)

    def test_time_limit(self):
        clock = FakeClock()
        env = LocalEnv(mode="train", time_limit_s=60, clock=clock)
        env.reset(2, "clean")
        clock.now = 59
        _, _, term, trunc, _ = env.step(act("calculator", expression="1"))
        self.assertFalse(term or trunc)
        clock.now = 61
        obs, reward, term, trunc, info = env.step(act("submit", findings={}))
        self.assertEqual((term, trunc, info["termination"]), (False, True, "time_limit"))
        self.assertIsNone(obs["result"])


class ReproducibilityTest(unittest.TestCase):
    def test_same_actions_same_stream(self):
        actions = [act("list_records", table="ledger", limit=7),
                   act("list_records", table="payments"), act("calculator", expression="2/3"),
                   act("get_document", doc_id="nope"), "{bad",
                   act("submit", findings={"episode_id": "?", "findings": []})]

        def run():
            env = LocalEnv(mode="train")
            out = [env.reset(21, "jury_like")]
            first = out[0][0]["manifest"]["episode_id"]
            for a in actions:
                if isinstance(a, dict) and a.get("action") == "submit":
                    a = act("submit", findings={"episode_id": first, "findings": []})
                out.append(env.step(a))
            return dumps_canonical(out)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
