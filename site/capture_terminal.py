"""Record the real terminal output of the VouchAI commands for the site.

    python site/capture_terminal.py            # from the root of the repository

Every command below is run for real; each output line is stored with the
moment it appeared (milliseconds from the start). The site replays these
recordings in its terminal panes: nothing in them is typed by hand.
Output: site/data/terminal.json. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "terminal.json"
PY = "python"
MAX_LINES = 400


def tables_sha(folder: Path) -> str:
    h = hashlib.sha256()
    for name in ("ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv"):
        h.update((folder / "public" / name).read_bytes())
    return h.hexdigest()


def run(argv: list[str], shown: str, cwd: Path) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", NO_COLOR="1")
    start = time.perf_counter()
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines: list[list] = []
    lock = threading.Lock()

    def pump() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = raw.decode("utf-8", "replace").rstrip("\r\n")
            with lock:
                lines.append([round((time.perf_counter() - start) * 1000), text])

    t = threading.Thread(target=pump)
    t.start()
    code = proc.wait()
    t.join()
    total = round((time.perf_counter() - start) * 1000)
    if len(lines) > MAX_LINES:
        lines = lines[: MAX_LINES // 2] + [[lines[MAX_LINES // 2][0], f"… ({len(lines) - MAX_LINES} lines skipped) …"]] + lines[-MAX_LINES // 2:]
    print(f"  {shown}: exit {code}, {len(lines)} lines, {total} ms", file=sys.stderr)
    return {"command": shown, "exit": code, "ms": total, "lines": lines}


def main() -> int:
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    tmp = Path(tempfile.mkdtemp(prefix="vouchai_capture_"))
    try:
        ep = tmp / "ep"
        m = [PY, "-m", "vouchai"]
        plan: list[tuple[str, list[str], str]] = [
            ("check", [*m, "check"], "python -m vouchai check"),
            ("demo", [*m, "demo"], "python -m vouchai demo"),
            ("generate", [*m, "generate", "--seed", "28112026", "--config", "jury_like", "--out", str(ep)],
             "python -m vouchai generate --seed 28112026 --config jury_like --out ep"),
            ("verify", [PY, "-m", "vouchai_verify", "--report", str(ep)], "python -m vouchai_verify --report ep"),
            ("transform", [*m, "transform", str(ep), "--out", str(tmp / "ep_t"), "--seed", "7"],
             "python -m vouchai transform ep --out ep_t --seed 7"),
            ("selftest", [*m, "judge-selftest", "--quick", "--no-write"], "python -m vouchai judge-selftest --quick --no-write"),
            ("recipes", [*m, "judge-recipes", "--seeds", "0:2"], "python -m vouchai judge-recipes --seeds 0:2"),
            ("attack", [*m, "attack-search", "--seeds", "6000:6004"], "python -m vouchai attack-search --seeds 6000:6004"),
            ("baseline_auditor", [*m, "run", "--policy", "vouchai_verify.auditor:Auditor", "--config", "jury_like", "--seeds", "0:5"],
             "python -m vouchai run --policy vouchai_verify.auditor:Auditor --config jury_like --seeds 0:5"),
            ("baseline_flag_all", [*m, "run", "--policy", "flag_all", "--config", "jury_like", "--seeds", "0:5"],
             "python -m vouchai run --policy flag_all --config jury_like --seeds 0:5"),
            ("replay", [*m, "replay"], "python -m vouchai replay"),
            ("exhaustive", [PY, "-m", "unittest", "-v", "tests.test_matcher_exhaustive"],
             "python -m unittest -v tests.test_matcher_exhaustive"),
            ("spy", [PY, "-m", "unittest", "-v", "tests.test_attacks.SpyTest", "tests.test_harden"],
             "python -m unittest -v tests.test_attacks.SpyTest tests.test_harden"),
            ("score", [PY, "site/grade_presets.py"], "python site/grade_presets.py"),
            ("version", [*m, "version"], "python -m vouchai version"),
        ]
        needs_ep = {"generate", "verify", "transform"}
        report = ROOT / "reports" / "ATTACK_SEARCH.md"   # attack-search rewrites it; keep the full 40-seed report
        kept = report.read_bytes()
        rec: dict[str, dict] = {}
        for key, argv, shown in plan:
            if only is not None and key not in only and not (key == "generate" and only & needs_ep):
                continue
            rec[key] = run(argv, shown, ROOT)
            report.write_bytes(kept)
            if key == "generate":
                sha = tables_sha(ep)
                rec[key]["lines"].append([rec[key]["ms"], "$ sha256(ledger.csv + invoices.jsonl + payments.jsonl + fx.csv)"])
                rec[key]["lines"].append([rec[key]["ms"] + 40, sha])
                rec[key]["sha256"] = sha
        temp = tempfile.gettempdir()
        for r in rec.values():               # never publish the paths of this machine
            r["lines"] = [[ms, s.replace(str(tmp) + os.sep, "").replace(str(tmp), ".").replace(str(ROOT) + os.sep, "")
                           .replace(temp, "%TEMP%")] for ms, s in r["lines"]]
        if only is not None:
            old = json.loads(OUT.read_text(encoding="utf-8"))["runs"]
            old.update({k: v for k, v in rec.items() if k in only})
            rec = {k: old[k] for k, _, _ in plan if k in old}
        doc = {"recorded_on": f"{platform.system()} · Python {platform.python_version()}",
               "note": "real output of the commands, each line with the moment it appeared (ms)",
               "runs": rec}
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT)}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
