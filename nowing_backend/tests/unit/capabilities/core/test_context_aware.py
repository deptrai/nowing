"""Red-phase scaffolds for the shared context-aware capability seam (9.1a)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.capabilities.core.types import CapabilityContext

pytestmark = pytest.mark.unit


def test_core_exports_context_aware_execution_helper():
    import app.capabilities.core as core

    assert hasattr(core, "execute_with_context")


async def test_execute_with_context_accepts_executor_payload_and_context():
    import app.capabilities.core as core

    execute_with_context = getattr(core, "execute_with_context", None)
    assert execute_with_context is not None

    async def executor(payload):
        return {"received": payload}

    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=7)
    result = await execute_with_context(executor, payload="hello", ctx=ctx)
    assert result["received"] == "hello"
    assert result["workspace_id"] == 7


async def test_execute_with_context_preserves_legacy_executor_signature():
    """Capabilities that do not opt in keep the old ``executor(payload)`` shape."""
    import app.capabilities.core as core

    execute_with_context = getattr(core, "execute_with_context", None)
    assert execute_with_context is not None

    calls = []

    async def legacy_executor(payload):
        calls.append(payload)
        return {"ok": True}

    result = await execute_with_context(legacy_executor, payload="legacy")
    assert result == {"ok": True}
    assert calls == ["legacy"]
