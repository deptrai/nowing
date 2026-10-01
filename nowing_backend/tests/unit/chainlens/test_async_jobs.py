"""Unit tests for ChainLens Async Research Jobs (Story 20.9)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.routes.async_research_routes import router as async_research_router
from app.services.chainlens.async_jobs import (
    ChainLensAsyncJobError,
    ChainLensAsyncJobsClient,
)
from app.users import require_session_context

pytestmark = pytest.mark.unit


@pytest.fixture
def async_client():
    return ChainLensAsyncJobsClient(base_url="http://mock-chainlens:3001")


def _auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


class TestAsyncJobsClient:
    """Client for submitting, polling, and recovering async research jobs."""

    async def test_submit_job_returns_run_id_and_pending_status(
        self, async_client: ChainLensAsyncJobsClient
    ):
        mock_res = MagicMock()
        mock_res.is_success = True
        mock_res.json.return_value = {
            "runId": "run_deep_123",
            "status": "pending",
            "createdAt": "2026-10-01T12:00:00Z",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_http):
            res = await async_client.submit_job(
                workspace_id=15,
                query="Báo cáo phân tích đối thủ AI Search",
                mode="quality",
            )

        assert res["runId"] == "run_deep_123"
        assert res["status"] == "pending"
        mock_http.post.assert_awaited_once()

    async def test_submit_job_http_error_raises_custom_exception(
        self, async_client: ChainLensAsyncJobsClient
    ):
        mock_res = MagicMock()
        mock_res.is_success = False
        mock_res.status_code = 503
        mock_res.text = "Service Unavailable"

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with (
            patch("httpx.AsyncClient", return_value=mock_http),
            pytest.raises(ChainLensAsyncJobError, match="503"),
        ):
            await async_client.submit_job(workspace_id=15, query="test")

    async def test_get_job_404_returns_none(
        self, async_client: ChainLensAsyncJobsClient
    ):
        mock_res = MagicMock()
        mock_res.status_code = 404

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_http):
            job = await async_client.get_job("non_existent_id")

        assert job is None

    async def test_recover_report_returns_result_without_re_billing(
        self, async_client: ChainLensAsyncJobsClient
    ):
        completed_job = {
            "runId": "run_done_999",
            "status": "completed",
            "result": {
                "report": "# Executive Deep Research\n\nFull analysis here...",
                "sources": [{"title": "TechCrunch", "url": "https://tc.com/1"}],
            },
        }

        async_client.get_job = AsyncMock(return_value=completed_job)  # type: ignore[method-assign]

        report = await async_client.recover_report("run_done_999", workspace_id=15)
        assert report is not None
        assert "# Executive Deep Research" in report["report"]
        assert len(report["sources"]) == 1

    async def test_recover_report_uncompleted_returns_none(
        self, async_client: ChainLensAsyncJobsClient
    ):
        running_job = {
            "runId": "run_running_888",
            "status": "running",
        }
        async_client.get_job = AsyncMock(return_value=running_job)  # type: ignore[method-assign]

        assert (
            await async_client.recover_report("run_running_888", workspace_id=15)
        ) is None


class TestAsyncResearchEndpoints:
    """REST API endpoints for async jobs."""

    @pytest.fixture
    def app(self):
        test_app = FastAPI()
        test_app.include_router(async_research_router)
        test_app.dependency_overrides[require_session_context] = _auth
        return test_app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_submit_job_returns_202_accepted(self, client: TestClient, app: FastAPI):
        from app.routes.async_research_routes import _get_async_jobs_client

        mock_client = MagicMock()
        mock_client.submit_job = AsyncMock(
            return_value={"runId": "run_abc", "status": "pending"}
        )
        app.dependency_overrides[_get_async_jobs_client] = lambda: mock_client

        resp = client.post(
            "/api/v1/workspaces/15/research/async-jobs",
            json={"query": "AI Agents Architecture 2026", "mode": "deep"},
        )
        assert resp.status_code == 202
        assert resp.json()["runId"] == "run_abc"

    def test_get_job_returns_200(self, client: TestClient, app: FastAPI):
        from app.routes.async_research_routes import _get_async_jobs_client

        mock_client = MagicMock()
        mock_client.get_job = AsyncMock(
            return_value={"runId": "run_abc", "status": "completed"}
        )
        app.dependency_overrides[_get_async_jobs_client] = lambda: mock_client

        resp = client.get("/api/v1/workspaces/15/research/async-jobs/run_abc")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_get_job_not_found_returns_404(self, client: TestClient, app: FastAPI):
        from app.routes.async_research_routes import _get_async_jobs_client

        mock_client = MagicMock()
        mock_client.get_job = AsyncMock(return_value=None)
        app.dependency_overrides[_get_async_jobs_client] = lambda: mock_client

        resp = client.get("/api/v1/workspaces/15/research/async-jobs/unknown_run")
        assert resp.status_code == 404
