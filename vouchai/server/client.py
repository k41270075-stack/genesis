"""Run zone B (environment + grader) in a child process and talk JSON lines.

The truth lives only in the child's memory; the caller's process holds
observations and nothing else.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..jsonsafe import MAX_INPUT_BYTES, dumps_canonical, too_deep

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


class EnvProtocolError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class ProcessEnv:
    def __init__(self, mode: str = "eval", time_limit_s: int | None = 60,
                 log_dir: str | None = None, popen_kwargs: dict | None = None):
        if mode not in ("eval", "train"):
            raise ValueError("mode must be 'eval' or 'train'")
        if time_limit_s is not None and (type(time_limit_s) is not int or time_limit_s <= 0):
            raise ValueError("time_limit_s must be a positive int or None")
        self.mode = mode
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PACKAGE_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONUTF8"] = "1"
        # stderr goes to a file: a full stderr pipe would deadlock the child. Without
        # a writable temp folder (read-only file system) the log is dropped instead.
        try:
            log_root = Path(log_dir) if log_dir else Path(tempfile.gettempdir())
            log_root.mkdir(parents=True, exist_ok=True)
            self._stderr = tempfile.NamedTemporaryFile(prefix="vouchai-zone-b-",
                                                       suffix=".log", dir=log_root,
                                                       delete=False)
        except OSError:
            self._stderr = None
        cmd = [sys.executable, "-m", "vouchai", "serve", "--mode", mode,
               "--time-limit", str(time_limit_s or 0)]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=self._stderr or subprocess.DEVNULL, env=env,
                                      cwd=str(PACKAGE_ROOT),
                                      **(popen_kwargs or {}))
        self.pid = self._proc.pid
        self._next_id = 0
        self.hello = self._call("hello")

    def _call(self, method: str, params: dict | None = None) -> Any:
        if getattr(self, "_proc", None) is None:
            raise EnvProtocolError("CLOSED", "the environment was closed")
        if self._proc.poll() is not None:
            raise EnvProtocolError("ZONE_B_EXITED")
        self._next_id += 1
        message = {"id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        try:
            self._proc.stdin.write(dumps_canonical(message).encode("ascii") + b"\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
        except (BrokenPipeError, OSError):
            raise EnvProtocolError("ZONE_B_EXITED") from None
        if not line:
            raise EnvProtocolError("ZONE_B_EXITED")
        try:
            response = json.loads(line)
        except ValueError:
            raise EnvProtocolError("BAD_RESPONSE") from None
        if "error" in response:
            error = response["error"]
            raise EnvProtocolError(error.get("code", "ERROR"), error.get("message", ""))
        return response["result"]

    def reset(self, seed: int | None = None, config: Any = None,
              options: dict | None = None) -> tuple[dict, dict]:
        if type(seed) is bool:
            raise ValueError("seed must be a non-negative int")
        if isinstance(options, dict) and options.get("episode_dir"):
            # zone B runs in another working directory: send an absolute path
            options = dict(options, episode_dir=str(Path(options["episode_dir"]).resolve()))
        try:
            result = self._call("reset", {"seed": seed, "config": config, "options": options})
        except EnvProtocolError as exc:
            if exc.code == "INVALID_RESET":
                raise ValueError(str(exc)) from None
            raise
        return result["observation"], result["info"]

    def step(self, action: Any) -> tuple[dict, float, bool, bool, dict]:
        if isinstance(action, (bytes, bytearray)):
            action = bytes(action).decode("utf-8", "replace")
        if isinstance(action, str):
            # the same 256 KB cap as zone B, checked here so the line always fits
            too_large = len(action) > MAX_INPUT_BYTES or \
                len(action.encode("utf-8", "surrogatepass")) > MAX_INPUT_BYTES
            params = {"action_json": "\x00too large" if too_large else action}
        else:
            try:
                if too_deep(action):
                    raise ValueError("too deep")
                text = dumps_canonical(action)
                if len(text) <= MAX_INPUT_BYTES:
                    params = {"action": action}
                elif isinstance(action, dict) and action.get("action") == "submit":
                    # an oversized submit is still a submit: invalid structure, -1
                    params = {"action": {"action": "submit", "findings": "too large"}}
                else:
                    params = {"action_json": "\x00too large"}
            except (TypeError, ValueError, RecursionError):
                if isinstance(action, dict) and action.get("action") == "submit":
                    params = {"action": {"action": "submit", "findings": "unserializable"}}
                else:
                    params = {"action_json": "\x00not serializable"}
        r = self._call("step", params)
        return r["observation"], r["reward"], r["terminated"], r["truncated"], r["info"]

    def finalize(self) -> dict[str, Any]:
        return self._call("finalize")

    def describe(self) -> dict[str, Any]:
        return self._call("describe")

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    self._call("close")
                except EnvProtocolError:
                    pass
                proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        finally:
            for stream in (proc.stdin, proc.stdout):
                try:
                    stream.close()
                except OSError:
                    pass
            self._proc = None
            if self._stderr is not None:
                self._stderr.close()
                # keep the zone B log only when it says something (a crash)
                try:
                    path = Path(self._stderr.name)
                    if path.stat().st_size == 0:
                        path.unlink()
                except OSError:
                    pass

    def __enter__(self) -> ProcessEnv:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
