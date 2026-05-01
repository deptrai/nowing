"""Unit tests for crypto_data_routes — AC1 through AC7 + F1 auth patch."""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.app import app
from app.db import (
    CryptoDataSnapshot,
    CryptoProject,
    SearchSpaceCryptoWatchlist,
    User,
    get_async_session,
)
from app.users import current_active_user

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(id=1, project_id="ethereum", symbol="ETH", name="Ethereum",
                  coingecko_id="ethereum", defillama_slug="ethereum"):
    p = MagicMock()
    p.id = id
    p.project_id = project_id
    p.symbol = symbol
    p.name = name
    p.coingecko_id = coingecko_id
    p.defillama_slug = defillama_slug
    return p


def _make_watchlist_entry(project_id=1, search_space_id=42, pin_order=None):
    w = MagicMock()
    w.project_id = project_id
    w.search_space_id = search_space_id
    w.added_at = datetime(2026, 4, 1, tzinfo=UTC)
    w.pin_order = pin_order
    return w


def _make_snapshot(id=1, project_id=1, data_category="price_realtime",
                   tool_name="get_live_token_price", api_source="dexscreener",
                   is_error=False, fetched_at=None):
    s = MagicMock()
    s.id = id
    s.project_id = project_id
    s.data_category = data_category
    s.tool_name = tool_name
    s.api_source = api_source
    s.fetched_at = fetched_at or datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    s.expires_at = s.fetched_at + timedelta(minutes=5)
    s.data = {"price": 3000.0}
    s.is_error = is_error
    return s


def _make_mock_user():
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    return user


def _make_session_with_single_result(result):
    mock_session = MagicMock()

    async def _execute(*a, **kw):
        return result

    mock_session.execute = _execute
    return mock_session


def _make_session_with_results(*results):
    mock_session = MagicMock()
    _calls = iter(results)

    async def _execute(*a, **kw):
        return next(_calls)

    mock_session.execute = _execute
    return mock_session


def _access_granted_result():
    """Result for _verify_project_access that grants access (scalar returns non-None)."""
    r = MagicMock()
    r.scalar.return_value = 1
    return r


def _access_denied_result():
    """Result for _verify_project_access that denies access (scalar returns None)."""
    r = MagicMock()
    r.scalar.return_value = None
    return r


# ---------------------------------------------------------------------------
# AC1: Watchlist returns tracked projects
# ---------------------------------------------------------------------------


def test_ac1_watchlist_returns_tracked_projects():
    """GET /api/v1/crypto/workspaces/42/watchlist returns workspace projects."""
    project = _make_project()
    watchlist_entry = _make_watchlist_entry()

    fetch_result = MagicMock()
    fetch_result.fetchall.return_value = [(project, watchlist_entry)]
    mock_session = _make_session_with_single_result(fetch_result)
    mock_user = _make_mock_user()

    async def _allow(*a, **kw):
        return MagicMock()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        with patch("app.routes.crypto_data_routes.check_search_space_access", new=_allow):
            client = TestClient(app)
            response = client.get("/api/v1/crypto/workspaces/42/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "ETH"
    assert data[0]["name"] == "Ethereum"
    assert data[0]["coingecko_id"] == "ethereum"
    assert "added_at" in data[0]


# ---------------------------------------------------------------------------
# AC2: Watchlist returns 403 for non-member
# ---------------------------------------------------------------------------


def test_ac2_watchlist_403_for_non_member():
    """GET /api/v1/crypto/workspaces/42/watchlist returns 403 for non-member."""
    mock_session = _make_session_with_single_result(MagicMock())
    mock_user = _make_mock_user()

    async def _deny(*a, **kw):
        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        with patch("app.routes.crypto_data_routes.check_search_space_access", new=_deny):
            client = TestClient(app)
            response = client.get("/api/v1/crypto/workspaces/42/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC2b: Timeline returns 403 when project not in any user workspace (F1 patch)
# ---------------------------------------------------------------------------


def test_ac2b_timeline_403_for_unauthorized_project():
    """GET /api/v1/crypto/projects/1/timeline returns 403 when user has no access."""
    mock_session = _make_session_with_single_result(_access_denied_result())
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC3: Timeline basic query — up to 100 snapshots, newest first
# ---------------------------------------------------------------------------


def test_ac3_timeline_basic_query():
    """GET /api/v1/crypto/projects/1/timeline returns snapshots newest first."""
    snapshots = [_make_snapshot(id=i) for i in range(1, 6)]

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = snapshots
    count_result = MagicMock()
    count_result.scalar.return_value = 5

    # execute calls: 1) _verify_project_access, 2) fetch snapshots, 3) count
    mock_session = _make_session_with_results(_access_granted_result(), snap_result, count_result)
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["next_cursor"] is None
    assert len(data["items"]) == 5


# ---------------------------------------------------------------------------
# AC4: Timeline category filter
# ---------------------------------------------------------------------------


def test_ac4_timeline_category_filter():
    """GET /api/v1/crypto/projects/1/timeline?category=defi_tvl filters by category."""
    snapshot = _make_snapshot(id=1, data_category="defi_tvl", tool_name="get_defillama_protocol")

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snapshot]
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    mock_session = _make_session_with_results(_access_granted_result(), snap_result, count_result)
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline?category=defi_tvl")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["data_category"] == "defi_tvl"


# ---------------------------------------------------------------------------
# AC5: Timeline cursor pagination
# ---------------------------------------------------------------------------


def test_ac5_timeline_cursor_pagination():
    """Timeline returns next_cursor when more items exist (101 returned → cursor set)."""
    snapshots = [_make_snapshot(id=i) for i in range(1, 102)]  # 101 items

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = snapshots
    count_result = MagicMock()
    count_result.scalar.return_value = 250

    mock_session = _make_session_with_results(_access_granted_result(), snap_result, count_result)
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline?limit=100")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 100
    assert data["next_cursor"] == snapshots[99].id
    assert data["total"] == 250


# ---------------------------------------------------------------------------
# AC6: Timeline since filter
# ---------------------------------------------------------------------------


def test_ac6_timeline_since_filter():
    """GET /api/v1/crypto/projects/1/timeline?since=... filters by date."""
    snapshot = _make_snapshot(id=1, fetched_at=datetime(2026, 4, 2, tzinfo=UTC))

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snapshot]
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    mock_session = _make_session_with_results(_access_granted_result(), snap_result, count_result)
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline?since=2026-04-01T00:00:00Z")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# AC7: Error snapshots excluded
# ---------------------------------------------------------------------------


def test_ac7_error_snapshots_excluded():
    """Timeline does not include is_error=True snapshots (filtered by WHERE clause)."""
    snapshots = [_make_snapshot(id=1, is_error=False)]

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = snapshots
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    mock_session = _make_session_with_results(_access_granted_result(), snap_result, count_result)
    mock_user = _make_mock_user()

    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/crypto/projects/1/timeline")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["is_error"] is False
