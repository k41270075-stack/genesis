"""SFT transcripts are well-formed, executable, truth-free and reproducible."""

import json
import unittest
from pathlib import Path

from vouchai.harness.scanner import scan_text
from vouchai.server.local import LocalEnv
from vouchai_learn.sft import SYSTEM, transcripts

ROOT = Path(__file__).resolve().parents[1]


class SftTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.dropped = transcripts([(101, "dev"), (102, "dev")], "dev")

    def test_chat_format(self):
        self.assertEqual((len(self.rows), self.dropped), (2, 0))
        for row in self.rows:
            roles = [m["role"] for m in row["messages"]]
            self.assertEqual(roles[0], "system")
            self.assertEqual(row["messages"][0]["content"], SYSTEM)
            self.assertEqual(roles[1:], ["user", "assistant"] * ((len(roles) - 1) // 2))
            last = json.loads(row["messages"][-1]["content"])
            self.assertEqual(last["action"], "submit")
            self.assertGreaterEqual(row["meta"]["return"], 0.9)
            self.assertEqual(row["meta"]["FP"], 0)

    def test_replaying_the_assistant_turns_reproduces_the_episode(self):
        """Every observation in the transcript is what the environment returns."""
        for seed, row in zip((101, 102), self.rows):
            env = LocalEnv(mode="train", time_limit_s=None)
            obs, info = env.reset(seed, "dev")
            msgs = row["messages"]
            self.assertEqual(json.loads(msgs[1]["content"]), json.loads(json.dumps(obs)))
            reward = None
            for i in range(2, len(msgs), 2):
                obs, reward, terminated, truncated, _ = env.step(json.loads(msgs[i]["content"]))
                if i + 1 < len(msgs):
                    self.assertEqual(json.loads(msgs[i + 1]["content"]),
                                     json.loads(json.dumps(obs)))
                else:
                    self.assertTrue(terminated)
            self.assertEqual(reward, row["meta"]["return"])

    def test_no_hidden_tokens(self):
        for row in self.rows:
            self.assertEqual(scan_text(json.dumps(row, ensure_ascii=False)), [])

    def test_published_files_are_current(self):
        """sft/dev.jsonl in the repository is exactly what the generator writes today."""
        rows, _ = transcripts([(s, "dev") for s in range(101, 111)], "dev")
        published = (ROOT / "sft" / "dev.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line) for line in published], json.loads(json.dumps(rows)))


if __name__ == "__main__":
    unittest.main()
