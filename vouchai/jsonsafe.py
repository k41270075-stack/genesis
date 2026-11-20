"""Hardened JSON input and canonical JSON output.

Input from an agent is untrusted: size is capped before parsing, NaN and
Infinity are rejected, duplicate keys are rejected (otherwise
{"action":"submit","action":"get_record"} silently becomes get_record), deep
nesting and huge integers are turned into a bounded error instead of a crash.
"""

from __future__ import annotations

import json
from typing import Any

MAX_INPUT_BYTES = 1024 * 1024


class JsonInputError(ValueError):
    """Untrusted JSON was rejected. `reason` is a fixed, input-free code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _reject_constant(_name: str) -> Any:
    raise JsonInputError("non_finite_number")


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise JsonInputError("duplicate_key")
        out[key] = value
    return out


def loads_untrusted(data: str | bytes, max_bytes: int = MAX_INPUT_BYTES) -> Any:
    """Parse untrusted JSON or raise JsonInputError with a fixed reason code."""
    if isinstance(data, (bytes, bytearray)):
        if len(data) > max_bytes:
            raise JsonInputError("too_large")
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            raise JsonInputError("not_utf8") from None
    elif isinstance(data, str):
        # Cheap upper bound first, exact byte length only when it matters.
        if len(data) > max_bytes or len(data.encode("utf-8", "surrogatepass")) > max_bytes:
            raise JsonInputError("too_large")
        text = data
    else:
        raise JsonInputError("not_text")
    try:
        return json.loads(text, parse_constant=_reject_constant,
                          object_pairs_hook=_pairs_no_duplicates)
    except JsonInputError:
        raise
    except RecursionError:
        raise JsonInputError("too_deep") from None
    except ValueError:  # JSONDecodeError and int-length limit
        raise JsonInputError("malformed") from None


def dumps_canonical(obj: Any) -> str:
    """One line, ASCII only, fixed separators, key order as given, no NaN."""
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def roundtrips(obj: Any) -> bool:
    """True if obj survives json.dumps -> json.loads unchanged (observation contract)."""
    try:
        return json.loads(dumps_canonical(obj)) == obj
    except (TypeError, ValueError):
        return False
