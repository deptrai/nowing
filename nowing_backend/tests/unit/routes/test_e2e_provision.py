"""Unit tests for ``POST /__e2e__/connectors/provision``.

The route is registered conditionally in ``app.routes`` — tests mount the
underlying ``e2e_provision.router`` directly and toggle ``E2E_PROVISION_ENABLED``
/ ``E2E_PROVIDER_ENV`` through monkeypatch, since ``app.config`` reads env at
import time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import SearchSourceConnector, SearchSourceConnectorType, get_async_session
from app.routes.e2e_provision import router as e2e_provision_router
from app.users import require_superuser

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])

    def scalar(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stub — queue results, capture adds."""

    def __init__(self, results: list[_FakeResult] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self._results = list(results or [])

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 42
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        if not self._results:
            return _FakeResult()
        return self._results.pop(0)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)


def _superuser_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=True)
    return AuthContext.session(user)


def _non_superuser_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(e2e_provision_router)
    test_app.dependency_overrides[require_superuser] = _superuser_auth
    return test_app


def test_missing_playwright_header_returns_404(app: FastAPI) -> None:
    """No ``x-playwright-test: true`` header → 404 (gate stays invisible)."""
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
    )
    assert res.status_code == 404


def test_wrong_playwright_header_value_returns_404(app: FastAPI) -> None:
    """``x-playwright-test: false`` is not accepted — must be exactly "true"."""
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
        headers={"x-playwright-test": "false"},
    )
    assert res.status_code == 404


def test_non_superuser_returns_403() -> None:
    """Playwright header present, but user isn't superuser → require_superuser rejects.

    The real ``require_superuser`` dep calls ``require_session_context`` first,
    which needs an Authorization header / session cookie — when absent, auth
    fails at that earlier layer (401). Either way the provision body never runs.
    """
    test_app = FastAPI()
    test_app.include_router(e2e_provision_router)
    test_app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    # No require_superuser override → real dep runs and rejects unauthenticated.
    client = TestClient(test_app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code in (401, 403)


def test_unsupported_connector_returns_422(app: FastAPI, monkeypatch) -> None:
    """``connector: "unknown"`` → 422."""
    from app.config import config

    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    monkeypatch.setattr(
        config, "E2E_PROVIDER_ENV", {"slack": {"bot_token": "x", "team_id": "T1"}}, raising=False
    )
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "unknown_provider", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 422


def test_missing_provider_env_returns_404(app: FastAPI, monkeypatch) -> None:
    """Provider listed but its required env vars are unset → 404."""
    from app.config import config

    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    # Slack listed but bot_token missing → 404
    monkeypatch.setattr(
        config,
        "E2E_PROVIDER_ENV",
        {"slack": {"bot_token": None, "team_id": None, "team_name": None}},
        raising=False,
    )
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 404
    assert "slack" in res.json()["detail"].lower()


def test_provision_slack_creates_row(app: FastAPI, monkeypatch) -> None:
    """Happy path: valid superuser + playwright header + slack env → 200 + row."""
    from app.config import config

    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-32bytes-long!!!!", raising=False)
    monkeypatch.setattr(
        config,
        "E2E_PROVIDER_ENV",
        {
            "slack": {
                "bot_token": "xoxb-e2e-fake",
                "refresh_token": None,
                "bot_user_id": "U123",
                "team_id": "T123",
                "team_name": "E2E Team",
            }
        },
        raising=False,
    )

    fake_session = _FakeSession(results=[_FakeResult(value=None)])  # no existing connector
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["workspace_id"] == 15
    assert body["connector_type"] == SearchSourceConnectorType.SLACK_CONNECTOR.value
    assert "connector_id" in body
    # Secrets never in response
    assert "xoxb" not in res.text
    assert "bot_token" not in res.text

    # Row was added with encrypted bot_token
    assert len(fake_session.added) == 1
    row = fake_session.added[0]
    assert isinstance(row, SearchSourceConnector)
    assert row.connector_type == SearchSourceConnectorType.SLACK_CONNECTOR
    assert row.workspace_id == 15
    assert row.config["_token_encrypted"] is True
    assert row.config["bot_token"]  # encrypted ciphertext, not plaintext
    assert row.config["bot_token"] != "xoxb-e2e-fake"


def test_provision_is_idempotent_updates_existing(app: FastAPI, monkeypatch) -> None:
    """Existing (ws, user, type, name) row → update config, no new row."""
    from app.config import config

    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-32bytes-long!!!!", raising=False)
    monkeypatch.setattr(
        config,
        "E2E_PROVIDER_ENV",
        {
            "slack": {
                "bot_token": "xoxb-rotated",
                "refresh_token": None,
                "bot_user_id": "U1",
                "team_id": "T1",
                "team_name": "E2E",
            }
        },
        raising=False,
    )

    existing = SearchSourceConnector(
        id=99,
        name="E2E Slack",
        connector_type=SearchSourceConnectorType.SLACK_CONNECTOR,
        is_indexable=False,
        config={"bot_token": "old"},
        workspace_id=15,
        user_id=uuid4(),
    )
    fake_session = _FakeSession(results=[_FakeResult(value=existing)])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    # Need to pass name explicitly so it matches existing.name
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15, "name": "E2E Slack"},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["connector_id"] == 99
    # Same row updated — nothing newly added to session
    assert len(fake_session.added) == 0


def test_provision_mcp_oauth_family_linear(app: FastAPI, monkeypatch) -> None:
    """Linear (MCP OAuth) stores mcp_oauth.access_token encrypted."""
    from app.config import config

    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-32bytes-long!!!!", raising=False)
    monkeypatch.setattr(
        config,
        "E2E_PROVIDER_ENV",
        {
            "linear": {
                "access_token": "lin_oauth_fake",
                "refresh_token": "lin_refresh",
                "client_id": "e2e-client-id",
                "client_secret": "e2e-client-secret",
                "token_endpoint": "https://api.linear.app/oauth/token",
                "organization_name": "E2E Org",
                "organization_url_key": "e2e-org",
            }
        },
        raising=False,
    )

    fake_session = _FakeSession(results=[_FakeResult(value=None)])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "linear", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 200, res.text
    row = fake_session.added[0]
    assert row.connector_type == SearchSourceConnectorType.LINEAR_CONNECTOR
    cfg = row.config
    assert cfg["mcp_service"] == "linear"
    assert cfg["server_config"]["url"] == "https://mcp.linear.app/mcp"
    assert cfg["mcp_oauth"]["access_token"] != "lin_oauth_fake"  # encrypted
    assert cfg["mcp_oauth"]["refresh_token"] != "lin_refresh"  # encrypted
    assert cfg["_token_encrypted"] is True


def test_provision_disabled_means_route_absent() -> None:
    """``E2E_PROVISION_ENABLED`` unset → aggregate ``app.routes.router`` has no
    ``/__e2e__/connectors/provision`` path. This is the prod safety guarantee.

    We drive the *real* mount gate in a subprocess so the test reflects the
    actual import-time ``if config.E2E_PROVISION_ENABLED:`` branch — not a
    re-implementation inside the test body.
    """
    import os
    import subprocess
    import sys

    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    # Flag off — route must be absent.
    env_off = dict(os.environ)
    env_off.pop("E2E_PROVISION_ENABLED", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.routes import router; "
            "import sys; sys.exit(0 if any("
            "getattr(r, 'path', '') == '/__e2e__/connectors/provision' "
            "for r in router.routes) else 1)",
        ],
        cwd=backend_root,
        env=env_off,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 1, (
        "route should be absent when E2E_PROVISION_ENABLED unset; "
        f"stderr={proc.stderr.decode()[-400:]}"
    )

    # Flag on — route must be present.
    env_on = dict(os.environ)
    env_on["E2E_PROVISION_ENABLED"] = "TRUE"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.routes import router; "
            "import sys; sys.exit(0 if any("
            "getattr(r, 'path', '') == '/__e2e__/connectors/provision' "
            "for r in router.routes) else 1)",
        ],
        cwd=backend_root,
        env=env_on,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        "route should be mounted when E2E_PROVISION_ENABLED=TRUE; "
        f"stderr={proc.stderr.decode()[-400:]}"
    )


def test_response_never_contains_plaintext_secret(app: FastAPI, monkeypatch) -> None:
    """Defense-in-depth: response body must not contain the raw secret."""
    from app.config import config

    secret_marker = "xoxb-SECRET-DO-NOT-LEAK-12345"
    monkeypatch.setattr(config, "E2E_PROVISION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-32bytes-long!!!!", raising=False)
    monkeypatch.setattr(
        config,
        "E2E_PROVIDER_ENV",
        {
            "slack": {
                "bot_token": secret_marker,
                "refresh_token": None,
                "bot_user_id": "U1",
                "team_id": "T1",
                "team_name": "E2E",
            }
        },
        raising=False,
    )

    fake_session = _FakeSession(results=[_FakeResult(value=None)])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.post(
        "/__e2e__/connectors/provision",
        json={"connector": "slack", "workspace_id": 15},
        headers={"x-playwright-test": "true"},
    )
    assert res.status_code == 200
    assert secret_marker not in res.text
    assert secret_marker not in res.content.decode("utf-8", errors="replace")
