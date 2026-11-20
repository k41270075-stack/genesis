"""Build the data of the site from the measured artifacts of the repository.

    python site/build_data.py            # from the root of the repository
    python site/build_data.py --out DIR  # write somewhere else (site/check_data.py)

Standard library only. Every number the site shows comes from here:

    reports/*.md, reports/*.json   tables of the reports, parsed as written
    docs/claims.json               claim -> tests -> command
    README.md                      slogan, the sealed prediction, uids of the zones
    episodes/dev/<DEMO_EPISODE>/   public tables + truth of one open dev episode
    trajectories.jsonl             what our scripted auditor submitted on it

Output: site/data/*.json (one file per source) and site/data/data.js, the same
objects wrapped for file:// (browsers refuse fetch() of local JSON). Nothing is
typed in by hand; a missing source becomes null and the site says so.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_EPISODE = "ep_IG7TOKQJH7G3UVKV"  # KZT, +05:00, all four types and the X1 scenario
TABLE_FILES = ("ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def warn(message: str) -> None:
    print(f"build_data: {message}", file=sys.stderr)


# ------------------------------------------------------------------ markdown


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    out, cur, i = [], "", 0
    while i < len(line):            # "\|" inside a cell is a literal bar
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur.strip())
    return out


def parse_markdown(text: str) -> dict:
    """Title, intro paragraphs and sections with their tables, values as written."""
    lines = text.splitlines()
    doc = {"title": None, "intro": [], "sections": []}
    section = {"heading": None, "level": 1, "text": [], "tables": []}
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            if level == 1 and doc["title"] is None:
                doc["title"] = m.group(2).strip()
            else:
                if section["heading"] is not None or section["text"] or section["tables"]:
                    doc["sections"].append(section)
                section = {"heading": m.group(2).strip(), "level": level, "text": [],
                           "tables": []}
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            headers = _cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            section["tables"].append({"headers": headers, "rows": rows})
            continue
        if line.strip():
            section["text"].append(line.strip())
        i += 1
    if section["heading"] is not None or section["text"] or section["tables"]:
        doc["sections"].append(section)
    # the first untitled section is the intro (What / Command / Versions lines)
    if doc["sections"] and doc["sections"][0]["heading"] is None:
        first = doc["sections"].pop(0)
        doc["intro"] = first["text"]
        if first["tables"]:
            doc["sections"].insert(0, {"heading": None, "level": 2, "text": [],
                                       "tables": first["tables"]})
    meta = {}
    for para in doc["intro"]:
        for key in ("What", "Command", "Versions"):
            if para.startswith(key + ":"):
                meta[key.lower()] = para[len(key) + 1:].strip()
    doc["meta"] = meta
    return doc


def build_reports() -> dict:
    out = {}
    for path in sorted((ROOT / "reports").glob("*")):
        if path.suffix == ".md":
            out[path.stem] = {"file": f"reports/{path.name}", "kind": "markdown",
                              **parse_markdown(read_text(path))}
        elif path.suffix == ".json":
            out[path.stem] = {"file": f"reports/{path.name}", "kind": "json",
                              "data": json.loads(read_text(path))}
    return out


# ------------------------------------------------------------------ README


def build_readme() -> dict:
    path = ROOT / "README.md"
    if not path.exists():
        warn("README.md not found")
        return {}
    text = read_text(path)
    out: dict = {"file": "README.md"}
    m = re.search(r"^\*\*(.+?)\*\*\s*$", text, re.M)
    out["slogan"] = m.group(1).strip() if m else None
    m = re.search(r"Лицензия\s*[—-]\s*([A-Za-z0-9.\-]+)", text)
    out["license"] = m.group(1).rstrip(".") if m else None
    uids = []
    for found in re.findall(r"uid\s+(\d{3,6})", text):
        if found not in uids:
            uids.append(found)
    out["uids"] = uids
    # the sealed prediction: the section whose heading names it
    pred = None
    m = re.search(r"^##+\s*(Предсказание|Prediction)[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if m:
        body = m.group(2)
        ep = re.search(r"\b(ep_[A-Z0-9]{8,})\b", body)
        sha = re.search(r"\b([0-9a-f]{64})\b", body)
        seed = re.search(r"seed\s*=\s*([0-9]+)", body)
        cfg = re.search(r"конфиг\s+`([^`]+)`", body) or re.search(r"config\s+`([^`]+)`", body)
        ver = re.search(r"версия\s+([0-9]+\.[0-9]+\.[0-9]+)", body) \
            or re.search(r"version\s+([0-9]+\.[0-9]+\.[0-9]+)", body)
        blocks = re.findall(r"```[a-z]*\n(.*?)```", body, re.S)
        rewards = []
        rm = re.search(r"награда:\s*(.+?)(?:\.\s*$|\n\n)", body, re.S | re.M)
        if rm:
            for part in re.split(r",\s*", " ".join(rm.group(1).split())):
                mm = re.match(r"(.+?)\s+(-?−?[0-9]+(?:\.[0-9]+)?)$", part.strip().rstrip("."))
                if mm:
                    rewards.append({"policy": mm.group(1).strip().strip("`"),
                                    "reward": mm.group(2).replace("−", "-")})
        hash_cmd = re.search(r"\(на любой ОС:\s*`(.+?)`\)", body, re.S)
        pred = {
            "episode_id": ep.group(1) if ep else None,
            "sha256": sha.group(1) if sha else None,
            "seed": seed.group(1) if seed else None,
            "config": cfg.group(1) if cfg else None,
            "version": ver.group(1) if ver else None,
            "rewards": rewards,
            "commands": [line for block in blocks for line in block.strip().splitlines()],
            "hash_command": hash_cmd.group(1) if hash_cmd else None,
        }
    else:
        warn("README.md has no prediction section")
    out["prediction"] = pred
    return out


# ------------------------------------------------------------------ episode


def _int_or_none(value: str):
    return int(value) if value.strip() != "" else None


def _str_or_none(value: str):
    return value if value != "" else None


def read_public(pub: Path) -> dict:
    def read_csv(name):
        return list(csv.DictReader(io.StringIO(read_text(pub / name), newline="")))

    def read_jsonl(name):
        return [json.loads(line) for line in read_text(pub / name).splitlines() if line.strip()]

    ledger = [{"row_id": r["row_id"], "timestamp": r["timestamp"], "account": r["account"],
               "debit_minor": _int_or_none(r["debit_minor"]),
               "credit_minor": _int_or_none(r["credit_minor"]), "currency": r["currency"],
               "entity_id": _str_or_none(r["entity_id"]),
               "invoice_id": _str_or_none(r["invoice_id"]),
               "payment_id": _str_or_none(r["payment_id"])} for r in read_csv("ledger.csv")]
    fx = [{"id": r.get("id") or f"{r['date']}:{r['source_currency']}:{r['target_currency']}",
           "date": r["date"], "source_currency": r["source_currency"],
           "target_currency": r["target_currency"], "rate": r["rate"]}
          for r in read_csv("fx.csv")]
    return {"ledger": ledger, "invoices": read_jsonl("invoices.jsonl"),
            "payments": read_jsonl("payments.jsonl"), "fx": fx}


def columnar(rows: list[dict]) -> dict:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return {"columns": columns, "rows": [[row.get(c) for c in columns] for row in rows]}


def auditor_run(episode_id: str) -> dict | None:
    path = ROOT / "trajectories.jsonl"
    if not path.exists():
        warn("trajectories.jsonl not found")
        return None
    steps = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if episode_id not in line[:120]:
                continue
            row = json.loads(line)
            if row.get("policy") == "vouchai_auditor" and row.get("episode_id") == episode_id:
                steps.append(row)
    if not steps:
        warn(f"no vouchai_auditor trajectory for {episode_id}")
        return None
    steps.sort(key=lambda r: r["step"])
    actions = [r["action"] for r in steps if r["action"] is not None]
    submit = next((a for a in actions if a.get("action") == "submit"), None)
    inspection = sum(1 for a in actions if a.get("action") != "submit")
    tools: dict[str, int] = {}
    for a in actions:
        tools[a.get("action")] = tools.get(a.get("action"), 0) + 1
    return {
        "policy": "vouchai_auditor",
        "split": steps[0].get("split"),
        "actions": len(actions),
        "inspection_steps": inspection,
        "tools": tools,
        "findings": (submit or {}).get("findings"),
        "reward": steps[-1].get("reward"),
        "terminated": steps[-1].get("terminated"),
        "source": "trajectories.jsonl",
    }


def hall_pair(tables: dict, issues: list[dict]) -> dict | None:
    """Two invoices of one customer, same amount and description, other service period."""
    flagged = {x for issue in issues for x in issue["affected_ids"]}
    inv = sorted(tables["invoices"], key=lambda r: r["invoice_id"])
    for a in inv:
        for b in inv:
            if not a["invoice_id"] < b["invoice_id"]:
                continue
            if a["entity_id"] != b["entity_id"] or a["total_minor"] != b["total_minor"]:
                continue
            if a["currency"] != b["currency"] or a.get("credit_for") or b.get("credit_for"):
                continue
            la, lb = a["line_items"][0], b["line_items"][0]
            if la["description"] != lb["description"]:
                continue
            if la.get("service_period_start") == lb.get("service_period_start"):
                continue
            if a["invoice_id"] in flagged or b["invoice_id"] in flagged:
                continue
            rows = [r for r in tables["ledger"]
                    if r["invoice_id"] in (a["invoice_id"], b["invoice_id"])
                    and r["account"] == "1200" and r["debit_minor"]]
            return {"invoices": [a, b], "ledger_rows": rows}
    return None


def life_of_error(tables: dict, issues: list[dict], manifest: dict, policy: dict) -> dict | None:
    """The X1 story: one bank instant, two calendars, one rate rule."""
    pick = next((i for i in issues if i["type"] == "fx_conversion"
                 and i.get("interaction_group") == "X1"), None) \
        or next((i for i in issues if i["type"] == "fx_conversion"
                 and i.get("variant") == "wrong_date"), None)
    if pick is None:
        return None
    target = pick["affected_ids"][0]
    pay = next((p for p in tables["payments"] if p["payment_id"] == target), None)
    if pay is None:
        return None
    mut = pick.get("mutation") or {}
    base = manifest["base_currency"]
    used, correct = None, None
    if mut.get("decision") == "rate_used" and mut.get("before") and mut.get("after"):
        correct = f"{mut['before'][0]}:{mut['before'][1]}:{base}"
        used = f"{mut['after'][0]}:{mut['after'][1]}:{base}"
    fx = {r["id"]: r for r in tables["fx"]}
    carrier = [r for r in tables["ledger"] if r["row_id"] in pick.get("carrier_row_ids", [])]
    partner = [i for i in issues if i is not pick and i.get("interaction_group")
               and i.get("interaction_group") == pick.get("interaction_group")]
    return {
        "issue_id": pick["issue_id"], "interaction_group": pick.get("interaction_group"),
        "payment": pay, "carrier_rows": carrier,
        "rate_used": fx.get(used), "rate_correct": fx.get(correct),
        "expected_amount_minor": pick["expected_amount_minor"],
        "tolerance_minor": pick.get("tolerance_minor", 0),
        "partner_issues": [{"issue_id": i["issue_id"], "type": i["type"],
                            "affected_ids": i["affected_ids"],
                            "expected_amount_minor": i["expected_amount_minor"]}
                           for i in partner],
        "rule": policy.get("fx", {}),
        "period": {"start": manifest["period_start"], "end": manifest["period_end"],
                   "timezone": manifest["timezone"],
                   "bank_timezone": manifest["time_conventions"]["bank_timezone"]},
    }


def build_episode() -> dict:
    root = ROOT / "episodes" / "dev" / DEMO_EPISODE
    pub = root / "public"
    manifest = json.loads(read_text(pub / "manifest.json"))
    policy = json.loads(read_text(pub / "policy.json"))
    truth = json.loads(read_text(root / "private" / "truth.json"))
    tables = read_public(pub)
    digest = hashlib.sha256(b"".join((pub / f).read_bytes() for f in TABLE_FILES)).hexdigest()
    keep = ("issue_id", "type", "variant", "interaction_group", "affected_ids",
            "expected_amount_minor", "currency", "tolerance_minor", "evidence_ids",
            "evidence_slots", "evidence_sets", "carrier_row_ids", "derivation", "mutation")
    issues = [{k: issue[k] for k in keep if k in issue} for issue in truth["issues"]]
    return {
        "episode_id": manifest["episode_id"],
        "folder": f"episodes/dev/{DEMO_EPISODE}",
        "tables_sha256": digest,
        "sha256_recipe": "sha256(ledger.csv + invoices.jsonl + payments.jsonl + fx.csv) of public/",
        "manifest": manifest,
        "policy": policy,
        "tables": {name: columnar(rows) for name, rows in tables.items()},
        "truth": {"episode_id": truth["episode_id"], "issues": issues},
        "auditor": auditor_run(manifest["episode_id"]),
        "hall": hall_pair(tables, truth["issues"]),
        "life": life_of_error(tables, truth["issues"], manifest, policy),
    }


# ------------------------------------------------------------------ main


def build() -> dict[str, object]:
    claims_path = ROOT / "docs" / "claims.json"
    claims = json.loads(read_text(claims_path)) if claims_path.exists() else None
    sources = ["README.md", "docs/claims.json", "trajectories.jsonl"]
    sources += [f"reports/{p.name}" for p in sorted((ROOT / "reports").glob("*"))
                if p.suffix in (".md", ".json")]
    ep_root = f"episodes/dev/{DEMO_EPISODE}"
    sources += [f"{ep_root}/public/{n}" for n in ("manifest.json", "policy.json") + TABLE_FILES]
    sources += [f"{ep_root}/private/truth.json"]
    meta = {
        "generator": "site/build_data.py",
        "command": "python site/build_data.py",
        "check": "python site/check_data.py",
        "sources": [{"file": s, "sha256": hashlib.sha256((ROOT / s).read_bytes()).hexdigest()}
                    for s in sources if (ROOT / s).exists()],
    }
    return {
        "meta": meta,
        "readme": build_readme(),
        "claims": claims,
        "reports": build_reports(),
        "episode": build_episode(),
    }


def dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def write(out: Path, data: dict[str, object]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, obj in data.items():
        path = out / f"{name}.json"
        path.write_text(dumps(obj) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    js = ["// generated by site/build_data.py from the repository; do not edit",
          "window.VOUCHAI_DATA = {"]
    js += [f"{json.dumps(name)}: {dumps(obj)}," for name, obj in data.items()]
    js += ["};", ""]
    path = out / "data.js"
    path.write_text("\n".join(js), encoding="utf-8", newline="\n")
    written.append(path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "site" / "data"))
    args = parser.parse_args(argv)
    for path in write(Path(args.out), build()):
        print(f"{path.stat().st_size:>8}  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
