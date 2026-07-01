#!/usr/bin/env python3
"""Evaluate the VLIW kernel with the official frozen harness.

The wrapper is intentionally thin: it does not replace the official tests, it
only runs them, parses cycle evidence, checks for forbidden local edits, and
records a JSONL trail for Humanize/Codex review.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLED_PYTHON = Path(
    "/Users/rayw/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)
FORBIDDEN_EXACT = {"problem.py", "tests/frozen_problem.py"}
FORBIDDEN_PREFIXES = ("tests/",)
MILESTONES = (1450, 1300, 1000)


def choose_python(cli_python: Optional[str]) -> str:
    if cli_python:
        return cli_python
    if os.environ.get("VLIW_PYTHON"):
        return os.environ["VLIW_PYTHON"]
    if DEFAULT_BUNDLED_PYTHON.exists():
        return str(DEFAULT_BUNDLED_PYTHON)
    return sys.executable


def run_cmd(cmd: list[str], timeout: int) -> tuple[int, str, float]:
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, time.monotonic() - start


def git_paths(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode not in (0, 1):
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def status_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return []
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def forbidden_changes() -> list[str]:
    candidates = set(status_paths())
    candidates.update(git_paths(["diff", "--name-only"]))
    candidates.update(git_paths(["diff", "--cached", "--name-only"]))
    changed = []
    for path in sorted(candidates):
        normalized = path.replace("\\", "/")
        if normalized in FORBIDDEN_EXACT or normalized.startswith(FORBIDDEN_PREFIXES):
            changed.append(normalized)
    return changed


def parse_cycles(output: str) -> list[int]:
    return [int(match.group(1)) for match in re.finditer(r"CYCLES:\s+(\d+)", output)]


def parse_unittest_summary(output: str) -> dict[str, Any]:
    failed = bool(re.search(r"\bFAILED\b", output))
    ok = bool(re.search(r"\bOK\b", output))
    incorrect = "Incorrect output values" in output or "Incorrect result" in output
    errors = len(re.findall(r"\bERROR:", output))
    failures = len(re.findall(r"\bFAIL:", output))
    return {
        "ok_token": ok,
        "failed_token": failed,
        "incorrect_output": incorrect,
        "errors": errors,
        "failures": failures,
    }


def load_previous_best(log_path: Path) -> Optional[int]:
    if not log_path.exists():
        return None
    best: Optional[int] = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        cycles = row.get("cycles")
        if isinstance(cycles, int) and row.get("correctness_passed") and not row.get("forbidden_changed"):
            best = cycles if best is None else min(best, cycles)
    return best


def append_log(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", dest="python_bin", help="Python executable for official harness")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument("--no-log", action="store_true", help="Do not append .humanize eval log")
    parser.add_argument(
        "--require-milestone",
        type=int,
        choices=MILESTONES,
        help="Exit nonzero unless cycles are below this milestone",
    )
    args = parser.parse_args()

    python_bin = choose_python(args.python_bin)
    forbidden = forbidden_changes()

    cmd = [python_bin, "tests/submission_tests.py"]
    try:
        returncode, output, duration = run_cmd(cmd, args.timeout)
    except subprocess.TimeoutExpired as exc:
        row = {
            "ok": False,
            "reason": "timeout",
            "command": cmd,
            "timeout_sec": args.timeout,
            "duration_sec": args.timeout,
            "forbidden_changed": forbidden,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
        }
        if not args.json:
            print(json.dumps(row, indent=2, sort_keys=True))
        else:
            print(json.dumps(row, sort_keys=True))
        return 2

    cycles_list = parse_cycles(output)
    cycles = min(cycles_list) if cycles_list else None
    summary = parse_unittest_summary(output)
    correctness_passed = bool(cycles_list) and not summary["incorrect_output"] and summary["errors"] == 0
    thresholds = {f"lt_{milestone}": bool(cycles is not None and cycles < milestone) for milestone in MILESTONES}
    log_path = ROOT / ".humanize" / "evals" / "results.jsonl"
    previous_best = None if args.no_log else load_previous_best(log_path)

    row: dict[str, Any] = {
        "ok": correctness_passed and not forbidden,
        "correctness_passed": correctness_passed,
        "official_returncode": returncode,
        "cycles": cycles,
        "cycles_observed": cycles_list,
        "thresholds": thresholds,
        "forbidden_changed": forbidden,
        "previous_best": previous_best,
        "improved_best": bool(
            cycles is not None
            and correctness_passed
            and not forbidden
            and (previous_best is None or cycles < previous_best)
        ),
        "duration_sec": round(duration, 3),
        "command": cmd,
        "unittest_summary": summary,
    }

    if args.require_milestone is not None:
        row["required_milestone"] = args.require_milestone
        row["milestone_passed"] = bool(cycles is not None and cycles < args.require_milestone)
        row["ok"] = bool(row["ok"] and row["milestone_passed"])

    if not args.no_log:
        append_log(log_path, row)

    if args.json:
        print(json.dumps(row, sort_keys=True))
    else:
        print(json.dumps(row, indent=2, sort_keys=True))
        print("\n--- official harness output tail ---")
        print(output[-4000:].rstrip())

    return 0 if row["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
