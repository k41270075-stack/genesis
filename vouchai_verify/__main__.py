import argparse
import sys

from . import __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vouchai_verify",
                                     description="Independent verifier of VouchAI episodes.")
    parser.add_argument("--version", action="version", version=f"vouchai_verify {__version__}")
    parser.add_argument("episode_dir", nargs="?")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--passport", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.episode_dir:
        parser.print_help()
        return 0
    print("vouchai_verify: episode checks are not implemented yet (phase 2).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
