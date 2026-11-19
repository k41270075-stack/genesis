"""python -m vouchai_verify EPISODE_DIR [--report] [--passport] [--json]"""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import report
from .core import load
from .passport import passport


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vouchai_verify",
                                     description="Independent verifier of VouchAI episodes.")
    parser.add_argument("--version", action="version", version=f"vouchai_verify {__version__}")
    parser.add_argument("episode_dir", nargs="+")
    parser.add_argument("--report", action="store_true", help="print the A/B/C report")
    parser.add_argument("--passport", action="store_true", help="write PASSPORT.md")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    all_ok = True
    for folder in args.episode_dir:
        episode = load(folder)
        result = report(episode)
        all_ok &= result["ok"]
        if args.passport:
            (Path(folder) / "PASSPORT.md").write_text(passport(episode, result), encoding="utf-8",
                                                      newline="\n")
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            marks = " ".join(f"{k}:{'ok' if result[k]['ok'] else 'FAIL'}" for k in "ABC")
            print(f"{result['episode_id']}  {marks}")
            if args.report or not result["ok"]:
                for k in "ABC":
                    for problem in result[k]["problems"]:
                        print(f"  {k}  {problem}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
