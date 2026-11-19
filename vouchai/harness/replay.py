"""Replay recorded trajectories and compare every transition byte for byte."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..jsonsafe import dumps_canonical
from ..server.local import LocalEnv


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def replay(trajectories: list[dict[str, Any]], index: dict[str, dict[str, Any]]) -> list[str]:
    """Return mismatches (empty list = every step reproduced exactly)."""
    runs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in trajectories:
        runs[(row.get("policy", ""), row["episode_id"])].append(row)
    problems: list[str] = []
    for (policy, episode_id), rows in sorted(runs.items()):
        rows.sort(key=lambda r: r["step"])
        entry = index.get(episode_id)
        if entry is None:
            problems.append(f"{policy}/{episode_id}: not in the episode index")
            continue
        env = LocalEnv(mode="train", time_limit_s=None)
        obs, info = env.reset(entry["seed"], entry["config"])
        if info["episode_id"] != episode_id:
            problems.append(f"{policy}/{episode_id}: reset produced {info['episode_id']}")
            continue
        if dumps_canonical(obs) != dumps_canonical(rows[0]["observation"]):
            problems.append(f"{policy}/{episode_id}: first observation differs")
        for row in rows[1:]:
            got = env.step(row["action"])
            want = (row["observation"], row["reward"], row["terminated"], row["truncated"])
            if dumps_canonical(got[:4]) != dumps_canonical(list(want)):
                problems.append(f"{policy}/{episode_id}: step {row['step']} differs")
                break
    return problems
