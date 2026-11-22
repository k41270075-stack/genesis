"""Supervised fine-tuning data for LLM auditors: whole episodes as chat transcripts.

    python -m vouchai_learn.sft                    # sft/train.jsonl, sft/dev.jsonl, sft/README.md
    python -m vouchai_learn.sft --extra 200        # + 200 fresh jury_like episodes in train

One line = one episode in the common chat format:

    {"messages": [{"role": "system", ...},
                  {"role": "user", "content": <observation JSON>},
                  {"role": "assistant", "content": <action JSON>}, ...],
     "meta": {"episode_id", "split", "config", "return", "steps", "TP", "FP", "FN"}}

The demonstrations come from the scripted auditor acting through the ordinary
environment API in train mode: it sees only observations, so every transcript
is what an agent could have seen and done. Only verified demonstrations are
kept (return >= MIN_RETURN, no false positive). Splits follow the open
dataset (episodes/train, episodes/dev), so a model fine-tuned on train can be
evaluated on dev and on fresh seeds with `python -m vouchai run`.
The leak scanner runs over every line; generation is byte-identical.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vouchai.harness.dataset import SPLITS
from vouchai.harness.runner import make_policy, run
from vouchai.harness.scanner import scan_text
from vouchai.version import VERSIONS

ROOT = Path(__file__).resolve().parents[1]
MIN_RETURN = 0.9
EXTRA_CONFIG = "jury_like"
EXTRA_FIRST_SEED = 70_000           # disjoint from the open splits and the learner's seeds

SYSTEM = (
    "You are a financial auditor agent in the VouchAI environment. The books of a fictional "
    "company hide accounting errors of four types: duplicate_invoice, payment_allocation, "
    "fx_conversion, period_cutoff. Legitimate look-alikes (credit notes, partial payments, "
    "rates of the right day, local time zones) are not errors. Every user message is an "
    "observation in JSON. Reply with exactly one action in JSON, using the formats listed in "
    "the first observation (action_formats). Read the tables with list_records, check with "
    "get_record, get_document and calculator, then submit findings with evidence: every "
    "finding must cite the records that prove it. A finding without proof, an accusation of "
    "a look-alike and every step spent cost reward."
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def transcripts(schedule: list[tuple[int, Any]], split: str) -> tuple[list[dict], int]:
    """Run the auditor and turn every verified episode into one chat transcript."""
    result = run(make_policy("vouchai_verify.auditor:Auditor"), schedule, mode="train",
                 record=True, split=split)
    by_episode: dict[str, list[dict]] = {}
    for row in result["trajectories"]:
        by_episode.setdefault(row["episode_id"], []).append(row)
    out, dropped = [], 0
    for (_seed, config), episode in zip(schedule, result["episodes"]):
        rows = by_episode[episode["episode_id"]]
        if episode["return"] < MIN_RETURN or episode["FP"]:
            dropped += 1
            continue
        messages = [{"role": "system", "content": SYSTEM}]
        for row in rows:
            if row["action"] is not None:
                messages.append({"role": "assistant", "content": _dump(row["action"])})
            if not (row["terminated"] or row["truncated"]):
                messages.append({"role": "user", "content": _dump(row["observation"])})
        out.append({"messages": messages,
                    "meta": {"episode_id": episode["episode_id"], "split": split,
                             "config": config if isinstance(config, str) else "custom",
                             "return": episode["return"], "steps": episode["steps"],
                             "TP": episode["TP"], "FP": episode["FP"], "FN": episode["FN"]}})
    return out, dropped


def build(out_dir: Path, extra: int = 0) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"versions": VERSIONS, "min_return": MIN_RETURN, "splits": {}}
    for split, (preset, seeds) in SPLITS.items():
        schedule = [(s, preset) for s in seeds]
        if split == "train" and extra:
            schedule += [(s, EXTRA_CONFIG) for s in range(EXTRA_FIRST_SEED,
                                                           EXTRA_FIRST_SEED + extra)]
        rows, dropped = transcripts(schedule, split)
        lines = [_dump(r) for r in rows]
        leaks = [hit for line in lines for hit in scan_text(line)]
        if leaks:
            raise RuntimeError(f"hidden tokens in SFT data: {leaks[:5]}")
        (out_dir / f"{split}.jsonl").write_text("".join(line + "\n" for line in lines),
                                                encoding="utf-8", newline="\n")
        turns = sum(sum(m["role"] == "assistant" for m in r["messages"]) for r in rows)
        summary["splits"][split] = {"episodes": len(rows), "dropped": dropped,
                                    "assistant_turns": turns}
    (out_dir / "README.md").write_text(_readme(summary, extra), encoding="utf-8",
                                       newline="\n")
    return summary


def _readme(summary: dict[str, Any], extra: int) -> str:
    rows = [f"| `{split}.jsonl` | {s['episodes']} | {s['assistant_turns']} | {s['dropped']} |"
            for split, s in summary["splits"].items()]
    v = summary["versions"]
    return "\n".join([
        "# SFT data for LLM auditors",
        "",
        "Generated by `python -m vouchai_learn.sft"
        + (f" --extra {extra}" if extra else "") + f"` (env {v['env_version']}, generator "
        f"{v['generator_version']}, reward {v['reward_version']}). Byte-identical on rebuild.",
        "",
        "| file | episodes | assistant turns (actions) | dropped (return < "
        f"{summary['min_return']} or a false positive) |",
        "|---|---:|---:|---:|",
        *rows,
        "",
        "One line = one episode in the common chat format (`messages` with `system`, `user` = "
        "observation JSON, `assistant` = action JSON) plus `meta` (episode, return, TP/FP/FN).",
        "Demonstrations: the scripted auditor acting through the environment API in train mode,",
        "so it sees only observations; the leak scanner runs over every line.",
        "",
        "Suggested loop: fine-tune on `train.jsonl`, then measure the model as a policy on dev",
        "and on fresh seeds (`python -m vouchai run --policy pkg.module:Class --config jury_like`)",
        "and continue with RL on the environment reward (`reports/LEARNING.md` shows that the",
        "reward is a usable training signal). More data: `python -m vouchai_learn.sft --extra N`.",
        "",
    ])


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m vouchai_learn.sft")
    ap.add_argument("--out", default=str(ROOT / "sft"))
    ap.add_argument("--extra", type=int, default=0,
                    help=f"fresh {EXTRA_CONFIG} episodes added to train")
    args = ap.parse_args()
    summary = build(Path(args.out), args.extra)
    print(json.dumps(summary["splits"]))


if __name__ == "__main__":
    main()
