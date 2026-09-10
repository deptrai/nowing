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


async def test_patch_notification_preferences_merges_with_latest_db_state(
    client_as_regular_user,
    db_session,
    db_user,
) -> None:
    # Update DB directly so cached auth.user in memory is stale
    db_user.notification_preferences = {"channel_a": {"email": True}}
    db_session.add(db_user)
    await db_session.commit()
    await db_session.refresh(db_user)

    # Patch with channel_b - should lock DB row, fetch channel_a, and merge both
    res = await client_as_regular_user.patch(
        "/users/me/notification-preferences",
        json={
            "notification_preferences": {
                "channel_b": {"in_app": True}
            }
        },
    )
    assert res.status_code == 200
    prefs = res.json()["notification_preferences"]
    assert prefs["channel_a"]["email"] is True
    assert prefs["channel_b"]["in_app"] is True


async def test_patch_users_me_deep_merges_notification_preferences(
    client_as_regular_user,
    db_session,
    db_user,
) -> None:
    # Seed channel_a directly in the database (simulates a prior update from
    # another session that hasn't been merged into the cached auth.user).
    db_user.notification_preferences = {"channel_a": {"email": True}}
    db_session.add(db_user)
    await db_session.commit()

    # PATCH /users/me should deep-merge channel_b on top of channel_a.
    res = await client_as_regular_user.patch(
        "/users/me",
        json={
            "notification_preferences": {
                "channel_b": {"in_app": True}
            }
        },
    )
    assert res.status_code == 200
    prefs = res.json()["notification_preferences"]
    assert prefs["channel_a"]["email"] is True
    assert prefs["channel_b"]["in_app"] is True


async def test_patch_users_me_without_notification_preferences_unchanged(
    client_as_regular_user,
    db_session,
    db_user,
) -> None:
    db_user.notification_preferences = {"channel_a": {"email": True}}
    db_session.add(db_user)
    await db_session.commit()

    res = await client_as_regular_user.patch(
        "/users/me",
        json={"display_name": "Updated Name"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["display_name"] == "Updated Name"
    assert data["notification_preferences"]["channel_a"]["email"] is True
