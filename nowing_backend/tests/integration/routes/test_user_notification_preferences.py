"""Integration tests for the user notification-preferences endpoint."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_patch_notification_preferences_merges_and_persists(
    client_as_regular_user,
) -> None:
    response = await client_as_regular_user.patch(
        "/users/me/notification-preferences",
        json={
            "notification_preferences": {"automation_run_complete": {"telegram": True}}
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert (
        data["notification_preferences"]["automation_run_complete"]["telegram"] is True
    )

    # A second patch with a different top-level key should deep-merge.
    response = await client_as_regular_user.patch(
        "/users/me/notification-preferences",
        json={"notification_preferences": {"connector_indexing": {"telegram": False}}},
    )
    assert response.status_code == 200
    data = response.json()
    prefs = data["notification_preferences"]
    assert prefs["automation_run_complete"]["telegram"] is True
    assert prefs["connector_indexing"]["telegram"] is False


async def test_get_current_user_includes_notification_preferences(
    client_as_regular_user,
) -> None:
    await client_as_regular_user.patch(
        "/users/me/notification-preferences",
        json={
            "notification_preferences": {"automation_run_complete": {"telegram": True}}
        },
    )
    response = await client_as_regular_user.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert (
        data["notification_preferences"]["automation_run_complete"]["telegram"] is True
    )


async def test_patch_users_me_with_null_notification_preferences_defaults_to_empty(
    client_as_regular_user,
) -> None:
    response = await client_as_regular_user.patch(
        "/users/me",
        json={"notification_preferences": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notification_preferences"] == {}
