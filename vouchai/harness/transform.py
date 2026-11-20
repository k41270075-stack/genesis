"""Harmless transformations of a saved episode (the jury's paired checks).

  T1 rename every ID consistently; --hostile swaps the visual formats between
     tables (rows look like invoices, invoices like rows...) and reverses order
  T2 shuffle the rows of every table
  T4 write timestamps in other offsets (the same instants)
  T5 shuffle JSON key order

The truth is rewritten with the same map and private/id_map.json records it.
Nothing about the books changes, so the oracle answer, the verifier report and
the reward of any content-based policy must stay the same.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..episode import load_episode
from ..render import fx_csv, json_bytes, jsonl, ledger_csv
from ..rng import Stream
from ..timeutil import format_ts, in_offset, parse_ts, utc_seconds

OFFSETS = (0, 330, -300, 540, -180)


def _new_ids(kind: str, keys: list[str], hostile: bool, stream: Stream) -> dict[str, str]:
    order = list(keys)
    if hostile:
        order.reverse()
        fmt = {"row": "INV-9{:05d}", "doc": "R{:09d}", "invoice": "PAY-1{:05d}",
               "payment": "CUS-{:06d}", "entity": "D{:09d}"}[kind]
    else:
        stream.shuffle(order)
        fmt = {"row": "row-{:06d}", "doc": "doc-{:06d}", "invoice": "inv-{:06d}",
               "payment": "pay-{:06d}", "entity": "ent-{:06d}"}[kind]
    return {old: fmt.format(n + 1) for n, old in enumerate(order)}


def _rekey(obj: dict, stream: Stream) -> dict:
    keys = list(obj)
    stream.shuffle(keys)
    return {k: obj[k] for k in keys}


def transform(src: str | Path, dst: str | Path, *, seed: int = 0, rename: bool = True,
              hostile: bool = False, shuffle: bool = True, reoffset: bool = True,
              rekey: bool = True) -> Path:
    src, dst = Path(src), Path(dst)
    ep = load_episode(src)
    clean = ep.clean_tables
    s = Stream.root(seed, "transform")
    t = ep.tables
    maps: dict[str, dict[str, str]] = {}
    if rename:
        maps["row"] = _new_ids("row", sorted({r["row_id"] for r in t["ledger"]}
                                             | {r["row_id"] for r in (clean or t)["ledger"]}),
                               hostile, s.child("rows"))
        maps["doc"] = _new_ids("doc", sorted([d["doc_id"] for d in t["invoices"] + t["payments"]]),
                               hostile, s.child("docs"))
        maps["invoice"] = _new_ids("invoice", sorted(d["invoice_id"] for d in t["invoices"]),
                                   hostile, s.child("inv"))
        maps["payment"] = _new_ids("payment", sorted(d["payment_id"] for d in t["payments"]),
                                   hostile, s.child("pay"))
        maps["entity"] = _new_ids("entity", sorted({d["entity_id"] for d in t["invoices"]}
                                                   | {r["entity_id"] for r in t["ledger"]
                                                      if r["entity_id"]}),
                                  hostile, s.child("ent"))
    flat: dict[str, str] = {}
    for m in maps.values():
        flat.update(m)

    def rid(value):
        return flat.get(value, value) if value is not None else None

    offsets = s.child("offsets")

    def ts(text: str) -> str:
        if not reoffset:
            return text
        return format_ts(in_offset(parse_ts(text), offsets.choice(OFFSETS)))

    def tables(src_tables: dict[str, list[dict]]) -> dict[str, list[dict]]:
        ledger = [{**r, "row_id": rid(r["row_id"]), "timestamp": ts(r["timestamp"]),
                   "entity_id": rid(r["entity_id"]), "invoice_id": rid(r["invoice_id"]),
                   "payment_id": rid(r["payment_id"])} for r in src_tables["ledger"]]
        # all rows of one entry keep one instant AND one written form
        by_instant: dict[int, str] = {}
        for r in ledger:
            key = utc_seconds(parse_ts(r["timestamp"]))
            r["timestamp"] = by_instant.setdefault(key, r["timestamp"])
        invoices = [{**d, "doc_id": rid(d["doc_id"]), "invoice_id": rid(d["invoice_id"]),
                     "entity_id": rid(d["entity_id"]), "issued_at": ts(d["issued_at"]),
                     "due_at": ts(d["due_at"]), "credit_for": rid(d.get("credit_for")),
                     "replaces_invoice_id": rid(d.get("replaces_invoice_id"))}
                    for d in src_tables["invoices"]]
        payments = [{**d, "doc_id": rid(d["doc_id"]), "payment_id": rid(d["payment_id"]),
                     "timestamp": ts(d["timestamp"]),
                     "invoice_refs": [rid(x) for x in d["invoice_refs"]] if d["invoice_refs"]
                     else None,
                     "allocations": [{**a, "invoice_id": rid(a["invoice_id"])}
                                     for a in d["allocations"]]}
                    for d in src_tables["payments"]]
        fx = [dict(r) for r in src_tables["fx"]]
        out = {"ledger": ledger, "invoices": invoices, "payments": payments, "fx": fx}
        if shuffle:
            for name, rows in out.items():
                s.child(f"shuffle.{name}").shuffle(rows)
        if rekey:
            out["invoices"] = [_rekey(d, s.child("rekey")) for d in out["invoices"]]
            out["payments"] = [_rekey(d, s.child("rekey")) for d in out["payments"]]
        return out

    new_tables = tables(t)
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "public").mkdir(parents=True)
    pub = dst / "public"
    (pub / "manifest.json").write_bytes(json_bytes(ep.manifest))
    (pub / "policy.json").write_bytes(json_bytes(ep.policy))
    _write_tables(pub, new_tables)

    priv = dst / "private"
    priv.mkdir()
    if clean is not None:
        (priv / "clean").mkdir()
        _write_tables(priv / "clean", tables(clean))
    issues = [_map_issue(issue, rid) for issue in ep.issues]
    (priv / "truth.json").write_bytes(json_bytes({"episode_id": ep.episode_id, "issues": issues}))
    (priv / "id_map.json").write_bytes(json_bytes({k: v for k, v in maps.items()}))
    return dst


def _write_tables(folder: Path, tables: dict[str, list[dict]]) -> None:
    (folder / "ledger.csv").write_bytes(ledger_csv(tables["ledger"]))
    (folder / "invoices.jsonl").write_bytes(jsonl(tables["invoices"]))
    (folder / "payments.jsonl").write_bytes(jsonl(tables["payments"]))
    (folder / "fx.csv").write_bytes(fx_csv(tables["fx"]))


def _map_issue(issue: dict[str, Any], rid) -> dict[str, Any]:
    out = dict(issue)
    out["affected_ids"] = [rid(x) for x in issue["affected_ids"]]
    out["carrier_row_ids"] = [rid(x) for x in issue["carrier_row_ids"]]
    out["evidence_slots"] = [sorted(rid(x) for x in slot) for slot in issue["evidence_slots"]]
    out["evidence_sets"] = [[rid(x) for x in st] for st in issue["evidence_sets"]]
    if "evidence_ids" in issue:
        out["evidence_ids"] = [rid(x) for x in issue["evidence_ids"]]
    out["absence_checks"] = [{k: (rid(v) if k in ("invoice_id", "payment_id") else v)
                              for k, v in c.items()} for c in issue["absence_checks"]]
    return out
