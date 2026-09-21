"""AD-J1 guard — ``typesafe_sdk`` imports are confined to an allowlist."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[4] / "app"
JEV_BACKEND = APP_ROOT / "services" / "decision" / "backends" / "jev.py"

# jev.py is the sanctioned adapter boundary (AD-J1); jev_router.py is the
# documented legacy path pending the story 39.2 rewire onto
# DecisionService. Any NEW importer anywhere under app/ fails the guard.
ALLOWLIST = frozenset(
    {
        Path("services/decision/backends/jev.py"),
        Path("agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py"),
    }
)


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
def test_typesafe_sdk_importers_confined_to_allowlist():
    assert _imports_typesafe_sdk(JEV_BACKEND)
    offenders = [
        str(path.relative_to(APP_ROOT))
        for path in APP_ROOT.rglob("*.py")
        if _imports_typesafe_sdk(path) and path.relative_to(APP_ROOT) not in ALLOWLIST
    ]
    assert not offenders, f"typesafe_sdk imported outside the allowlist: {offenders}"
