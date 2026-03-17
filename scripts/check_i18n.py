#!/usr/bin/env python3
"""
CI i18n consistency checker.

Commands:
  pot        Fail if translations/messages.pot is out of date.
             Run before pushing if you edit Python/Jinja strings.

  frontend   Fail if any frontend JSON translation file is inconsistent
             with the source (translations/frontend/es.json).
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VOLATILE_HEADERS_RE = re.compile(
    r'^"(POT-Creation-Date|PO-Revision-Date|Last-Translator|X-Generator):[^"]*"$',
    flags=re.MULTILINE,
)


def _normalize_pot(text: str) -> str:
    """Strip volatile header lines so timestamps don't cause false diffs."""
    return _VOLATILE_HEADERS_RE.sub("", text).strip()


def _python_with_babel() -> str:
    """Return a Python executable that can import Babel.

    Prefer the current interpreter. If it lacks Babel, fall back to the repo
    virtualenv when present.
    """
    try:
        if importlib.util.find_spec("babel.messages.frontend") is not None:
            return sys.executable
    except ModuleNotFoundError:
        pass

    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return sys.executable


# ---------------------------------------------------------------------------
# Check: backend messages.pot
# ---------------------------------------------------------------------------


def check_pot() -> None:
    pot_committed = ROOT / "translations" / "messages.pot"
    if not pot_committed.exists():
        _fail(
            "translations/messages.pot not found.\n"
            "Fix: pybabel extract -F babel.cfg -o translations/messages.pot ."
        )

    with tempfile.NamedTemporaryFile(suffix=".pot", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                _python_with_babel(),
                "-m",
                "babel.messages.frontend",
                "extract",
                "-F",
                "babel.cfg",
                "-o",
                str(tmp_path),
                ".",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode != 0:
            _fail(f"pybabel extract failed:\n{result.stderr}")

        generated = _normalize_pot(tmp_path.read_text(encoding="utf-8"))
        committed = _normalize_pot(pot_committed.read_text(encoding="utf-8"))

        if generated != committed:
            _fail(
                "translations/messages.pot is out of date.\n"
                "Fix: pybabel extract -F babel.cfg -o translations/messages.pot ."
            )
    finally:
        tmp_path.unlink(missing_ok=True)

    _ok("messages.pot is up to date.")


# ---------------------------------------------------------------------------
# Check: frontend translation JSON files
# ---------------------------------------------------------------------------


def check_frontend() -> None:
    frontend_dir = ROOT / "translations" / "frontend"
    source_path = frontend_dir / "es.json"

    if not source_path.exists():
        _fail("translations/frontend/es.json not found.")

    source: dict[str, str] = json.loads(source_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    # Source must not have empty values
    empty_keys = [k for k, v in source.items() if not str(v).strip()]
    if empty_keys:
        errors.append(f"es.json has empty source values: {empty_keys}")

    # Target locale files must not have keys absent from the source (es.json).
    # Missing keys in targets are only warnings: Crowdin fills them via sync.
    for locale_path in sorted(frontend_dir.glob("*.json")):
        if locale_path.name == "es.json":
            continue
        locale_data: dict = json.loads(locale_path.read_text(encoding="utf-8"))
        missing = sorted(set(source) - set(locale_data))
        extra = sorted(set(locale_data) - set(source))
        if missing:
            print(
                f"WARNING: {locale_path.name}: {len(missing)} key(s) not yet translated (Crowdin will fill them): {missing}"
            )
        if extra:
            errors.append(
                f"{locale_path.name}: extra keys not in source es.json (remove or add to source): {extra}"
            )

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)

    _ok("frontend translation files are consistent.")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _ok(message: str) -> None:
    print(f"OK: {message}")


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "pot":
        check_pot()
    elif command == "frontend":
        check_frontend()
    else:
        print(__doc__)
        print("Usage: python scripts/check_i18n.py [pot|frontend]")
        sys.exit(1)
