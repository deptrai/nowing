"""Unit tests for Social Monitored Targets CRUD routes (Story 21.8a)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.auth.context import AuthContext
from app.db import SocialMonitoredTarget, User, Workspace, get_async_session
from app.routes.social_routes import router
from app.users import get_auth_context

pytestmark = pytest.mark.unit


def _fake_target(
    id: int = 1,
    workspace_id: int = 10,
    platform: str = "facebook_group",
    target_id: str = "grp_123",
    target_name: str = "HN Real Estate",
    is_active: bool = True,
    status: str = "active",
    account_id: str | None = "acc_01",
    proxy_url: str | None = "http://proxy:8080",
) -> SocialMonitoredTarget:
    target = SocialMonitoredTarget(
        workspace_id=workspace_id,
        platform=platform,
        target_id=target_id,
        target_name=target_name,
        target_url="https://facebook.com/groups/123",
        category="real_estate",
        is_active=is_active,
        realtime_stream=False,
        scrape_interval_minutes=15,
        status=status,
        proxy_url=proxy_url,
        account_id=account_id,
    )
    target.id = id
    return target


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items

    def first(self) -> Any:
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._items)


class _FakeSession:
    def __init__(self, workspace: Workspace | None = None, targets: list[SocialMonitoredTarget] | None = None) -> None:
        self.workspace = workspace
        self.targets = {t.id: t for t in (targets or [])}
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.raise_on_commit: Exception | None = None

    async def get(self, model: Any, ident: Any) -> Any:
        if model is Workspace:
            return self.workspace
        if model is SocialMonitoredTarget:
            return self.targets.get(ident)
        return None

    def add(self, obj: Any) -> None:
        if isinstance(obj, SocialMonitoredTarget) and not getattr(obj, "id", None):
            obj.id = len(self.targets) + 1
            self.targets[obj.id] = obj
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)
        if isinstance(obj, SocialMonitoredTarget) and obj.id in self.targets:
            del self.targets[obj.id]

    async def commit(self) -> None:
        if self.raise_on_commit:
            raise self.raise_on_commit

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(list(self.targets.values()))


@pytest.fixture
def fake_auth() -> AuthContext:
    user = User(email="test@nowing.vn")
    user.id = 1
    return AuthContext.session(user=user)


@pytest.fixture
def fake_workspace() -> Workspace:
    ws = Workspace(name="Test Workspace")
    ws.id = 10
    return ws


@pytest.fixture
def app(fake_auth: AuthContext, fake_workspace: Workspace) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


def test_create_social_target_success(app: FastAPI, fake_auth: AuthContext, fake_workspace: Workspace) -> None:
    session = _FakeSession(workspace=fake_workspace)
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        payload = {
            "platform": "facebook_group",
            "target_id": "bds_hanoi",
            "target_name": "BDS Ha Noi Group",
            "category": "bds",
            "scrape_interval_minutes": 30,
            "account_id": "fb_01",
        }
        resp = client.post("/workspaces/10/social-monitored-targets", json=payload)

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["platform"] == "facebook_group"
    assert data["target_id"] == "bds_hanoi"
    assert data["workspace_id"] == 10
    assert data["account_id"] == "fb_01"


def test_create_social_target_invalid_platform(app: FastAPI, fake_auth: AuthContext) -> None:
    session = _FakeSession()
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    client = TestClient(app)
    payload = {
        "platform": "unsupported_platform",
        "target_id": "123",
        "target_name": "Test",
    }
    resp = client.post("/workspaces/10/social-monitored-targets", json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_social_target_workspace_not_found(app: FastAPI, fake_auth: AuthContext) -> None:
    session = _FakeSession(workspace=None)
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        payload = {
            "platform": "tiktok_hashtag",
            "target_id": "bds",
            "target_name": "TikTok BDS",
        }
        resp = client.post("/workspaces/99/social-monitored-targets", json=payload)

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json()["detail"] == "Workspace not found"


def test_create_social_target_duplicate_conflict(app: FastAPI, fake_auth: AuthContext, fake_workspace: Workspace) -> None:
    session = _FakeSession(workspace=fake_workspace)
    session.raise_on_commit = IntegrityError("duplicate", None, None)
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        payload = {
            "platform": "chotot_category",
            "target_id": "nha_dat",
            "target_name": "Cho Tot Nha Dat",
        }
        resp = client.post("/workspaces/10/social-monitored-targets", json=payload)

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp.json()["detail"]


def test_list_social_targets_success(app: FastAPI, fake_auth: AuthContext) -> None:
    t1 = _fake_target(id=1, workspace_id=10, platform="facebook_group")
    t2 = _fake_target(id=2, workspace_id=10, platform="batdongsan_category")
    session = _FakeSession(targets=[t1, t2])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.get("/workspaces/10/social-monitored-targets?limit=10&offset=0")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[1]["id"] == 2


def test_get_social_target_success(app: FastAPI, fake_auth: AuthContext) -> None:
    t = _fake_target(id=5, workspace_id=10)
    session = _FakeSession(targets=[t])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.get("/workspaces/10/social-monitored-targets/5")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == 5


def test_get_social_target_not_found(app: FastAPI, fake_auth: AuthContext) -> None:
    session = _FakeSession(targets=[])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.get("/workspaces/10/social-monitored-targets/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_social_target_wrong_workspace_returns_404(app: FastAPI, fake_auth: AuthContext) -> None:
    t = _fake_target(id=5, workspace_id=20)
    session = _FakeSession(targets=[t])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.get("/workspaces/10/social-monitored-targets/5")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_update_social_target_success(app: FastAPI, fake_auth: AuthContext) -> None:
    t = _fake_target(id=1, workspace_id=10, target_name="Old Name")
    session = _FakeSession(targets=[t])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.patch(
            "/workspaces/10/social-monitored-targets/1",
            json={"target_name": "New Name", "scrape_interval_minutes": 60},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["target_name"] == "New Name"
    assert data["scrape_interval_minutes"] == 60


def test_delete_social_target_success(app: FastAPI, fake_auth: AuthContext) -> None:
    t = _fake_target(id=1, workspace_id=10)
    session = _FakeSession(targets=[t])
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", new=AsyncMock()):
        client = TestClient(app)
        resp = client.delete("/workspaces/10/social-monitored-targets/1")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert 1 not in session.targets


def test_routes_permission_denied(app: FastAPI, fake_auth: AuthContext) -> None:
    session = _FakeSession()
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: fake_auth

    with patch("app.routes.social_routes.check_permission", side_effect=HTTPException(status_code=403, detail="Forbidden")):
        client = TestClient(app)
        resp = client.get("/workspaces/10/social-monitored-targets")

    assert resp.status_code == status.HTTP_403_FORBIDDEN
