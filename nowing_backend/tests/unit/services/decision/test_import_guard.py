"""AD-J1 guard — only ``backends/jev.py`` may import ``typesafe_sdk``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DECISION_PKG = Path(__file__).resolve().parents[4] / "app" / "services" / "decision"
JEV_BACKEND = DECISION_PKG / "backends" / "jev.py"


def _imports_typesafe_sdk(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typesafe_sdk" or alias.name.startswith(
                    "typesafe_sdk."
                ):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "typesafe_sdk" or module.startswith("typesafe_sdk."):
                return True
    return False


@pytest.mark.unit
def test_jev_backend_is_the_only_typesafe_sdk_importer():
    assert _imports_typesafe_sdk(JEV_BACKEND)
    offenders = [
        str(path.relative_to(DECISION_PKG))
        for path in DECISION_PKG.rglob("*.py")
        if path != JEV_BACKEND and _imports_typesafe_sdk(path)
    ]
    assert not offenders, f"typesafe_sdk imported outside backends/jev.py: {offenders}"
