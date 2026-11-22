"""judge_adapter.py: the jury's single way of connecting (check definitions,
20.11.2026, «Единый способ подключения»)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import judge_adapter as ja
from vouchai.episode import load_episode, oracle_findings


class AdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="vouchai-adapter-"))
        cls.ep_dir = str(cls.tmp / "ep")
        ja.generate_episode(11, {"preset": "smoke"}, cls.ep_dir)
        cls.episode = load_episode(cls.ep_dir)
        cls.env = ja.make_env()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def closed(self):
        return self.env.reset(11, {"mode": "closed", "episode_dir": self.ep_dir,
                                   "team_config": {"preset": "smoke"}})

    def step(self, name, **args):
        return self.env.step({"name": name, "args": args})

    def test_generate_writes_public_and_closed_files(self):
        root = Path(self.ep_dir)
        self.assertEqual(sorted(p.name for p in (root / "public").iterdir()),
                         ["fx.csv", "invoices.jsonl", "ledger.csv", "manifest.json",
                          "payments.jsonl", "policy.json"])
        self.assertTrue((root / "private" / "truth.json").is_file())
        self.assertTrue((root / "private" / "provenance.json").is_file())
        for issue in json.loads((root / "private" / "truth.json").read_text("utf-8"))["issues"]:
            self.assertTrue(issue["evidence_ids"])      # the field a jury oracle cites

    def test_first_observation(self):
        obs, info = self.closed()
        self.assertEqual(set(obs), {"task", "manifest", "policy", "remaining_steps"})
        self.assertEqual(obs["remaining_steps"], 100)
        self.assertNotIn("steps_remaining", obs)
        self.assertEqual(info["mode"], "closed")
        text = json.dumps([obs, info])
        self.assertNotIn('"iss_', text)
        self.assertNotIn("expected_amount_minor", text)
        self.assertNotIn("evidence_slots", text)
        self.assertEqual(set(info["action_formats"]), set(info["tools"]))
        for fmt in info["action_formats"].values():
            self.assertIn("name", fmt)
            self.assertIn("args", fmt)

    def test_results_in_the_jury_shape(self):
        self.closed()
        obs, reward, term, trunc, _ = self.step("list_records", table="ledger", cursor=None,
                                                limit=50)
        self.assertEqual(set(obs), {"result", "error", "remaining_steps"})
        self.assertEqual(set(obs["result"]), {"records", "next_cursor"})
        self.assertLessEqual(len(obs["result"]["records"]), 50)
        self.assertEqual((reward, term, trunc), (0, False, False))
        self.assertIs(type(term), bool)
        row = obs["result"]["records"][0]
        obs, *_ = self.step("get_record", table="ledger", id=row["row_id"])
        self.assertEqual(obs["result"], row)
        doc = self.episode.tables["invoices"][0]
        obs, *_ = self.step("get_document", doc_id=doc["doc_id"])
        self.assertEqual(obs["result"]["doc_id"], doc["doc_id"])
        obs, *_ = self.step("calculator", expression="0.1+0.2")
        self.assertEqual(obs["result"], "0.3")
        self.assertEqual(obs["remaining_steps"], 96)

    def test_bounded_errors_spend_a_step(self):
        self.closed()
        cases = [({"name": "get_record", "args": {"table": "ledger", "id": "U-404"}},
                  "UNKNOWN_ID"),
                 ({"name": "get_document", "args": {"doc_id": "U-404"}}, "UNKNOWN_ID"),
                 ({"name": "explode", "args": {}}, "UNKNOWN_ACTION"),
                 ({"name": "calculator", "args": {"expression": "open('/etc/passwd')"}},
                  "CALC_ERROR"),
                 ("not an object", "MALFORMED_ACTION"),
                 ({"args": {}}, "MALFORMED_ACTION"),
                 ({"name": "list_records", "args": [1]}, "MALFORMED_ACTION")]
        for n, (action, code) in enumerate(cases, start=1):
            obs, reward, term, trunc, _ = self.env.step(action)
            self.assertEqual(obs["error"]["code"], code, action)
            self.assertEqual(obs["remaining_steps"], 100 - n)
            self.assertFalse(term or trunc)
        obs, *_ = self.step("list_records", table="fx", cursor=None, limit=1)
        self.assertIsNone(obs["error"])                 # access survives errors

    def test_submit_closed_and_score(self):
        self.closed()
        for _ in range(3):
            self.step("calculator", expression="1+1")
        findings = oracle_findings(self.episode)
        obs, reward, term, trunc, info = self.step("submit", findings=findings)
        self.assertEqual(obs["result"], {"accepted": True})
        self.assertEqual((reward, term, trunc), (0, True, False))
        self.assertNotIn("grade", info)
        obs, *_ = self.step("calculator", expression="1")
        self.assertEqual(obs["error"]["code"], "EPISODE_ENDED")
        score = ja.score_episode(self.ep_dir, findings, 3)
        self.assertEqual((score["tp"], score["fp"], score["fn"]),
                         (len(self.episode.issues), 0, 0))
        self.assertAlmostEqual(score["return"], 1 - 0.006, places=9)
        self.assertEqual(set(score), {"tp", "fp", "fn", "precision", "recall", "f1", "return"})

    def test_submit_on_action_100_and_truncation(self):
        self.closed()
        for _ in range(99):
            obs, reward, term, trunc, _ = self.step("calculator", expression="1")
        self.assertEqual((obs["remaining_steps"], term, trunc), (1, False, False))
        obs, reward, term, trunc, _ = self.step(
            "submit", findings={"episode_id": self.episode.episode_id, "findings": []})
        self.assertEqual((obs["result"], term, trunc), ({"accepted": True}, True, False))
        self.closed()
        for _ in range(100):
            obs, reward, term, trunc, _ = self.step("calculator", expression="1")
        self.assertEqual((term, trunc, reward), (False, True, 0))
        obs, *_ = self.step("submit", findings=oracle_findings(self.episode))
        self.assertEqual(obs["error"]["code"], "EPISODE_ENDED")

    def test_train_mode_returns_the_reward(self):
        obs, info = self.env.reset(5, {"mode": "train", "team_config": {"preset": "smoke"}})
        self.assertEqual(info["mode"], "train")
        obs, reward, term, trunc, info = self.step(
            "submit", findings={"episode_id": obs["manifest"]["episode_id"], "findings": []})
        self.assertTrue(term)
        self.assertEqual(reward, -1.0)          # two errors missed
        self.closed()                           # and back to closed mode

    def test_broken_submit_envelope_is_an_invalid_submit(self):
        _, info = self.env.reset(5, {"mode": "train", "team_config": {"preset": "smoke"}})
        obs, reward, term, trunc, info = self.env.step({"name": "submit", "args": "oops"})
        self.assertEqual((reward, term), (-1.0, True))
        self.assertFalse(info["grade"]["valid"])

    def test_jury_made_fixture_loads_through_episode_dir(self):
        # organizers, 21.11: test 12 uses one jury fixture for all teams (manifest,
        # ledger, invoices, payments, fx, policy + closed truth), loaded via episode_dir
        from vouchai.episode import read_tables
        src = Path(__file__).resolve().parent.parent / "examples" / "matcher_fixture"
        tables = read_tables(src / "public")
        d = self.tmp / "jury_fixture"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"episode_id": "jury_fx_12",
                                                     "base_currency": "KZT"}), "utf-8")
        (d / "policy.json").write_text("{}", "utf-8")
        (d / "ledger.json").write_text(json.dumps(tables["ledger"]), "utf-8")
        (d / "invoices.json").write_text(json.dumps(tables["invoices"]), "utf-8")
        (d / "payments.json").write_text("[]", "utf-8")
        (d / "fx.json").write_text("[]", "utf-8")
        (d / "truth.json").write_text(json.dumps([{                # no issue_id, a bare list
            "type": "duplicate_invoice", "affected_ids": ["R1"], "expected_amount_minor": 10000,
            "currency": "KZT", "evidence_ids": ["D1", "D2"]}]), "utf-8")
        obs, _ = self.env.reset(0, {"mode": "closed", "episode_dir": str(d), "team_config": {}})
        self.assertEqual(obs["manifest"]["episode_id"], "jury_fx_12")
        o, *_ = self.step("list_records", table="ledger", cursor=None, limit=50)
        self.assertEqual(len(o["result"]["records"]), 5)
        o, *_ = self.step("get_record", table="ledger", id="R1")
        self.assertEqual(o["result"]["debit_minor"], 10000)
        o, *_ = self.step("get_document", doc_id="D2")
        self.assertEqual(o["result"]["invoice_id"], "INV-2")
        findings = {"findings": [{"type": "duplicate_invoice", "affected_ids": ["R1"],   # no
                                  "claimed_amount_minor": 10000, "currency": "KZT",      # id
                                  "evidence_ids": ["D1", "D2"], "explanation": "twice"}]}
        o, r, term, _, _ = self.step("submit", findings=findings)
        self.assertEqual((o["result"], r, term), ({"accepted": True}, 0, True))
        score = ja.score_episode(str(d), findings, 3)
        self.assertEqual((score["tp"], score["fp"], score["fn"]), (1, 0, 0))
        self.assertAlmostEqual(score["return"], 0.994, places=9)

    def test_reviewer_holes_stay_closed(self):
        import shutil as sh
        import time
        # train without team_config: the jury keys never reach the generator
        obs, info = self.env.reset(4, {"mode": "train"})
        self.assertEqual(info["mode"], "train")
        # a closed folder without private/ (the closed files stay with the jury)
        pub_only = self.tmp / "public_only"
        sh.copytree(Path(self.ep_dir) / "public", pub_only / "public")
        obs, _ = self.env.reset(0, {"mode": "closed", "episode_dir": str(pub_only)})
        self.assertEqual(obs["remaining_steps"], 100)
        # a failed reset leaves nothing playable
        with self.assertRaises((ValueError, RuntimeError)):    # RuntimeError: protocol
            self.env.reset(0, {"mode": "closed", "episode_dir": str(self.tmp / "missing")})
        obs, *_ = self.step("calculator", expression="1")
        self.assertEqual(obs["error"]["code"], "RESET_REQUIRED")
        # a crashed zone B: a bounded answer, then reset brings a new one
        self.closed()
        self.env._env._proc.kill()
        self.env._env._proc.wait()
        obs, r, term, trunc, info = self.step("calculator", expression="1")
        self.assertEqual((obs["error"]["code"], trunc), ("INTERNAL_ERROR", True))
        obs, _ = self.closed()
        self.assertEqual(obs["remaining_steps"], 100)
        # the time limit runs from the start of reset
        env = ja.JudgeEnv(time_limit_s=1)
        try:
            t0 = time.monotonic()
            env.reset(0, {"mode": "closed", "episode_dir": self.ep_dir})
            time.sleep(max(0, 1.05 - (time.monotonic() - t0)))
            obs, _, term, trunc, info = env.step({"name": "calculator",
                                                  "args": {"expression": "1"}})
            self.assertEqual((trunc, info.get("termination")), (True, "time_limit"))
        finally:
            env.close()

    def test_step_before_reset_is_bounded(self):
        env = ja.make_env()
        try:
            obs, r, term, trunc, _ = env.step({"name": "calculator", "args": {"expression": "1"}})
            self.assertEqual((obs["error"]["code"], r, term, trunc),
                             ("RESET_REQUIRED", 0, False, False))
        finally:
            env.close()

    def test_fixture_without_episode_id_does_not_leak_the_folder_name(self):
        import shutil as sh
        d = self.tmp / "D06_seed_918273"
        sh.copytree(Path(self.ep_dir) / "public", d)
        manifest = json.loads((d / "manifest.json").read_text("utf-8"))
        del manifest["episode_id"]
        (d / "manifest.json").write_text(json.dumps(manifest), "utf-8")
        obs, info = self.env.reset(0, {"mode": "closed", "episode_dir": str(d)})
        self.assertNotIn("918273", json.dumps([obs, info]))
        self.assertTrue(info["episode_id"].startswith("ep_"))

    def test_invalid_reset_config(self):
        for bad in ({"mode": "exam"}, "closed", [1]):
            with self.assertRaises(ValueError):
                self.env.reset(1, bad)


if __name__ == "__main__":
    unittest.main()
