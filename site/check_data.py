"""Fail if site/data is stale: rebuild into a temporary folder and compare bytes.

    python site/check_data.py      # from the root of the repository; exit 0 = fresh
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SITE = Path(__file__).resolve().parent


# written by their own scripts (they run the real commands, minutes long):
# site/capture_terminal.py -> terminal.json, site/grade_presets.py -> grade_presets.json
RECORDED = {"terminal.json", "grade_presets.json"}


def main() -> int:
    current = SITE / "data"
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run([sys.executable, str(SITE / "build_data.py"), "--out", tmp],
                              stdout=subprocess.DEVNULL)
        if done.returncode != 0:
            print("check_data: build_data.py failed", file=sys.stderr)
            return 1
        fresh = {p.name: p.read_bytes() for p in Path(tmp).iterdir() if p.is_file()}
    have = {p.name: p.read_bytes() for p in current.iterdir() if p.is_file()} \
        if current.is_dir() else {}
    problems = []
    for name in sorted(set(fresh) | set(have)):
        if name not in have:
            problems.append(f"missing  site/data/{name}")
        elif name not in fresh:
            if name not in RECORDED:
                problems.append(f"extra    site/data/{name}")
        elif fresh[name] != have[name]:
            problems.append(f"stale    site/data/{name}")
    if problems:
        print("site/data is out of date; run: python site/build_data.py", file=sys.stderr)
        for line in problems:
            print("  " + line, file=sys.stderr)
        return 1
    print(f"site/data is fresh ({len(fresh)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
