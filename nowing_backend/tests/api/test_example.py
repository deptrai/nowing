"""
Example API test — Health check endpoint.

Demonstrates:
  - pytest + httpx pattern
  - Given/When/Then format
  - pytest.mark usage
"""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
async def test_health_check(api_client: AsyncClient) -> None:
    """
    Given the app is running
    When GET /health is called
    Then it returns 200 with status ok
    """
    # When
    response = await api_client.get("/health")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


@pytest.mark.integration
async def test_authenticated_endpoint(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """
    Given a valid auth token
    When GET /api/me is called
    Then it returns the current user profile
    """
    # When
    response = await api_client.get("/api/me", headers=auth_headers)

    # Then
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "email" in data


@pytest.mark.unit
async def test_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """
    Given no auth token
    When GET /api/me is called
    Then it returns 401 Unauthorized
    """
    # When
    response = await api_client.get("/api/me")

    # Then
    assert response.status_code == 401
