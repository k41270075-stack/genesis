"""Deterministic, tamper-evident page cursors.

cursor = base32("v1|<table>|<offset>|<episode tag>" + CRC32), no padding.

There is no secret: the same request yields the same cursor in any process,
which keeps trajectories replayable. The CRC and the episode tag turn a forged
cursor, a cursor of another table and a cursor of a previous episode into
INVALID_CURSOR instead of a silent wrong page.
"""

from __future__ import annotations

import base64
import re
import zlib

from .errors import ActionError

_VERSION = "v1"
_ALPHABET_RE = re.compile(r"^[A-Z2-7]{8,160}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")


def episode_tag(episode_id: str) -> str:
    """Short stable tag of an episode, embedded into its cursors."""
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("episode_id must be a non-empty string")
    return format(zlib.crc32(episode_id.encode("utf-8")), "08x")


def encode(table: str, offset: int, tag: str) -> str:
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative int")
    if not _TAG_RE.match(tag) or "|" in table:
        raise ValueError("invalid cursor parts")
    payload = f"{_VERSION}|{table}|{offset}|{tag}".encode("ascii")
    raw = payload + zlib.crc32(payload).to_bytes(4, "big")
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def decode(cursor: object, table: str, tag: str, row_count: int) -> int:
    """Return the offset encoded in a cursor or raise INVALID_CURSOR."""
    if not isinstance(cursor, str) or not _ALPHABET_RE.match(cursor):
        raise ActionError("INVALID_CURSOR")
    padded = cursor + "=" * (-len(cursor) % 8)
    try:
        raw = base64.b32decode(padded)
    except (ValueError, TypeError):
        raise ActionError("INVALID_CURSOR") from None
    if len(raw) < 5:
        raise ActionError("INVALID_CURSOR")
    payload, crc = raw[:-4], raw[-4:]
    if zlib.crc32(payload).to_bytes(4, "big") != crc:
        raise ActionError("INVALID_CURSOR")
    try:
        parts = payload.decode("ascii").split("|")
    except UnicodeDecodeError:
        raise ActionError("INVALID_CURSOR") from None
    if len(parts) != 4 or parts[0] != _VERSION or parts[1] != table or parts[3] != tag:
        raise ActionError("INVALID_CURSOR")
    text = parts[2]
    canonical = text.isascii() and text.isdigit() and len(text) <= 9
    if not canonical or (len(text) > 1 and text[0] == "0"):
        raise ActionError("INVALID_CURSOR")
    offset = int(text)
    if not 0 < offset < row_count:
        # Offset 0 is the first page (cursor null); a cursor at or past the end
        # is never issued (next_cursor is null on the last page).
        raise ActionError("INVALID_CURSOR")
    return offset
