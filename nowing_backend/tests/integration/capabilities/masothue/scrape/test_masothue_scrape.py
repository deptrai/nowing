"""Integration tests for ``masothue.scrape`` (Story 16.1).

These tests cover the Pattern 6 SQL acceptance criteria for the masothue.com
company-data capability: canonical entity upsert/dedup, workspace RLS, Run and
TokenUsage persistence, and billing rollback.

The masothue-specific modules are not implemented yet, so several tests
intentionally fail (red phase) until ``bmad-dev-story`` adds:

* ``app.services.company_aggregator`` (fingerprint / merge / search_text)
* ``app.capabilities.masothue.scrape.{executor,schemas,definition}``
* ``BillingUnit.MASOTHUE_COMPANY`` and ``config.MASOTHUE_SCRAPE_MICROS_PER_ITEM``
* ``masothue.scrape`` in the capability registry

Tests that exercise the shared platform-billing SQL path use an existing
``BillingUnit`` as a surrogate and note the switch in their docstrings.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.canonical.tenant_context import set_canonical_workspace_id
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.runs import record_run, serialize_output
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalMergeHistory,
    Run,
    TokenUsage,
    User,
    Workspace,
)
from app.services.etl_credit_service import InsufficientCreditsError

pytestmark = [pytest.mark.integration]


def _company_fingerprint(tax_code: str | None, name: str, address: str) -> str:
    """Stable fingerprint matching the expected ``company_aggregator`` contract.

    Normalizes the tax code (strip whitespace/dashes, keep leading zeros) and
    falls back to ``name|address`` when no tax code is present.
    """
    if tax_code:
        normalized = tax_code.strip().replace(" ", "").replace("-", "")
        if normalized:
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    payload = f"{name.strip().lower()}|{address.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _search_text(data: dict[str, Any]) -> str:
    keys = [
        "name",
        "tax_code",
        "address",
        "legal_representative",
        "status",
        "company_type",
        "main_industry",
        "managed_by",
    ]
    return " ".join(str(data.get(k) or "") for k in keys).strip()


def _company_data(tax_code: str, name: str, **overrides: Any) -> dict[str, Any]:
    data = {
        "tax_code": tax_code,
        "name": name,
        "address": "10 Đường 3/2, P. 12, Q. 10, TP. HCM",
        "tax_address": "10 Đường 3/2",
        "legal_representative": "Nguyễn Văn A",
        "status": "Đang hoạt động",
        "company_type": "Công ty TNHH",
        "main_industry": "Sản xuất sữa",
        "active_date": "2010-01-01",
        "managed_by": "Cục Thuế TP. Hồ Chí Minh",
        "international_name": f"{name} Co., Ltd",
        "short_name": name.split()[-1] if name else None,
        "detail_url": f"https://masothue.com/{tax_code}-cong-ty-test",
    }
    data.update(overrides)
    data["fingerprint"] = _company_fingerprint(
        data["tax_code"], data["name"], data["address"]
    )
    data["search_text"] = _search_text(data)
    return data


# ---------------------------------------------------------------------------
# Surrogate input/output models used until ``app.capabilities.masothue.scrape``
# is implemented.  These expose the same BillableInput / BillableOutput surface
# the real executor will use.
# ---------------------------------------------------------------------------


class MasothueScrapeInput(BaseModel):
    query: str
    search_type: str = "auto"
    tax_code: str | None = None
    max_pages: int = Field(default=5, ge=0)
    max_items: int = Field(default=10, ge=0)
    resolve_detail: bool = True
    include_phone: bool = False

    @property
    def estimated_units(self) -> int:
        """Worst-case billable units for the pre-flight credit gate."""
        return self.max_items


class MasothueScrapeOutput(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        return len(self.items)


@pytest.fixture
async def another_workspace(db_session: AsyncSession, db_user: User) -> Workspace:
    """A second workspace for RLS / scoping tests."""
    space = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(space)
    await db_session.flush()
    return space


# ---------------------------------------------------------------------------
# Canonical entity / dedup (AC-8 Pattern 6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_canonical_company_creates_entity_and_source(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """Canonical upsert persists a company entity, source and merge history."""
    data = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    fingerprint = data["fingerprint"]
    search_text = data["search_text"]

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint=fingerprint,
        title=data["name"],
        data=data,
        search_text=search_text,
        source_name="masothue",
        source_record_id=data["tax_code"],
        source_snapshot=data,
        source_url=data["detail_url"],
        source_fingerprint=fingerprint,
    )

    assert entity.workspace_id == db_workspace.id
    assert entity.entity_type == "company"
    assert entity.fingerprint == fingerprint
    assert entity.canonical_title == data["name"]
    assert entity.canonical_data == data
    assert entity.search_text == search_text
    assert entity.version == 1
    assert entity.source_count == 1
    assert entity.embedding_status == "pending"

    row = (
        await db_session.execute(
            select(CanonicalEntity).where(CanonicalEntity.id == entity.id)
        )
    ).scalar_one()
    assert row.fingerprint == fingerprint
    assert row.canonical_data["tax_code"] == data["tax_code"]

    source = (
        await db_session.execute(
            select(CanonicalEntitySource).where(
                CanonicalEntitySource.canonical_entity_id == entity.id
            )
        )
    ).scalar_one()
    assert source.workspace_id == db_workspace.id
    assert source.source_name == "masothue"
    assert source.source_record_id == data["tax_code"]
    assert source.source_snapshot == data

    history = (
        await db_session.execute(
            select(CanonicalMergeHistory).where(
                CanonicalMergeHistory.canonical_entity_id == entity.id
            )
        )
    ).scalar_one()
    assert history.operation == "create"
    assert history.previous_version == 0
    assert history.new_version == 1


@pytest.mark.asyncio
async def test_upsert_canonical_company_is_idempotent(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """Re-fetching the same company updates the entity; no duplicate is created."""
    data = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    fingerprint = data["fingerprint"]

    first = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint=fingerprint,
        title=data["name"],
        data=data,
        search_text=data["search_text"],
        source_name="masothue",
        source_record_id=data["tax_code"],
        source_snapshot=data,
        source_url=data["detail_url"],
        source_fingerprint=fingerprint,
    )

    updated = dict(data)
    updated["status"] = "Tạm ngừng"
    updated["search_text"] = _search_text(updated)

    second = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint=fingerprint,
        title=updated["name"],
        data=updated,
        search_text=updated["search_text"],
        source_name="masothue",
        source_record_id=updated["tax_code"],
        source_snapshot=updated,
        source_url=updated["detail_url"],
        source_fingerprint=fingerprint,
    )

    assert second.id == first.id
    assert second.version == 2
    assert second.source_count == 1
    assert second.canonical_data["status"] == "Tạm ngừng"

    entity_rows = (
        await db_session.execute(
            select(func.count())
            .select_from(CanonicalEntity)
            .where(
                CanonicalEntity.workspace_id == db_workspace.id,
                CanonicalEntity.entity_type == "company",
                CanonicalEntity.fingerprint == fingerprint,
            )
        )
    ).scalar_one()
    assert entity_rows == 1

    source_rows = (
        await db_session.execute(
            select(func.count())
            .select_from(CanonicalEntitySource)
            .where(
                CanonicalEntitySource.workspace_id == db_workspace.id,
                CanonicalEntitySource.entity_type == "company",
                CanonicalEntitySource.source_name == "masothue",
                CanonicalEntitySource.source_record_id == data["tax_code"],
            )
        )
    ).scalar_one()
    assert source_rows == 1

    history = (
        await db_session.execute(
            select(func.count())
            .select_from(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == first.id)
        )
    ).scalar_one()
    assert history == 2


@pytest.mark.asyncio
async def test_canonical_company_fingerprint_unique_constraint(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """Two company entities in the same workspace cannot share a fingerprint."""
    await set_canonical_workspace_id(db_session, db_workspace.id)

    first = CanonicalEntity(
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint="fp-duplicate",
        canonical_title="Company A",
        canonical_data={},
        search_text="company a",
        source_count=0,
        version=1,
    )
    db_session.add(first)
    await db_session.flush()

    second = CanonicalEntity(
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint="fp-duplicate",
        canonical_title="Company B",
        canonical_data={},
        search_text="company b",
        source_count=0,
        version=1,
    )
    db_session.add(second)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_canonical_company_source_unique_constraint(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """A (workspace, entity_type, source_name, source_record_id) tuple is unique."""
    await set_canonical_workspace_id(db_session, db_workspace.id)

    e1 = CanonicalEntity(
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint="fp-source-a",
        canonical_title="Company A",
        canonical_data={},
        search_text="company a",
        source_count=0,
        version=1,
    )
    e2 = CanonicalEntity(
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint="fp-source-b",
        canonical_title="Company B",
        canonical_data={},
        search_text="company b",
        source_count=0,
        version=1,
    )
    db_session.add(e1)
    db_session.add(e2)
    await db_session.flush()

    s1 = CanonicalEntitySource(
        workspace_id=db_workspace.id,
        canonical_entity_id=e1.id,
        entity_type="company",
        source_name="masothue",
        source_record_id="same-mst",
        source_snapshot={},
    )
    db_session.add(s1)
    await db_session.flush()

    s2 = CanonicalEntitySource(
        workspace_id=db_workspace.id,
        canonical_entity_id=e2.id,
        entity_type="company",
        source_name="masothue",
        source_record_id="same-mst",
        source_snapshot={},
    )
    db_session.add(s2)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_canonical_company_is_workspace_scoped(
    db_session: AsyncSession,
    db_workspace: Workspace,
    another_workspace: Workspace,
):
    """Company entities are isolated to the workspace that owns them."""
    data_a = _company_data("0314539064-a", "Company A")
    data_b = _company_data("0314539064-b", "Company B")

    entity_a = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="company",
        fingerprint=data_a["fingerprint"],
        title=data_a["name"],
        data=data_a,
        search_text=data_a["search_text"],
        source_name="masothue",
        source_record_id=data_a["tax_code"],
        source_snapshot=data_a,
    )

    entity_b = await upsert_canonical_entity(
        db_session,
        workspace_id=another_workspace.id,
        entity_type="company",
        fingerprint=data_b["fingerprint"],
        title=data_b["name"],
        data=data_b,
        search_text=data_b["search_text"],
        source_name="masothue",
        source_record_id=data_b["tax_code"],
        source_snapshot=data_b,
    )

    scoped = (
        await db_session.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.workspace_id == db_workspace.id
            )
        )
    ).scalars().all()
    assert len(scoped) == 1
    assert scoped[0].id == entity_a.id

    other = (
        await db_session.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.workspace_id == another_workspace.id
            )
        )
    ).scalars().all()
    assert len(other) == 1
    assert other[0].id == entity_b.id

    # The canonical tenant context is set via set_config in the SQL session.
    await set_canonical_workspace_id(db_session, db_workspace.id)
    config_value = (
        await db_session.execute(text("SELECT current_setting('app.workspace_id')"))
    ).scalar()
    assert config_value == str(db_workspace.id)


# ---------------------------------------------------------------------------
# Run / TokenUsage persistence (AC-4, AC-5, AC-7 Pattern 6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_masothue_run_is_recorded(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A successful ``masothue.scrape`` call writes one ``runs`` row."""
    c1 = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    c2 = _company_data("0314539065", "Công ty Cổ phần Sữa Việt Nam")
    output = MasothueScrapeOutput(
        items=[c1, c2],
        cost_micros=6000,
        degraded=False,
    )
    payload = MasothueScrapeInput(query="vinamilk", max_items=2)

    run_id = await record_run(
        session=db_session,
        workspace_id=db_workspace.id,
        capability="masothue.scrape",
        origin="ui",
        status="success",
        serialized=serialize_output(output),
        input=payload.model_dump(exclude_none=True),
        user_id=db_user.id,
        duration_ms=1234,
        cost_micros=6000,
    )

    assert run_id is not None
    row = (
        await db_session.execute(select(Run).where(Run.id == uuid.UUID(run_id)))
    ).scalar_one()
    assert row.capability == "masothue.scrape"
    assert row.workspace_id == db_workspace.id
    assert row.user_id == db_user.id
    assert row.status == "success"
    assert row.item_count == 2
    assert row.cost_micros == 6000
    assert row.duration_ms == 1234


@pytest.mark.asyncio
async def test_masothue_degraded_run_is_recorded(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A degraded run is persisted with status ``degraded`` and zero cost."""
    output = MasothueScrapeOutput(
        items=[],
        cost_micros=0,
        degraded=True,
        degradation_reason="rate_limited",
    )
    payload = MasothueScrapeInput(query="vinamilk")

    run_id = await record_run(
        session=db_session,
        workspace_id=db_workspace.id,
        capability="masothue.scrape",
        origin="api",
        status="degraded",
        error="rate_limited",
        serialized=serialize_output(output),
        input=payload.model_dump(exclude_none=True),
        user_id=db_user.id,
        duration_ms=500,
        cost_micros=0,
    )

    assert run_id is not None
    row = (
        await db_session.execute(select(Run).where(Run.id == uuid.UUID(run_id)))
    ).scalar_one()
    assert row.status == "degraded"
    assert row.error == "rate_limited"
    assert row.cost_micros == 0
    assert row.item_count == 0


@pytest.mark.asyncio
async def test_masothue_billing_records_token_usage(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
):
    """AC-4 P6: a successful run writes exactly one TokenUsage audit row.

    Uses ``BillingUnit.BATDONGSAN_ITEM`` as a surrogate because
    ``MASOTHUE_COMPANY`` is not registered yet; the SQL path is identical.
    """
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3000)
    db_user.credit_micros_balance = 1_000_000

    c1 = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    c2 = _company_data("0314539065", "Công ty Cổ phần Sữa Việt Nam")
    output = MasothueScrapeOutput(items=[c1, c2], cost_micros=0, degraded=False)
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.BATDONGSAN_ITEM, ctx)

    assert charged == 2 * 3000
    assert db_user.credit_micros_balance == 1_000_000 - 2 * 3000

    rows = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].usage_type == "batdongsan_item"
    assert rows[0].cost_micros == 2 * 3000
    assert rows[0].user_id == db_user.id
    assert rows[0].call_details["items"] == 2


@pytest.mark.asyncio
async def test_masothue_billing_records_zero_cost_for_degraded_run(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
):
    """AC-5 P6: a degraded run records a 0-cost TokenUsage, debits nothing."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    output = MasothueScrapeOutput(
        items=[],
        cost_micros=0,
        degraded=True,
        degradation_reason="rate_limited",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.BATDONGSAN_ITEM, ctx)

    assert charged == 0
    assert db_user.credit_micros_balance == 1_000_000

    rows = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].cost_micros == 0
    assert rows[0].call_details["degradation_reason"] == "rate_limited"


@pytest.mark.asyncio
async def test_masothue_billing_preflight_fails_closed_on_insufficient_credits(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
):
    """AC-4 P6: the pre-flight gate blocks the run and nothing is charged."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3000)
    db_user.credit_micros_balance = 1000

    payload = MasothueScrapeInput(query="vinamilk", max_items=10)
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(payload, BillingUnit.BATDONGSAN_ITEM, ctx)

    assert db_user.credit_micros_balance == 1000
    rows = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_masothue_billing_is_charged_once_per_call(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
):
    """AC-4 P6: one capability charge call produces exactly one TokenUsage row."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3000)
    db_user.credit_micros_balance = 1_000_000

    c1 = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    output = MasothueScrapeOutput(items=[c1], cost_micros=0, degraded=False)
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    await charge_capability(output, BillingUnit.BATDONGSAN_ITEM, ctx)

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(TokenUsage)
            .where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert count == 1


# ---------------------------------------------------------------------------
# Red-phase tests for missing masothue implementation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_company_aggregator_helpers_exist():
    """AC-8: ``company_aggregator`` exposes fingerprint / merge / search_text."""
    from app.services.company_aggregator import (
        fingerprint,
        merge,
        normalize,
        search_text,
    )

    data = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    fp = fingerprint(data)
    assert fp == data["fingerprint"]

    canonical = {"name": data["name"], "tax_code": data["tax_code"]}
    merged = merge(canonical, data)
    assert merged["tax_code"] == data["tax_code"]

    text = search_text(data)
    assert data["tax_code"] in text

    normalized = normalize("  Vinamilk  ")
    assert normalized == "vinamilk"


@pytest.mark.asyncio
async def test_masothue_scrape_executor_exists():
    """AC-1/AC-7: the masothue scrape executor is importable and returns output."""
    from app.capabilities.masothue.scrape.executor import build_scrape_executor
    from app.capabilities.masothue.scrape.schemas import ScrapeInput, ScrapeOutput

    async def _fake_fetcher(_params: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": [_company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")],
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=_fake_fetcher)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert isinstance(out, ScrapeOutput)
    assert out.degraded is False
    assert out.total_items == 1


@pytest.mark.asyncio
async def test_masothue_billing_unit_is_registered():
    """AC-4: the MASOTHUE_COMPANY billing unit is wired into the platform biller."""
    from app.capabilities.core.billing import _PLATFORM_RATE_KEYS

    masothue_unit = getattr(BillingUnit, "MASOTHUE_COMPANY", None)
    assert masothue_unit is not None

    rate = getattr(config, "MASOTHUE_SCRAPE_MICROS_PER_ITEM", None)
    assert rate is not None

    assert masothue_unit in _PLATFORM_RATE_KEYS


@pytest.mark.asyncio
async def test_masothue_capability_is_registered():
    """AC-7: ``masothue.scrape`` appears in the capability registry."""
    from app.capabilities.core.store import all_capabilities

    names = {capability.name for capability in all_capabilities()}
    assert "masothue.scrape" in names
