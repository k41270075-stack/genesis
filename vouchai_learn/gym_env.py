"""Gymnasium-style wrapper: VouchAI for RL libraries that expect gymnasium.Env.

    from vouchai_learn.gym_env import VouchAIGymEnv
    env = VouchAIGymEnv(config="jury_like")          # train mode, zone B in a child process
    obs, info = env.reset(seed=7)                     # obs: JSON text
    obs, reward, terminated, truncated, info = env.step('{"action": "list_records", ...}')

Observations and actions are JSON text (gymnasium.spaces.Text), the natural
format for language-model agents; dict actions are accepted as well. The
wrapper adds nothing to what the agent sees: it serialises the same envelope
the core returns. If gymnasium is installed the class is a real gymnasium.Env
(and is registered as "VouchAI-v0"); without it the class keeps the same
reset / step / close signatures, so the core stays dependency-free.
"""

from __future__ import annotations

import json
from typing import Any

from vouchai.api import VouchAIEnv

try:                                           # optional dependency
    import gymnasium
    from gymnasium import spaces
except ImportError:                            # pragma: no cover - depends on the machine
    gymnasium = None
    spaces = None

MAX_TEXT = 1 << 20
_Base: Any = gymnasium.Env if gymnasium is not None else object


def _text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class VouchAIGymEnv(_Base):
    metadata = {"render_modes": []}

    def __init__(self, config: Any = "jury_like", isolation: str = "process",
                 mode: str = "train"):
        self.env = VouchAIEnv(mode=mode, isolation=isolation, config=config)
        self.config = config
        if spaces is not None:
            self.observation_space = spaces.Text(max_length=MAX_TEXT)
            self.action_space = spaces.Text(max_length=MAX_TEXT)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if gymnasium is not None:
            super().reset(seed=seed)
        obs, info = self.env.reset(seed, self.config, options)
        return _text(obs), info

    def step(self, action: str | dict):
        if isinstance(action, str):
            try:
                action = json.loads(action)
            except json.JSONDecodeError:
                action = {"action": "<unparseable>"}   # the core answers with an error code
        obs, reward, terminated, truncated, info = self.env.step(action)
        return _text(obs), reward, terminated, truncated, info

    def finalize(self) -> dict[str, Any]:
        return self.env.finalize()

    def close(self) -> None:
        self.env.close()


if gymnasium is not None:                      # pragma: no cover - depends on the machine
    try:
        gymnasium.register(id="VouchAI-v0", entry_point=VouchAIGymEnv)
    except Exception:
        pass
