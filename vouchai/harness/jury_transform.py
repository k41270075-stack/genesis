"""An independent implementation of the jury's paired-check transformation.

Written from the text of the check definitions (20.11.2026, block 4), not from
our own `transform`: copy the episode folder, permute the records of the tables
and the document streams (never the order inside a document), and rename IDs
one-to-one in every file, public and closed. The original is never touched.

Three renaming modes, because we do not know how the jury implements it:

  listed  every ID field of schemas/id_fields.json (our documented list)
  blind   any string value equal to a known ID, wherever it is
  lazy    only the field names of the jury's text: row_id, doc_id, invoice_id,
          payment_id, entity_id, affected_ids, evidence_ids

The fx key date:source:target is not a surrogate ID and is never renamed.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path
from typing import Any

from ..rng import Stream

MODES = ("listed", "blind", "lazy")
LAZY_KEYS = frozenset({"row_id", "doc_id", "invoice_id", "payment_id", "entity_id",
                       "affected_ids", "evidence_ids"})
LISTED_KEYS = LAZY_KEYS | {"credit_for", "replaces_invoice_id", "invoice_refs", "evidence_sets",
                           "evidence_slots", "carrier_row_ids"}
TABLE_FILES = ("ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv")
PREFIX = {"row": "JR", "doc": "JD", "invoice": "JI", "payment": "JP", "entity": "JE"}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8", newline="")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8", newline="")


def collect_ids(public: Path) -> dict[str, list[str]]:
    """The ID spaces of the public tables (sorted, unique)."""
    spaces: dict[str, set[str]] = {k: set() for k in PREFIX}
    _, ledger = _read_csv(public / "ledger.csv")
    for r in ledger:
        spaces["row"].add(r["row_id"])
        for f, ns in (("entity_id", "entity"), ("invoice_id", "invoice"),
                      ("payment_id", "payment")):
            if r.get(f):
                spaces[ns].add(r[f])
    for d in _read_jsonl(public / "invoices.jsonl"):
        spaces["doc"].add(d["doc_id"])
        spaces["invoice"].add(d["invoice_id"])
        if d.get("entity_id"):
            spaces["entity"].add(d["entity_id"])
    for d in _read_jsonl(public / "payments.jsonl"):
        spaces["doc"].add(d["doc_id"])
        spaces["payment"].add(d["payment_id"])
    return {k: sorted(v) for k, v in spaces.items()}


def make_mapping(public: Path, seed: int, plain: bool = False) -> dict[str, str]:
    """One-to-one map old -> new within every ID space; new IDs never reuse an old string.

    plain=True numbers every space from 1 without a prefix, so the same string
    appears in several spaces (payment "19" and invoice "19"): legal for the jury,
    because spaces are separate."""
    mapping: dict[str, str] = {}
    stream = Stream.root(seed, "jury-transform")
    for ns, ids in collect_ids(public).items():
        order = list(ids)
        stream.child(ns).shuffle(order)
        for n, old in enumerate(order):
            if old in mapping:
                raise ValueError(f"ID {old!r} is in two namespaces")
            mapping[old] = str(n + 1) if plain else f"{PREFIX[ns]}{n + 1:06d}"
    if set(mapping.values()) & set(mapping):
        raise ValueError("new IDs collide with old ones")
    return mapping


def _rename(node: Any, mapping: dict[str, str], mode: str, key: str | None = None,
            inside: bool = False) -> Any:
    """Rename IDs inside one JSON value. `inside`: an ancestor key is an ID field."""
    if isinstance(node, dict):
        return {k: _rename(v, mapping, mode, k, inside) for k, v in node.items()}
    if isinstance(node, list):
        return [_rename(v, mapping, mode, key, inside) for v in node]
    if isinstance(node, str):
        if mode == "blind":
            return mapping.get(node, node)
        keys = LAZY_KEYS if mode == "lazy" else LISTED_KEYS
        if key in keys or inside:
            return mapping.get(node, node)
    return node


def _rename_json(obj: Any, mapping: dict[str, str], mode: str) -> Any:
    if mode != "listed" or not isinstance(obj, dict):
        return _rename(obj, mapping, mode)
    out = _rename(obj, mapping, mode)
    if isinstance(out.get("id_map"), dict):          # provenance: values are public IDs
        out["id_map"] = {space: {k: mapping.get(v, v) for k, v in values.items()}
                         if isinstance(values, dict) else values
                         for space, values in out["id_map"].items()}
    return out


def jury_transform(src: str | Path, dst: str | Path, *, seed: int, permute: bool,
                   rename: bool, mode: str = "listed", plain: bool = False) -> dict[str, str]:
    """Write the transformed copy and return the old -> new ID map ({} without renaming)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    mapping = make_mapping(src / "public", seed, plain) if rename else {}
    stream = Stream.root(seed, "jury-permute")
    folders = [dst / "public", dst / "private" / "clean"]
    for folder in folders:
        if not folder.is_dir():
            continue
        for name in TABLE_FILES:
            path = folder / name
            if not path.is_file():
                continue
            if name.endswith(".csv"):
                header, rows = _read_csv(path)
                if mapping and name != "fx.csv":
                    rows = [_rename(r, mapping, mode) for r in rows]
                if permute and folder.name == "public":
                    stream.child(name).shuffle(rows)
                _write_csv(path, header, rows)
            else:
                rows = _read_jsonl(path)
                if mapping:
                    rows = [_rename(r, mapping, mode) for r in rows]
                if permute and folder.name == "public":
                    stream.child(name).shuffle(rows)
                _write_jsonl(path, rows)
    if mapping:
        for name in ("truth.json", "provenance.json"):
            path = dst / "private" / name
            if path.is_file():
                obj = json.loads(path.read_text(encoding="utf-8"))
                path.write_text(json.dumps(_rename_json(obj, mapping, mode), ensure_ascii=False),
                                encoding="utf-8", newline="")
    for stale in ("PASSPORT.md",):
        if (dst / stale).exists():
            (dst / stale).unlink()
    return mapping
