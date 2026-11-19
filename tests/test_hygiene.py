"""Static rules of the core (PLAN sections 2 and 10).

- banned modules and calls that break byte-level determinism;
- no float() anywhere in the core; true division of ints only where marked;
- import graph: env never imports grader; vouchai_verify never imports vouchai;
  the core never imports extras.
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "vouchai"
VERIFY = ROOT / "vouchai_verify"

BANNED_MODULES = {"random", "secrets", "uuid", "zoneinfo", "pickle", "shelve", "marshal"}
BANNED_CALLS = {"hash", "eval", "exec", "compile", "float", "__import__", "input"}
BANNED_ATTRS = {"now", "today", "utcnow", "getcontext", "setcontext", "localcontext",
                "utcfromtimestamp", "fromtimestamp", "localtime", "time_ns"}
# time.monotonic is allowed only for timeouts and report timing.
ALLOWED_TIME_ATTRS = {"monotonic"}
# Tooling modules that use "/" only to join pathlib paths; they never touch
# money, rates or generated data.
PATH_JOIN_FILES = {"vouchai/checks.py", "vouchai/cli.py"}


def python_files(folder: Path):
    return sorted(p for p in folder.rglob("*.py") if "__pycache__" not in p.parts)


def imported_modules(tree: ast.AST, package: str, path: Path):
    """Absolute names of imported modules (relative imports resolved)."""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    else:
        parts = parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = parts[: len(parts) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            yield mod
            for alias in node.names:
                yield f"{mod}.{alias.name}"


class HygieneTest(unittest.TestCase):
    def test_banned_modules_and_calls(self):
        problems = []
        for path in python_files(CORE) + python_files(VERIFY):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            lines = source.splitlines()
            rel = path.relative_to(ROOT)
            for mod in imported_modules(tree, "vouchai", path):
                if mod.split(".")[0] in BANNED_MODULES:
                    problems.append(f"{rel}: imports {mod}")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    if isinstance(fn, ast.Name) and fn.id in BANNED_CALLS:
                        problems.append(f"{rel}:{node.lineno}: calls {fn.id}()")
                    if isinstance(fn, ast.Attribute):
                        if fn.attr in BANNED_ATTRS:
                            problems.append(f"{rel}:{node.lineno}: calls .{fn.attr}()")
                        if fn.attr == "astimezone" and not node.args and not node.keywords:
                            problems.append(f"{rel}:{node.lineno}: astimezone() without tz")
                        if fn.attr == "strftime":
                            problems.append(f"{rel}:{node.lineno}: strftime is locale-dependent")
                        if (isinstance(fn.value, ast.Name) and fn.value.id == "time"
                                and fn.attr not in ALLOWED_TIME_ATTRS):
                            problems.append(f"{rel}:{node.lineno}: time.{fn.attr}()")
                if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                        and rel.as_posix() not in PATH_JOIN_FILES):
                    line = lines[node.lineno - 1]
                    if "float-ok" not in line and not _is_fraction_or_decimal_context(line):
                        problems.append(f"{rel}:{node.lineno}: '/' without float-ok marker")
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    problems.append(f"{rel}:{node.lineno}: float literal")
        self.assertEqual(problems, [])

    def test_import_graph(self):
        problems = []
        for path in python_files(CORE):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(ROOT).as_posix()
            mods = set(imported_modules(tree, "vouchai", path))
            if rel.startswith("vouchai/env/"):
                bad = {m for m in mods if m.startswith(("vouchai.grader", "vouchai.harness"))}
                problems += [f"{rel}: env imports {m}" for m in sorted(bad)]
            bad = {m for m in mods if m.split(".")[0] in ("extras", "vouchai_verify")}
            problems += [f"{rel}: core imports {m}" for m in sorted(bad)]
        for path in python_files(VERIFY):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            mods = set(imported_modules(tree, "vouchai_verify", path))
            bad = {m for m in mods if m.split(".")[0] == "vouchai"}
            problems += [f"{path.relative_to(ROOT).as_posix()}: verifier imports {m}"
                         for m in sorted(bad)]
        self.assertEqual(problems, [])

    def test_text_files_are_lf_utf8(self):
        problems = []
        for path in python_files(CORE) + python_files(VERIFY) + python_files(ROOT / "tests"):
            data = path.read_bytes()
            if b"\r\n" in data:
                problems.append(f"{path.relative_to(ROOT)}: CRLF")
            if data.startswith(b"\xef\xbb\xbf"):
                problems.append(f"{path.relative_to(ROOT)}: BOM")
        self.assertEqual(problems, [], "check .gitattributes / core.autocrlf")


def _is_fraction_or_decimal_context(line: str) -> bool:
    # Division of Fraction/Decimal objects is exact; such lines are marked by
    # the names involved. Everything else must carry "float-ok".
    return "Fraction" in line or "ctx." in line


if __name__ == "__main__":
    unittest.main()
