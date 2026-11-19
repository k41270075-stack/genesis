"""The five agent tools over the public tables of one episode.

The sandbox receives only public data (manifest, policy, tables). It never
sees the truth, the seed or the config, and it never imports the grader.
"""

from __future__ import annotations

import copy
from typing import Any

from . import calculator, cursor
from .errors import ActionError

PAGE_LIMIT = 50
TABLE_ALIASES = {
    "ledger": "ledger", "ledger.csv": "ledger",
    "invoices": "invoices", "invoices.jsonl": "invoices",
    "payments": "payments", "payments.jsonl": "payments",
    "fx": "fx", "fx.csv": "fx",
}
ID_FIELDS = {
    "ledger": ("row_id",),
    "invoices": ("doc_id", "invoice_id"),
    "payments": ("doc_id", "payment_id"),
    "fx": ("id",),
}
TOOLS = ("list_records", "get_record", "get_document", "calculator", "submit")

# One dictionary for every document; the choice depends on structural fields
# only, never on IDs or on whether the document is involved in an error.
INVOICE_NOTES = ("Thank you for your business.", "Payment terms as agreed.",
                 "Please quote the invoice number with your payment.",
                 "Services rendered as per contract.")
PAYMENT_NOTES = ("Payment received.", "Bank transfer.", "Remittance as per statement.",
                 "Incoming transfer.")


def _table(params: dict) -> str:
    name = params.get("table")
    if not isinstance(name, str):
        raise ActionError("INVALID_ARGUMENT")
    if name not in TABLE_ALIASES:
        raise ActionError("UNKNOWN_TABLE")
    return TABLE_ALIASES[name]


class ToolSandbox:
    def __init__(self, episode_id: str, manifest: dict, policy: dict,
                 tables: dict[str, list[dict[str, Any]]]):
        self.episode_id = episode_id
        self.manifest = manifest
        self.policy = policy
        self.tables = tables
        self.tag = cursor.episode_tag(episode_id)
        self.index: dict[str, dict[str, dict]] = {}
        for name, fields in ID_FIELDS.items():
            primary: dict[str, dict] = {}
            secondary: dict[str, list[dict]] = {}
            for row in tables[name]:
                primary.setdefault(row[fields[0]], row)
                for f in fields[1:]:
                    secondary.setdefault(row[f], []).append(row)
            for ident, rows in secondary.items():
                if ident not in primary and len(rows) == 1:
                    primary[ident] = rows[0]
            self.index[name] = primary
        # Documents: doc_id first; a business ID only if it is unambiguous.
        self.documents: dict[str, tuple[str, dict]] = {}
        business: dict[str, list[tuple[str, dict]]] = {}
        for kind, table, field in (("invoice", "invoices", "invoice_id"),
                                   ("payment", "payments", "payment_id")):
            for row in tables[table]:
                self.documents.setdefault(row["doc_id"], (kind, row))
                business.setdefault(row[field], []).append((kind, row))
        for ident, docs in business.items():
            if ident not in self.documents and len(docs) == 1:
                self.documents[ident] = docs[0]

    # ------------------------------------------------------------ tools

    def execute(self, action: dict) -> dict[str, Any]:
        name = action.get("action")
        if name == "list_records":
            return self.list_records(action)
        if name == "get_record":
            return self.get_record(action)
        if name == "get_document":
            return self.get_document(action)
        if name == "calculator":
            return {"value": calculator.evaluate(action.get("expression"))}
        raise ActionError("UNKNOWN_ACTION")

    def list_records(self, params: dict) -> dict[str, Any]:
        table = _table(params)
        limit = params.get("limit", PAGE_LIMIT)
        if limit is None:
            limit = PAGE_LIMIT
        if type(limit) is not int or not 1 <= limit <= PAGE_LIMIT:
            raise ActionError("LIMIT_OUT_OF_RANGE")
        rows = self.tables[table]
        token = params.get("cursor")
        offset = 0 if token is None else cursor.decode(token, table, self.tag, len(rows))
        page = rows[offset:offset + limit]
        nxt = offset + limit
        return {
            "table": table,
            "rows": copy.deepcopy(page),
            "next_cursor": cursor.encode(table, nxt, self.tag) if nxt < len(rows) else None,
        }

    def get_record(self, params: dict) -> dict[str, Any]:
        table = _table(params)
        ident = params.get("id")
        if not isinstance(ident, str):
            raise ActionError("INVALID_ARGUMENT")
        row = self.index[table].get(ident)
        if row is None:
            raise ActionError("UNKNOWN_ID")
        return {"table": table, "record": copy.deepcopy(row)}

    def get_document(self, params: dict) -> dict[str, Any]:
        ident = params.get("doc_id")
        if not isinstance(ident, str):
            raise ActionError("INVALID_ARGUMENT")
        found = self.documents.get(ident)
        if found is None:
            raise ActionError("UNKNOWN_ID")
        kind, row = found
        document = copy.deepcopy(row)
        document["document_type"] = kind
        document["notes"] = notes(kind, row)
        return {"document": document}


def notes(kind: str, row: dict) -> str:
    if kind == "invoice":
        n = row["total_minor"] + len(row["line_items"])
        return INVOICE_NOTES[n % len(INVOICE_NOTES)]
    return PAYMENT_NOTES[row["amount_minor"] % len(PAYMENT_NOTES)]
