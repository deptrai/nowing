"""Re-validate a memory by re-executing its source capability (Story 9.6b).

A run-derived memory carries an immutable recipe (``source_capability`` +
``source_input``) copied from the original ``Run``. Re-validation runs that
recipe again, compares the new output to the stored fact, and records the
outcome as a confidence bump or a ``MemoryVersion`` correction.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.canonical.tenant_context import set_request_tenant_context
from app.capabilities.core import execute_with_context
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.runs import record_run, serialize_output
from app.capabilities.core.store import get_capability
from app.capabilities.core.types import CapabilityContext
from app.db import Memory, MemorySourceType
from app.services.memory.repository import MemoryRepository

logger = logging.getLogger(__name__)


class RevalidationError(Exception):
    """Raised when a memory cannot be re-validated."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class RevalidationResult:
    """Outcome of a single re-validation attempt."""

    memory_id: int
    status: str  # "verified" | "mismatch" | "failed"
    memory: Memory
    cost_micros: int | None
    reason: str | None = None


def _extract_text(output: Any, capability_name: str) -> str:
    """Extract a comparable text string from a capability output.

    Capability outputs vary by verb. The priority order is intentionally simple
    for MVP:
    1. ``ResearchOutput``-style ``answer`` field.
    2. ``items`` list → JSON-serialized joined lines.
    3. Pydantic model → JSON.
    4. Fallback to ``str(output)``.

    ponytail: this is a naive content comparison. Upgrade path is a semantic
    or LLM judge when the corpus outgrows string equality.
    """
    if isinstance(output, BaseModel):
        dump = output.model_dump(exclude_none=True)
        if isinstance(dump, dict) and "answer" in dump:
            return str(dump["answer"])
        if (
            isinstance(dump, dict)
            and "items" in dump
            and isinstance(dump["items"], list)
        ):
            return "\n".join(
                json.dumps(item, default=str, ensure_ascii=False)
                for item in dump["items"]
            )
        return json.dumps(dump, default=str, ensure_ascii=False)

    # Plain objects used in tests may also expose ``model_dump``.
    if hasattr(output, "model_dump") and callable(output.model_dump):
        try:
            dump = output.model_dump()
            if isinstance(dump, dict) and "answer" in dump:
                return str(dump["answer"])
            if (
                isinstance(dump, dict)
                and "items" in dump
                and isinstance(dump["items"], list)
            ):
                return "\n".join(
                    json.dumps(item, default=str, ensure_ascii=False)
                    for item in dump["items"]
                )
            return json.dumps(dump, default=str, ensure_ascii=False)
        except Exception:
            pass

    if isinstance(output, dict):
        if "answer" in output:
            return str(output["answer"])
        if "items" in output and isinstance(output["items"], list):
            return "\n".join(
                json.dumps(item, default=str, ensure_ascii=False)
                for item in output["items"]
            )
        return json.dumps(output, default=str, ensure_ascii=False)

    return str(output)


def _normalize(text: str) -> str:
    """Case-insensitive, whitespace-normalized comparison."""
    return re.sub(r"\s+", " ", text.strip()).casefold()


class RevalidationService:
    """Service to re-validate a memory against a fresh capability run."""

    def __init__(self, session) -> None:
        self.session = session

    async def revalidate(
        self,
        memory_id: int,
        *,
        workspace_id: int | None = None,
        actor_id: Any | None = None,
    ) -> RevalidationResult:
        """Re-run the source capability of a memory and compare the result.

        ``source_capability`` and ``source_input`` are read from ``Memory``
        itself, so the original ``Run`` may already have been cleaned up.
        """
        # AC-18.8: load the memory by id-token, then enforce its tenant scope
        # for the rest of the re-validation writes.
        await set_request_tenant_context(self.session, memory_id=memory_id)
        memory = (
            await self.session.execute(select(Memory).where(Memory.id == memory_id))
        ).scalar_one_or_none()
        if memory is not None:
            await set_request_tenant_context(
                self.session,
                workspace_id=memory.workspace_id,
                client_id=memory.client_id,
            )

        if memory is None:
            raise RevalidationError("memory_not_found", "Memory not found.")

        if workspace_id is not None and memory.workspace_id != workspace_id:
            raise RevalidationError(
                "workspace_mismatch",
                "Memory does not belong to the specified workspace.",
            )

        if memory.source_capability is None or memory.source_input is None:
            raise RevalidationError(
                "not_revalidatable",
                "This memory source does not support re-validation.",
            )

        if memory.source_type != MemorySourceType.SCRAPER_RUN:
            raise RevalidationError(
                "not_revalidatable",
                "This memory source does not support re-validation.",
            )

        try:
            capability = get_capability(memory.source_capability)
        except KeyError as exc:
            raise RevalidationError(
                "capability_not_found",
                f"Capability '{memory.source_capability}' is no longer available.",
            ) from exc

        try:
            source_input = memory.source_input
            if isinstance(source_input, (dict, list)):
                payload = capability.input_schema.model_validate(source_input)
            else:
                # Fall back to treating the stored input as the raw model input.
                payload = capability.input_schema.model_validate(source_input)
        except ValidationError as exc:
            raise RevalidationError(
                "invalid_recipe",
                f"Stored input no longer matches capability schema: {exc.errors()}",
            ) from exc

        ctx = CapabilityContext(session=self.session, workspace_id=memory.workspace_id)
        try:
            await gate_capability(payload, capability.billing_unit, ctx)
        except Exception as exc:
            raise RevalidationError(
                "gate_failed",
                f"Re-validation was blocked by the billing gate: {exc}",
            ) from exc

        started = time.perf_counter()
        try:
            output = await execute_with_context(
                capability.executor, payload=payload, ctx=ctx
            )
        except Exception as exc:
            # Upstream errors become failed revalidations, not 500s.
            logger.exception("re-validation capability %s failed", capability.name)
            return RevalidationResult(
                memory_id=memory.id,
                status="failed",
                memory=memory,
                cost_micros=None,
                reason=f"Capability failed: {exc}",
            )

        duration_ms = int((time.perf_counter() - started) // 1000)
        cost_micros: int | None = None
        try:
            cost_micros = await charge_capability(output, capability.billing_unit, ctx)
        except Exception:
            logger.exception("charge failed for re-validation %s", memory_id)
            raise RevalidationError(
                "charge_failed",
                "Failed to charge for re-validation. The capability was executed but billing failed.",
            ) from None

        if isinstance(output, BaseModel):
            try:
                serialized = serialize_output(output)
                input_dump = payload.model_dump(exclude_none=True)
                await record_run(
                    self.session,
                    workspace_id=memory.workspace_id,
                    capability=capability.name,
                    origin="revalidate",
                    status="success",
                    serialized=serialized,
                    input=input_dump,
                    user_id=actor_id,
                    duration_ms=duration_ms,
                    cost_micros=cost_micros,
                )
            except Exception:
                logger.exception("record_run failed for re-validation %s", memory_id)

        extracted_text = _extract_text(output, capability.name)
        original_text = _normalize(memory.content)
        new_text = _normalize(extracted_text)

        repo = MemoryRepository(self.session)

        if new_text == original_text:
            bump = (1.0 - memory.confidence) * 0.2
            memory.confidence = round(min(1.0, memory.confidence + bump), 4)
            memory.updated_at = datetime.now(UTC)
            self.session.add(memory)
            await self.session.flush()

            return RevalidationResult(
                memory_id=memory.id,
                status="verified",
                memory=memory,
                cost_micros=cost_micros,
            )

        # Mismatch: lower confidence, update content to new fact, create version.
        damp = max(0.1, memory.confidence * 0.8)
        updated = await repo.update_memory(
            memory.id,
            corrected_content=extracted_text,
            corrected_by_id=actor_id,
            confidence=damp,
            skip_version_if_unchanged=False,
            commit=False,
        )

        return RevalidationResult(
            memory_id=memory.id,
            status="mismatch",
            memory=updated if updated is not None else memory,
            cost_micros=cost_micros,
        )
