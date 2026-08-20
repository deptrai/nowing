"""Deliver step for DSH wide-research missions: format the checkpoint matrix as .xlsx.

Runs the Pro Excel formatter script inside a Daytona sandbox and persists the
output to local storage so it can be served by ``sandbox_routes.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox import (
    get_local_sandbox_file,
    get_or_create_sandbox,
    persist_and_delete_sandbox,
)
from app.tasks.dsh_worker_crawl_subgraph import _is_valid_matrix

logger = logging.getLogger(__name__)

FORMATTER_SCRIPT_PATH = (
    Path(__file__).parent.parent.parent / "scripts" / "sandbox_pro_excel_template.py"
)

# Sandbox paths are absolute inside the Daytona container.
SANDBOX_INPUT_PATH = "/documents/wide_research_matrix.json"
SANDBOX_OUTPUT_PATH = "/documents/wide_research_output.xlsx"


def _redact_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    """Return a PII-safe copy of the wide-research matrix.

    ``sources`` are stripped to the whitelist used by the formatter template.
    All other top-level keys are preserved.
    """
    safe = {k: v for k, v in matrix.items() if k != "sources"}
    safe["sources"] = [
        {k: s[k] for k in ("title", "url", "source_type") if k in s}
        for s in matrix.get("sources", [])
        if isinstance(s, dict)
    ]
    return safe


def _load_formatter_script() -> str:
    if not FORMATTER_SCRIPT_PATH.exists():
        raise FileNotFoundError(
            f"Pro Excel formatter template not found: {FORMATTER_SCRIPT_PATH}"
        )
    return FORMATTER_SCRIPT_PATH.read_text(encoding="utf-8")


class DshDeliverSubgraph:
    """Minimal deliver subgraph for wide-research Excel generation."""

    def __init__(self, include_pii: bool = False) -> None:
        self.include_pii = include_pii

    async def run(
        self,
        mission_id: str,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generate a wide-research .xlsx deliverable and return the reference.

        Returns ``None`` if the checkpoint has no ``wide_research_matrix``.
        Raises on sandbox or formatter errors.
        """
        raw_matrix = checkpoint.get("wide_research_matrix")
        if not raw_matrix:
            logger.info(
                "No wide_research_matrix in mission %s checkpoint; skipping deliver",
                mission_id,
            )
            return None

        if not _is_valid_matrix(raw_matrix):
            logger.info(
                "Invalid wide_research_matrix in mission %s checkpoint; skipping deliver",
                mission_id,
            )
            return None

        if not isinstance(raw_matrix, dict):
            raise ValueError("checkpoint.wide_research_matrix must be a dict")

        matrix = raw_matrix if self.include_pii else _redact_matrix(raw_matrix)

        sandbox, _ = await get_or_create_sandbox(mission_id)

        script = _load_formatter_script()
        input_json = json.dumps(matrix, ensure_ascii=False, default=str).encode("utf-8")

        def _upload() -> None:
            sandbox.upload_files(
                [
                    ("/documents/formatter.py", script.encode("utf-8")),
                    (SANDBOX_INPUT_PATH, input_json),
                ]
            )

        await asyncio.to_thread(_upload)

        command = (
            f"python3 /documents/formatter.py "
            f"--input {SANDBOX_INPUT_PATH} "
            f"--output {SANDBOX_OUTPUT_PATH}"
        )
        if self.include_pii:
            command += " --include-pii"

        result = await sandbox.aexecute(command, timeout=300)
        output = (result.output or "").strip()
        if result.exit_code != 0:
            raise RuntimeError(
                f"Formatter failed for mission {mission_id}: "
                f"exit={result.exit_code} output={output}"
            )

        logger.info("Formatter output for mission %s: %s", mission_id, output)

        await persist_and_delete_sandbox(mission_id, [SANDBOX_OUTPUT_PATH])

        content = get_local_sandbox_file(mission_id, SANDBOX_OUTPUT_PATH)
        if content is None:
            raise FileNotFoundError(
                f"Deliverable was not persisted locally for mission {mission_id}"
            )

        return {
            "type": "xlsx",
            "filename": "wide_research_output.xlsx",
            "sandbox_path": SANDBOX_OUTPUT_PATH,
            "size": len(content),
            "created_at": datetime.now(UTC).isoformat(),
        }
