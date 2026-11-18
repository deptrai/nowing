"""Unit tests Epic 44.2 — Campaign CRUD + launch + runs routes.

Wire-contract: response KHỚP FE ``campaignSchema`` (nowing_web/contracts/
types/campaign.types.ts) — mapper ``campaign_to_response`` là source-of-truth
backend. Fake session theo pattern ``test_projects_routes.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.lead_intelligence.services.campaign_service import (
    ConcurrentCampaignRunError,
)
from app.routes.campaign_routes import router as campaign_router
from app.users import get_auth_context, require_session_context

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Fake AsyncSession — execute/get/commit/refresh đủ cho CRUD routes.

    ``execute_results``: danh sách `_FakeResult` trả lần lượt theo thứ tự
    ``session.execute`` (mapper + routes gọi tuần tự, không idempotent)."""
    def __init__(
        self,
        *,
        campaigns: list[Any] | None = None,
        execute_results: list[_FakeResult] | None = None,
    ) -> None:
        self._campaigns = campaigns or []
        self._execute_results = list(execute_results or [])
        self.added: list[Any] = []
        self.committed = False
        self.executed_sql: list[str] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any, _params: Any = None) -> _FakeResult:
        sql = str(_stmt)
        if "set_config" in sql:
            # set_request_tenant_context phát 7 set_config GUC calls — không
            # consume queue, cũng không record (nhiễu assert SQL).
            return _FakeResult(None, [])
        self.executed_sql.append(sql)
        if self._execute_results:
            return self._execute_results.pop(0)
        return _FakeResult(None, [])

    async def get(self, model: type, obj_id: Any) -> Any:
        for c in self._campaigns:
            if getattr(c, "id", None) == obj_id:
                return c
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        pass

    async def flush(self) -> None:
        pass


_INPUT_PAYLOAD = {
    "name": "ICP Demand Campaign",
    "description": None,
    "workspace_id": 10,
    "direction": "demand",
    "icp_config": {
        "template": "custom",
        "target_industries": ["B2B SaaS"],
        "locations": ["Hà Nội"],
        "company_size_range": None,
        "tech_stack": [],
        "intents": ["BÁN"],
        "negative_keywords": [],
        "reverse_icp_url": None,
        "custom_instructions": None,
        "location_profile": None,
    },
    "source_budget_config": {
        "sources": ["muasamcong", "enterprise"],
        "expected_leads_target": 100,
        "max_daily_spend_vnd": 500000,
        "min_fit_score": 60,
        "min_intent_score": 50,
        "max_contacts_per_lead": 3,
        "exclude_dnc": True,
        "auto_unlock_verified_phones": False,
    },
    "launch_config": {
        "schedule_type": "once",
        "cron_expression": None,
        "start_time": None,
        "auto_start": True,
        "export_destination": "workspace",
        "notification_webhook": None,
    },
}


_PAYLOAD_UNSET: Any = object()


def _campaign(
    *,
    cid: UUID | None = None,
    status: str = "draft",
    payload: Any = _PAYLOAD_UNSET,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=cid or uuid4(),
        workspace_id=10,
        name="ICP Demand Campaign",
        direction="demand",
        status=status,
        # payload=None explicit → input_payload=None (implicit campaign);
        # không truyền → default _INPUT_PAYLOAD.
        input_payload=(
            dict(_INPUT_PAYLOAD) if payload is _PAYLOAD_UNSET else payload
        ),
        # Scalar fields 45.1 — mapper đọc trực tiếp.
        source="created",
        next_run_at=None,
        schedule_frequency=None,
        schedule_cron=None,
        max_runs=None,
        skipped_by_quota=0,
        created_by=uuid4(),
        created_at=now,
    )


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(campaign_router)
    return test_app


def _client(app: FastAPI, session: _FakeSession) -> TestClient:
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[require_session_context] = _fake_auth
    app.dependency_overrides[get_auth_context] = _fake_auth
    return TestClient(app)


def _patch_rbac():
    return patch(
        "app.dependencies.auth.check_permission", AsyncMock(return_value=None)
    )


@pytest.fixture(autouse=True)
def _patch_auth_check():
    """RequirePermission gọi app.dependencies.auth.check_permission — patch
    luôn để mọi route pass auth (unit test, RBAC đã cover ở test khác)."""
    with patch(
        "app.dependencies.auth.check_permission", AsyncMock(return_value=None)
    ), patch(
        "app.routes.campaign_routes.check_permission", AsyncMock(return_value=None)
    ):
        yield


# ---------------------------------------------------------------------------
# Wire-contract: mapper khớp campaignSchema
# ---------------------------------------------------------------------------


REQUIRED_FE_KEYS = {
    "id",
    "workspace_id",
    "name",
    "status",
    "icp_config",
    "source_budget_config",
    "launch_config",
    "collected_leads_count",
    "qualified_leads_count",
    "estimated_cost_vnd",
    "created_at",
}


def test_wire_contract_created_campaign_response(app: FastAPI):
    """POST create → 201 + response có đủ keys campaignSchema + sources min-1."""
    campaign = _campaign()
    session = _FakeSession(
        campaigns=[campaign],
        # execute tuần tự: dup pre-select (None) → INSERT...RETURNING id →
        # latest run row (None — 45.1 gộp spec_snapshot+finished_at) → count.
        execute_results=[
            _FakeResult(None),
            _FakeResult((campaign.id,)),
            _FakeResult(None),
            _FakeResult(0),
        ],
    )
    client = _client(app, session)

    with _patch_rbac():
        res = client.post(
            "/workspaces/10/campaigns", json=dict(_INPUT_PAYLOAD)
        )
    assert res.status_code == 201, res.text
    body = res.json()
    missing = REQUIRED_FE_KEYS - set(body)
    assert not missing, f"missing keys: {missing}"
    assert body["icp_config"]["target_industries"] == ["B2B SaaS"]
    assert body["source_budget_config"]["sources"] == ["muasamcong", "enterprise"]
    assert body["launch_config"]["schedule_type"] == "once"
    assert body["workspace_id"] == 10


def test_wire_contract_implicit_campaign_fallback(app: FastAPI):
    """GET detail implicit campaign (input_payload=None) → fallback shape từ
    spec_snapshot vẫn đủ keys campaignSchema."""
    campaign = _campaign(payload=None)
    snapshot = {
        "name": "Implicit",
        "direction": "demand",
        "icp_criteria": {"target_industries": ["B2B SaaS"]},
        "source_budget": {"sources": ["muasamcong"]},
        "max_total_leads": 50,
    }
    # execute tuần tự: latest run row (spec_snapshot, finished_at) → count.
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[
            _FakeResult((snapshot, None)),
            _FakeResult(3),
        ],
    )
    client = _client(app, session)

    with _patch_rbac():
        res = client.get(f"/workspaces/10/campaigns/{campaign.id}")
    assert res.status_code == 200, res.text
    body = res.json()
    missing = REQUIRED_FE_KEYS - set(body)
    assert not missing, f"missing keys: {missing}"
    # FE schema: sources min-1 — fallback đảm bảo không rỗng.
    assert len(body["source_budget_config"]["sources"]) >= 1


# ---------------------------------------------------------------------------
# List / detail / runs
# ---------------------------------------------------------------------------


def test_list_campaigns_response_shape(app: FastAPI):
    # execute: count → rows(items).
    session = _FakeSession(
        execute_results=[_FakeResult(1), _FakeResult(None, [_campaign()])]
    )
    client = _client(app, session)

    with _patch_rbac():
        res = client.get("/workspaces/10/campaigns?page=1&page_size=20")
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert isinstance(body["items"], list)


def test_list_include_implicit_exposes_execute_campaigns(app: FastAPI):
    """LIST_IMPLICIT — ?include_implicit=true bỏ filter source='created';
    default (không flag) vẫn filter source='created'."""
    session = _FakeSession(execute_results=[_FakeResult(0), _FakeResult(None, [])])
    client = _client(app, session)
    res = client.get("/workspaces/10/campaigns?include_implicit=true")
    assert res.status_code == 200, res.text
    count_sql = session.executed_sql[0]
    assert "lead_campaigns.source" not in count_sql

    session2 = _FakeSession(
        execute_results=[_FakeResult(0), _FakeResult(None, [])]
    )
    res2 = _client(app, session2).get("/workspaces/10/campaigns")
    assert res2.status_code == 200, res2.text
    assert "lead_campaigns.source" in session2.executed_sql[0]


def test_list_page_size_cap_100(app: FastAPI):
    session = _FakeSession()
    client = _client(app, session)
    with _patch_rbac():
        res = client.get("/workspaces/10/campaigns?page_size=500")
    assert res.status_code == 422


def test_get_campaign_not_found(app: FastAPI):
    session = _FakeSession()
    client = _client(app, session)
    with _patch_rbac():
        res = client.get(f"/workspaces/10/campaigns/{uuid4()}")
    assert res.status_code == 404


def test_get_campaign_wrong_workspace_404(app: FastAPI):
    campaign = _campaign()
    campaign.workspace_id = 99
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.get(f"/workspaces/10/campaigns/{campaign.id}")
    assert res.status_code == 404


def test_list_runs_newest_first_shape(app: FastAPI):
    campaign = _campaign()
    now = datetime.now(UTC)
    run = SimpleNamespace(
        id=uuid4(),
        campaign_id=campaign.id,
        status="completed",
        trigger="api",
        started_at=now,
        finished_at=now,
        stats={"total_deduplicated": 5},
        cost_micros=1200,
        error=None,
    )
    # execute: count → rows.
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[_FakeResult(1), _FakeResult(None, [run])],
    )
    client = _client(app, session)

    with _patch_rbac():
        res = client.get(f"/workspaces/10/campaigns/{campaign.id}/runs")
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    item = body["items"][0]
    assert item["status"] == "completed"
    # 45.1: run response expose stats/cost_micros.
    assert item["stats"] == {"total_deduplicated": 5}
    assert item["cost_micros"] == 1200


def test_presets_path_precedence(app: FastAPI):
    """Regression: /campaigns/presets không bị shadow bởi /{campaign_id}."""
    session = _FakeSession()
    client = _client(app, session)
    with _patch_rbac():
        res = client.get("/workspaces/10/campaigns/presets")
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)


# ---------------------------------------------------------------------------
# Create / PATCH / launch / pause
# ---------------------------------------------------------------------------


def test_create_duplicate_returns_409(app: FastAPI):
    # execute: dup pre-select → trả row truthy.
    campaign = _campaign()
    session = _FakeSession(
        campaigns=[campaign], execute_results=[_FakeResult((uuid4(),))]
    )
    client = _client(app, session)
    with _patch_rbac():
        res = client.post("/workspaces/10/campaigns", json=dict(_INPUT_PAYLOAD))
    assert res.status_code == 409
    assert "đã tồn tại" in res.json()["detail"]


def test_create_invalid_payload_422(app: FastAPI):
    session = _FakeSession()
    client = _client(app, session)
    bad = dict(_INPUT_PAYLOAD)
    bad["direction"] = "sideways"
    with _patch_rbac():
        res = client.post("/workspaces/10/campaigns", json=bad)
    assert res.status_code == 422


def test_patch_name_and_status(app: FastAPI):
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"name": "Tên mới", "status": "paused"},
        )
    assert res.status_code == 200, res.text
    assert campaign.name == "Tên mới"
    assert campaign.status == "paused"


def test_patch_machine_status_422(app: FastAPI):
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    for bad_status in ("running", "completed", "failed"):
        with _patch_rbac():
            res = client.patch(
                f"/workspaces/10/campaigns/{campaign.id}",
                json={"status": bad_status},
            )
        assert res.status_code == 422, bad_status


def test_patch_name_clash_409(app: FastAPI):
    campaign = _campaign()
    # execute: name clash pre-select → trả id khác.
    session = _FakeSession(
        campaigns=[campaign], execute_results=[_FakeResult((uuid4(),))]
    )
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"name": "Trùng tên"},
        )
    assert res.status_code == 409


def test_launch_paused_409(app: FastAPI):
    campaign = _campaign(status="paused")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac(), patch(
        "app.routes.campaign_routes._launch_campaign_run"
    ) as launch_mock:
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/launch")
    assert res.status_code == 409
    launch_mock.apply_async.assert_not_called()


def test_launch_archived_409(app: FastAPI):
    campaign = _campaign(status="archived")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac(), patch(
        "app.routes.campaign_routes._launch_campaign_run"
    ) as launch_mock:
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/launch")
    assert res.status_code == 409
    launch_mock.apply_async.assert_not_called()


def test_launch_queues_task(app: FastAPI):
    """Launch happy path: commit bookkeeping + queue celery, response run-shape."""
    campaign = _campaign()
    run = SimpleNamespace(id=uuid4(), trigger="api")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac(), patch(
        "app.routes.campaign_routes.campaign_service.open_campaign_run",
        AsyncMock(return_value=run),
    ), patch(
        "app.routes.campaign_routes._launch_campaign_run"
    ) as launch_mock:
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/launch")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "queued"
    assert body["campaign_id"] == str(campaign.id)
    assert body["id"] == str(run.id)
    launch_mock.apply_async.assert_called_once_with(
        args=[str(campaign.id), str(run.id), 10]
    )
    assert session.committed


def test_launch_concurrent_run_409(app: FastAPI):
    """LAUNCH_RUNNING — đã có run 'running' → 409, không queue task."""
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac(), patch(
        "app.routes.campaign_routes.campaign_service.open_campaign_run",
        AsyncMock(
            side_effect=ConcurrentCampaignRunError(campaign.id, uuid4())
        ),
    ), patch(
        "app.routes.campaign_routes._launch_campaign_run"
    ) as launch_mock:
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/launch")
    assert res.status_code == 409, res.text
    launch_mock.apply_async.assert_not_called()


def test_pause_from_running(app: FastAPI):
    campaign = _campaign(status="running")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/pause")
    assert res.status_code == 200, res.text
    assert campaign.status == "paused"


def test_pause_from_draft_422(app: FastAPI):
    campaign = _campaign(status="draft")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.post(f"/workspaces/10/campaigns/{campaign.id}/pause")
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 45.3 — schedule scalars + archived guard (M1–M9)
# ---------------------------------------------------------------------------


def test_patch_schedule_custom_cron(app: FastAPI):
    """M1: PATCH {frequency:'custom', cron} → scalars set + next_run_at."""
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={
                "schedule_frequency": "custom",
                "schedule_cron": "0 9 * * 1",
            },
        )
    assert res.status_code == 200, res.text
    assert campaign.schedule_frequency == "custom"
    assert campaign.schedule_cron == "0 9 * * 1"
    assert campaign.next_run_at is not None
    assert campaign.next_run_at > datetime.now(UTC)


def test_patch_schedule_cron_invalid_422(app: FastAPI):
    """M2: cron xấu → 422; custom thiếu cron → 422."""
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"schedule_cron": "not-cron"},
        )
        assert res.status_code == 422, res.text
        res2 = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"schedule_frequency": "custom"},
        )
        assert res2.status_code == 422, res2.text


def test_patch_status_scheduled_no_schedule_422(app: FastAPI):
    """M3: PATCH status='scheduled' khi không có freq/cron → 422."""
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"status": "scheduled"},
        )
    assert res.status_code == 422, res.text


def test_patch_archived_any_status_422(app: FastAPI):
    """M4: campaign archived + PATCH status bất kỳ → 422 (one-way archive)."""
    campaign = _campaign(status="archived")
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    for st in ("scheduled", "paused", "draft", "archived"):
        with _patch_rbac():
            res = client.patch(
                f"/workspaces/10/campaigns/{campaign.id}",
                json={"status": st},
            )
        assert res.status_code == 422, st
    # PATCH name trên archived vẫn OK (AC3).
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"name": "Tên mới"},
        )
    assert res.status_code == 200, res.text
    assert campaign.name == "Tên mới"


def test_patch_resume_paused_with_cron(app: FastAPI):
    """M5: paused + cron sẵn + PATCH status='scheduled' → next_run_at ≠ None."""
    campaign = _campaign(status="paused")
    campaign.schedule_frequency = "custom"
    campaign.schedule_cron = "0 8 * * *"
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"status": "scheduled"},
        )
    assert res.status_code == 200, res.text
    assert campaign.status == "scheduled"
    assert campaign.next_run_at is not None


def test_patch_frequency_change_recomputes(app: FastAPI):
    """M6: scheduled + PATCH frequency='daily' → recompute + cron cleared."""
    campaign = _campaign(status="scheduled")
    campaign.schedule_frequency = "custom"
    campaign.schedule_cron = "0 9 * * 1"
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"schedule_frequency": "daily"},
        )
    assert res.status_code == 200, res.text
    assert campaign.schedule_frequency == "daily"
    assert campaign.schedule_cron is None
    assert campaign.next_run_at is not None


def test_patch_once_clears_schedule(app: FastAPI):
    """M7: PATCH frequency='once' → cron=None, next_run_at=None."""
    campaign = _campaign(status="scheduled")
    campaign.schedule_frequency = "custom"
    campaign.schedule_cron = "0 8 * * *"
    campaign.next_run_at = datetime.now(UTC)
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    with _patch_rbac():
        res = client.patch(
            f"/workspaces/10/campaigns/{campaign.id}",
            json={"schedule_frequency": "once"},
        )
    assert res.status_code == 200, res.text
    assert campaign.schedule_frequency == "once"
    assert campaign.schedule_cron is None
    assert campaign.next_run_at is None


def test_create_recurring_sets_schedule_scalars(app: FastAPI):
    """M8: POST create launch_config recurring+cron → scalars + next_run_at."""
    campaign = _campaign()
    session = _FakeSession(
        campaigns=[campaign],
        # execute: dup pre-select → INSERT RETURNING id → latest run → count.
        execute_results=[
            _FakeResult(None),
            _FakeResult((campaign.id,)),
            _FakeResult(None),
            _FakeResult(0),
        ],
    )
    client = _client(app, session)
    payload = dict(_INPUT_PAYLOAD)
    payload["launch_config"] = {
        **_INPUT_PAYLOAD["launch_config"],
        "schedule_type": "recurring",
        "cron_expression": "0 8 * * *",
    }
    with _patch_rbac():
        res = client.post("/workspaces/10/campaigns", json=payload)
    assert res.status_code == 201, res.text
    assert campaign.schedule_frequency == "custom"
    assert campaign.schedule_cron == "0 8 * * *"
    assert campaign.next_run_at is not None
    body = res.json()
    assert body["schedule_frequency"] == "custom"
    assert body["schedule_cron"] == "0 8 * * *"
    assert body["next_run_at"] is not None


def test_create_recurring_missing_cron_422(app: FastAPI):
    """M9: recurring thiếu/sai cron_expression → 422, không query/insert gì."""
    session = _FakeSession()
    client = _client(app, session)
    for bad_cron in (None, "not-a-cron"):
        payload = dict(_INPUT_PAYLOAD)
        payload["launch_config"] = {
            **_INPUT_PAYLOAD["launch_config"],
            "schedule_type": "recurring",
            "cron_expression": bad_cron,
        }
        with _patch_rbac():
            res = client.post("/workspaces/10/campaigns", json=payload)
        assert res.status_code == 422, bad_cron
    # 422 trước insert → không có SQL nào chạy (set_config đã bị fake bỏ qua).
    assert session.executed_sql == []
    assert not session.committed


# ---------------------------------------------------------------------------
# /execute?async=true
# ---------------------------------------------------------------------------


def test_execute_async_without_persist_422(app: FastAPI):
    session = _FakeSession()
    client = _client(app, session)
    with patch("app.utils.rbac.check_permission", AsyncMock(return_value=None)):
        res = client.post(
            "/workspaces/10/campaigns/execute?persist=false&async=true",
            json=dict(_INPUT_PAYLOAD),
        )
    assert res.status_code == 422


def test_execute_async_queues_task(app: FastAPI):
    """persist=true&async=true → bookkeeping + queue, response {campaign_id,
    run_id, status:'queued'}."""
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)

    open_run = SimpleNamespace(id=uuid4())
    with patch(
        "app.routes.campaign_routes.campaign_service.get_or_create_campaign",
        AsyncMock(return_value=campaign),
    ), patch(
        "app.routes.campaign_routes.campaign_service.open_campaign_run",
        AsyncMock(return_value=open_run),
    ), patch(
        "app.routes.campaign_routes._launch_campaign_run"
    ) as launch_mock:
        res = client.post(
            "/workspaces/10/campaigns/execute?persist=true&async=true",
            json=dict(_INPUT_PAYLOAD),
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {
        "campaign_id": str(campaign.id),
        "run_id": str(open_run.id),
        "status": "queued",
    }
    launch_mock.apply_async.assert_called_once()
    assert session.committed
