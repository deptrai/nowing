"""Client for invoking entity extraction endpoint or replaying recorded cassettes."""

from __future__ import annotations

import asyncio
import copy
import os
import re
from typing import Any

from nowing_evals.core.cassette import Cassette
from nowing_evals.core.registry import RunContext

_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_case_id(case_id: str) -> str:
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("case_id must be a non-empty string")
    if not _CASE_ID_RE.match(case_id):
        raise ValueError(
            f"case_id {case_id!r} contains unsafe characters; only [a-zA-Z0-9_-] allowed"
        )
    return case_id


def _resolve_cassette_path(cassettes_dir: Any, case_id: str) -> Any:
    _validate_case_id(case_id)
    expected = cassettes_dir / f"{case_id}.sse.jsonl"
    try:
        resolved = expected.resolve()
        cassettes_resolved = cassettes_dir.resolve()
        if not str(resolved).startswith(str(cassettes_resolved)):
            raise ValueError(
                f"cassette path {expected} resolves outside cassettes directory {cassettes_dir}"
            )
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid cassette path for case {case_id!r}: {exc}") from exc
    return expected


def _sanitize_cassette_body(body: dict[str, Any]) -> dict[str, Any]:
    """Replace PII in a recorded cassette body with deterministic synthetic values.

    The mapping preserves relationships (a unique phone/tax/company always maps
    to the same synthetic value) while keeping the shape of the response intact.
    """
    from .metrics import normalize_vn_phone

    sanitized = copy.deepcopy(body)
    phone_map: dict[str, str] = {}
    tax_map: dict[str, str] = {}
    company_map: dict[str, str] = {}

    def _synth_phone(idx: int) -> str:
        return f"090{idx:07d}"

    def _synth_tax(tax_id: str, idx: int) -> str:
        base = f"010{idx:07d}"
        return f"{base}-001" if len(re.sub(r"[^\d]", "", tax_id)) == 13 else base

    def _synth_company(idx: int) -> str:
        return f"Công ty TNHH Sanitized {idx}"

    phones = sanitized.get("phones") or []
    for i, phone in enumerate(phones):
        norm = normalize_vn_phone(phone)
        if not norm:
            continue
        if norm not in phone_map:
            phone_map[norm] = _synth_phone(len(phone_map) + 1)
        phones[i] = phone_map[norm]

    tax_ids = sanitized.get("tax_ids") or []
    for i, tax_id in enumerate(tax_ids):
        digits = re.sub(r"[^\d]", "", tax_id)
        if not digits or len(digits) not in (10, 13):
            continue
        if digits not in tax_map:
            tax_map[digits] = _synth_tax(digits, len(tax_map) + 1)
        tax_ids[i] = tax_map[digits]

    company_name = sanitized.get("company_name")
    if isinstance(company_name, str) and company_name.strip():
        if company_name not in company_map:
            company_map[company_name] = _synth_company(len(company_map) + 1)
        sanitized["company_name"] = company_map[company_name]

    # tax_ids_valid stays untouched; it is a boolean array, not PII.
    return sanitized


class ExtractorClient:
    """Invokes live REST endpoint or loads recorded cassettes for replay."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.mode = getattr(ctx, "mode", "live")
        self.cassettes_dir = ctx.replay_artifacts_dir()
        self.record = getattr(ctx, "record", False) or os.getenv("RECORD_CASSETTES") == "true"

    async def extract_entities(self, case_id: str, source_text: str) -> dict[str, Any]:
        """Extract entities for a test case."""
        _validate_case_id(case_id)

        if self.mode == "replay":
            cassette_path = _resolve_cassette_path(self.cassettes_dir, case_id)
            cassette = Cassette.load(cassette_path)
            if cassette.status != 200:
                raise RuntimeError(
                    f"Replay cassette {case_id} recorded non-200 status {cassette.status}: {cassette.body}"
                )
            return cassette.body

        # Live mode — call local test endpoint
        config = getattr(self.ctx, "config", None)
        if config is not None:
            base = (config.nowing_api_base or "http://localhost:8000").rstrip("/")
        else:
            base = "http://localhost:8000"
        url = f"{base}/api/v1/test/extract-entities"
        secret = os.environ.get("TEST_EXTRACTION_SECRET")
        if not secret:
            raise RuntimeError(
                "TEST_EXTRACTION_SECRET must be set to use lead extraction live mode"
            )
        headers = {"X-Internal-Test": secret}
        payload = {"source_text": source_text}

        # Throttle live calls to stay under the backend's 30/minute rate limit.
        await asyncio.sleep(2.1)

        resp = await self.ctx.http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()

        if self.record:
            cassette_path = _resolve_cassette_path(self.cassettes_dir, case_id)
            sanitized = _sanitize_cassette_body(body)
            cassette = Cassette(
                type="rest",
                status=resp.status_code,
                headers=dict(resp.headers),
                body=sanitized,
            )
            cassette.save(cassette_path)

        return body
