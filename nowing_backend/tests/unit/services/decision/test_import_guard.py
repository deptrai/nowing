"""AD-J1 guard — ``typesafe_sdk`` imports are confined to an allowlist."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[4] / "app"
JEV_BACKEND = APP_ROOT / "services" / "decision" / "backends" / "jev.py"

# jev.py is the sanctioned adapter boundary (AD-J1). Any NEW importer
# anywhere under app/ fails the guard.
ALLOWLIST = frozenset(
    {
        Path("services/decision/backends/jev.py"),
    }
)


def _matches_typesafe(module: str) -> bool:
    return module == "typesafe_sdk" or module.startswith("typesafe_sdk.")


def _is_dynamic_typesafe_import(node: ast.Call) -> bool:
    """Flag ``importlib.import_module("typesafe_sdk...")`` and
    ``__import__("typesafe_sdk...")`` — the static-import walk misses
    these, and either would smuggle the SDK past the allowlist."""
    func = node.func
    is_dynamic = (
        (isinstance(func, ast.Name) and func.id == "__import__")
        or (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
        )
    )
    if not is_dynamic or not node.args:
        return False
    first = node.args[0]
    return (
        isinstance(first, ast.Constant)
        and isinstance(first.value, str)
        and _matches_typesafe(first.value)
    )


def _source_uses_typesafe_sdk(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _matches_typesafe(alias.name):
                    return True
        elif isinstance(node, ast.ImportFrom):
            if _matches_typesafe(node.module or ""):
                return True
        elif isinstance(node, ast.Call) and _is_dynamic_typesafe_import(node):
            return True
    return False


def _imports_typesafe_sdk(path: Path) -> bool:
    return _source_uses_typesafe_sdk(path.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_typesafe_sdk_importers_confined_to_allowlist():
    assert _imports_typesafe_sdk(JEV_BACKEND)
    offenders = [
        str(path.relative_to(APP_ROOT))
        for path in APP_ROOT.rglob("*.py")
        if _imports_typesafe_sdk(path) and path.relative_to(APP_ROOT) not in ALLOWLIST
    ]
    assert not offenders, f"typesafe_sdk imported outside the allowlist: {offenders}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        'import typesafe_sdk',
        'import typesafe_sdk.client',
        'from typesafe_sdk import decide',
        'from typesafe_sdk.client import Client',
        'importlib.import_module("typesafe_sdk")',
        'importlib.import_module("typesafe_sdk.client")',
        'm = importlib.import_module("typesafe_sdk")',
        '__import__("typesafe_sdk")',
        '__import__("typesafe_sdk.client")',
    ],
)
def test_source_check_flags_typesafe_sdk(source):
    assert _source_uses_typesafe_sdk(source)


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        'import os',
        'import typesafe_helpers',  # prefix alone is not the SDK
        'importlib.import_module("other_sdk")',
        'importlib.import_module("typesafe")',
        '__import__("typesafe")',
        'importlib.import_module(name)',  # non-literal — nothing to prove
        '__import__()',
        'import_module("typesafe_sdk")',  # bare name ≠ importlib.import_module
    ],
)
def test_source_check_ignores_non_typesafe(source):
    assert not _source_uses_typesafe_sdk(source)
