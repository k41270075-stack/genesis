"""Public Python API.

    from vouchai import VouchAIEnv
    env = VouchAIEnv(mode="eval")           # zone B in a child process
    obs, info = env.reset(seed, config)
    obs, reward, terminated, truncated, info = env.step(action)
    results = env.finalize()
"""

from __future__ import annotations

from typing import Any

from .server.client import ProcessEnv
from .server.local import LocalEnv


def make(mode: str = "eval", isolation: str = "process", config: Any = None,
         time_limit_s: int | None = 60, log_dir: str | None = None) -> VouchAIEnv:
    return VouchAIEnv(mode=mode, isolation=isolation, config=config,
                      time_limit_s=time_limit_s, log_dir=log_dir)


class VouchAIEnv:
    """The environment object the jury imports. No constructor argument is required.

    isolation="process" (default) keeps the generator, the truth and the grader in a
    child process. isolation="inproc" is faster but allowed only in train mode.
    """

    def __init__(self, mode: str = "eval", isolation: str = "process", config: Any = None,
                 time_limit_s: int | None = 60, log_dir: str | None = None):
        if isolation == "process":
            self._impl: Any = ProcessEnv(mode=mode, time_limit_s=time_limit_s, log_dir=log_dir)
        elif isolation == "inproc":
            if mode != "train":
                raise ValueError("isolation='inproc' is allowed only in train mode")
            self._impl = LocalEnv(mode=mode, time_limit_s=time_limit_s)
        else:
            raise ValueError("isolation must be 'process' or 'inproc'")
        self.mode = mode
        self.isolation = isolation
        self.default_config = config

    def reset(self, seed: int | None = None, config: Any = None,
              options: dict | None = None) -> tuple[dict, dict]:
        return self._impl.reset(seed, config if config is not None else self.default_config,
                                options)

    def step(self, action: Any) -> tuple[dict, float, bool, bool, dict]:
        return self._impl.step(action)

    def finalize(self) -> dict[str, Any]:
        return self._impl.finalize()

    def describe(self) -> dict[str, Any]:
        return self._impl.describe()

    def close(self) -> None:
        self._impl.close()

    def __enter__(self) -> VouchAIEnv:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
