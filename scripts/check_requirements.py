#!/usr/bin/env python3
"""Validate the split between production and development requirements."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD_REQUIREMENTS = ROOT / "requirements.txt"
DEV_REQUIREMENTS = ROOT / "requirements-dev.txt"


def _load_requirement_lines(path: Path) -> list[str]:
    if not path.exists():
        _fail(f"{path.name} not found.")

    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _package_name(requirement_line: str) -> str:
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if separator in requirement_line:
            return requirement_line.split(separator, 1)[0].strip().lower()
    return requirement_line.strip().lower()


def check_split() -> None:
    prod_lines = _load_requirement_lines(PROD_REQUIREMENTS)
    dev_lines = _load_requirement_lines(DEV_REQUIREMENTS)

    if not dev_lines or dev_lines[0] != "-r requirements.txt":
        _fail("requirements-dev.txt must start with '-r requirements.txt'.")

    prod_packages = {
        _package_name(line) for line in prod_lines if not line.startswith("-")
    }
    dev_only_packages = {
        _package_name(line)
        for line in dev_lines[1:]
        if line and not line.startswith("-")
    }

    misplaced = sorted(prod_packages & dev_only_packages)
    if misplaced:
        _fail(
            "Development-only packages found in requirements.txt: "
            + ", ".join(misplaced)
            + ". Move them to requirements-dev.txt."
        )

    _ok("requirements split looks correct.")


def _ok(message: str) -> None:
    print(f"OK: {message}")


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    check_split()
