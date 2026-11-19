"""`python -m vouchai check`: the single official check command.

Standard library only (unittest). Runs every test module as a section, prints
time per section and writes a machine-readable summary to the output folder.
"""

from __future__ import annotations

import io
import json
import os
import platform
import sys
import tempfile
import time
import unittest
from pathlib import Path

from .version import VERSIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"


def default_out_dir() -> Path:
    return Path(tempfile.gettempdir()) / "vouchai"


def _iter_modules(suite: unittest.TestSuite):
    """discover() returns one sub-suite per test module."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests = list(_flatten(item))
            if tests:
                yield _module_name(tests[0]), unittest.TestSuite(tests)


def _flatten(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _module_name(test: unittest.TestCase) -> str:
    name = type(test).__module__
    if name == "unittest.loader":  # import failure placeholder (_FailedTest)
        return test.id().split(".")[-1]
    return name.rsplit(".", 1)[-1]


def run_check(out_dir: Path | None = None, full: bool = False, pattern: str = "test_*.py") -> int:
    out_dir = Path(out_dir) if out_dir else default_out_dir()
    if full:
        os.environ["VOUCHAI_CHECK_FULL"] = "1"
    started = time.monotonic()  # timing only, never written into observations
    print(f"VouchAI check  env {VERSIONS['env_version']}  schema {VERSIONS['schema_version']}  "
          f"reward {VERSIONS['reward_version']}")
    print(f"python {platform.python_version()} on {platform.system()} {platform.machine()}")

    if not TESTS_DIR.is_dir():
        print("FAIL  tests/ folder not found next to the package")
        return 1

    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR), pattern=pattern, top_level_dir=str(REPO_ROOT))

    sections = []
    all_ok = True
    for name, module_suite in _iter_modules(suite):
        stream = io.StringIO()
        t0 = time.monotonic()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(module_suite)
        elapsed = time.monotonic() - t0
        ok = result.wasSuccessful()
        all_ok &= ok
        sections.append({
            "section": name,
            "tests": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "ok": ok,
            "seconds": round(elapsed, 3),  # float-ok: report timing only
        })
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<28} {result.testsRun:>4} tests  {elapsed:7.2f}s")
        if not ok:
            for _test, trace in result.failures + result.errors:
                print(trace.rstrip())

    total = time.monotonic() - started
    summary = {
        "ok": all_ok,
        "versions": VERSIONS,
        "python": sys.version,
        "platform": platform.platform(),
        "full": full,
        "sections": sections,
        "seconds": round(total, 3),  # float-ok: report timing only
    }
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "check.json").write_text(json.dumps(summary, indent=2) + "\n",
                                            encoding="utf-8", newline="\n")
        where = str(out_dir / "check.json")
    except OSError:
        where = "(not written: output folder is read-only)"
    count = sum(s["tests"] for s in sections)
    print(f"{'OK' if all_ok else 'FAILED'}  {count} tests in {total:.1f}s  summary: {where}")
    return 0 if all_ok else 1
