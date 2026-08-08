"""Integration tests for platform-admin global model connection routes."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.config import config
from app.db import Connection, Model
from app.routes import admin_global_model_connections_routes
from app.services.auto_model_pin_service import auto_model_candidates
from app.services.model_connection_service import VerifyResult

pytestmark = pytest.mark.integration


def _restore_global_catalog(
    original_connections: list[dict[str, Any]],
    original_models: list[dict[str, Any]],
) -> None:
    config.GLOBAL_CONNECTIONS = original_connections
    config.GLOBAL_MODELS = original_models


@pytest.fixture
def _patched_admin_model_service(monkeypatch):
    """Avoid real provider network calls during admin discover/test flows."""

    async def _fake_discover(conn: Connection) -> list[dict[str, Any]]:
        del conn
        return [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "supports_image_input": False,
                "supports_tools": False,
                "supports_image_generation": False,
                "max_input_tokens": 128_000,
                "metadata": {},
            }
        ]

    async def _fake_test(conn: Connection, model: Model) -> VerifyResult:
        del conn, model
        return VerifyResult("OK", True, "Model responded")

    monkeypatch.setattr(
        admin_global_model_connections_routes, "discover_models", _fake_discover
    )
    monkeypatch.setattr(admin_global_model_connections_routes, "test_model", _fake_test)


@pytest.fixture
def _clean_catalog():
    original_connections = list(config.GLOBAL_CONNECTIONS)
    original_models = list(config.GLOBAL_MODELS)
    try:
        yield
    finally:
        _restore_global_catalog(original_connections, original_models)


async def test_admin_routes_reject_regular_user(client_as_regular_user):
    response = await client_as_regular_user.get(
        "/api/v1/admin/global-model-connections"
    )
    assert response.status_code == 403


async def test_admin_routes_reject_pat(pat_client):
    response = await pat_client.get("/api/v1/admin/global-model-connections")
    assert response.status_code == 403


async def test_admin_create_and_list_managed_connection(
    admin_client,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "extra": {"litellm_params": {"temperature": 0.5}},
        "enabled": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
                "pricing": {
                    "cost_per_1k_input_tokens": 0.002,
                    "cost_per_1k_output_tokens": 0.008,
                    "rpm": 1000,
                    "tpm": 100000,
                },
            }
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["provider"] == "openai"
    assert created["source"] == "managed"
    assert created["can_edit"] is True
    assert created["can_delete"] is True
    assert created["has_api_key"] is True
    assert created["api_key"] is None
    assert len(created["models"]) == 1
    assert created["models"][0]["model_id"] == "gpt-4o-mini"
    assert created["models"][0]["source"] == "managed"
    assert created["models"][0]["cost_per_1k_input_tokens"] == 0.002

    # The in-memory global catalog should reflect the new DB row.
    assert any(
        m.get("model_id") == "gpt-4o-mini"
        and m.get("catalog", {}).get("admin_source") == "managed"
        for m in config.GLOBAL_MODELS
    )

    list_response = await admin_client.get("/api/v1/admin/global-model-connections")
    assert list_response.status_code == 200
    connections = list_response.json()
    managed = [c for c in connections if c["source"] == "managed"]
    assert len(managed) == 1


async def test_admin_update_and_delete_managed_connection(
    admin_client,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
                "pricing": {
                    "cost_per_1k_input_tokens": 0.002,
                },
            }
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201
    created = create_response.json()
    connection_id = created["id"]

    update_response = await admin_client.put(
        f"/api/v1/admin/global-model-connections/{connection_id}",
        json={"base_url": "http://localhost:5678"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["base_url"] == "http://localhost:5678"

    model_id = created["models"][0]["id"]
    model_update_response = await admin_client.put(
        f"/api/v1/admin/global-model-connections/models/{model_id}",
        json={"enabled": False},
    )
    assert model_update_response.status_code == 200
    updated_model = model_update_response.json()
    assert updated_model["enabled"] is False

    # The disabled model should leave the in-memory global catalog.
    assert not any(
        m.get("model_id") == "gpt-4o-mini" and m.get("enabled") is True
        for m in config.GLOBAL_MODELS
    )

    delete_response = await admin_client.delete(
        f"/api/v1/admin/global-model-connections/{connection_id}"
    )
    assert delete_response.status_code == 204

    list_after_delete = await admin_client.get("/api/v1/admin/global-model-connections")
    assert list_after_delete.status_code == 200
    connections = list_after_delete.json()
    managed = [c for c in connections if c["source"] == "managed"]
    assert len(managed) == 0


async def test_admin_discover_and_test_preview(
    admin_client,
    _patched_admin_model_service,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [],
    }
    discover_response = await admin_client.post(
        "/api/v1/admin/global-model-connections/discover-preview", json=payload
    )
    assert discover_response.status_code == 200
    models = discover_response.json()
    assert len(models) == 1
    assert models[0]["model_id"] == "gpt-4o-mini"

    test_response = await admin_client.post(
        "/api/v1/admin/global-model-connections/test-preview",
        json={**payload, "model_id": "gpt-4o-mini"},
    )
    assert test_response.status_code == 200
    result = test_response.json()
    assert result["ok"] is True


async def test_admin_discover_and_test_saved_model(
    admin_client,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
            }
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201
    connection_id = create_response.json()["id"]

    discover_response = await admin_client.post(
        f"/api/v1/admin/global-model-connections/{connection_id}/discover"
    )
    assert discover_response.status_code == 200
    models = discover_response.json()
    assert any(m["model_id"] == "gpt-4o-mini" for m in models)

    test_response = await admin_client.post(
        f"/api/v1/admin/global-model-connections/{connection_id}/test",
        json={"model_id": "gpt-4o-mini"},
    )
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True


async def test_admin_bulk_update_models(
    admin_client,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [
            {
                "model_id": "model-a",
                "display_name": "Model A",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
            },
            {
                "model_id": "model-b",
                "display_name": "Model B",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
            },
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201
    connection_id = create_response.json()["id"]
    model_ids = [m["id"] for m in create_response.json()["models"]]

    bulk_response = await admin_client.patch(
        f"/api/v1/admin/global-model-connections/{connection_id}/models",
        json={"model_ids": model_ids, "enabled": False},
    )
    assert bulk_response.status_code == 200
    updated = bulk_response.json()
    assert all(m["enabled"] is False for m in updated["models"])


async def test_admin_managed_global_model_appears_in_auto_mode(
    admin_client,
    db_session,
    db_superuser,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
            }
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201

    candidates = await auto_model_candidates(
        db_session,
        workspace_id=1,
        user_id=str(db_superuser.id),
        capability="chat",
    )
    managed = [c for c in candidates if c["model_id"] == "gpt-4o-mini"]
    assert len(managed) == 1
    assert managed[0]["source"] == "global"
    assert managed[0]["billing_tier"] == "free"


async def test_admin_managed_global_model_pricing_normalized(
    admin_client,
    _patched_admin_model_service,
    _clean_catalog,
):
    payload = {
        "provider": "openai",
        "base_url": "http://localhost:1234",
        "api_key": "sk-test",
        "enabled": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "supports_chat": True,
                "enabled": True,
                "billing_tier": "free",
                "pricing": {
                    "cost_per_1k_input_tokens": 0.002,
                    "cost_per_1k_output_tokens": 0.008,
                },
            }
        ],
    }
    create_response = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=payload
    )
    assert create_response.status_code == 201

    catalog = next(
        (
            m.get("catalog", {})
            for m in config.GLOBAL_MODELS
            if m.get("model_id") == "gpt-4o-mini"
        ),
        {},
    )
    assert catalog.get("input_cost_per_token") == 2e-6
    assert catalog.get("output_cost_per_token") == 8e-6


# ---------------------------------------------------------------------------
# AC-5: Non-superuser 403 on all write routes
# ---------------------------------------------------------------------------

_BASE_PAYLOAD = {
    "provider": "openai",
    "base_url": "http://localhost:1234",
    "api_key": "sk-test",
    "enabled": True,
    "models": [
        {
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "supports_chat": True,
            "enabled": True,
            "billing_tier": "free",
        }
    ],
}


async def test_non_superuser_403_on_create(client_as_regular_user):
    resp = await client_as_regular_user.post(
        "/api/v1/admin/global-model-connections", json=_BASE_PAYLOAD
    )
    assert resp.status_code == 403


async def test_non_superuser_403_on_update(client_as_regular_user):
    resp = await client_as_regular_user.put(
        "/api/v1/admin/global-model-connections/1",
        json={"base_url": "http://localhost:5678"},
    )
    assert resp.status_code == 403


async def test_non_superuser_403_on_delete(client_as_regular_user):
    resp = await client_as_regular_user.delete(
        "/api/v1/admin/global-model-connections/1"
    )
    assert resp.status_code == 403


async def test_non_superuser_403_on_discover_preview(client_as_regular_user):
    resp = await client_as_regular_user.post(
        "/api/v1/admin/global-model-connections/discover-preview",
        json=_BASE_PAYLOAD,
    )
    assert resp.status_code == 403


async def test_non_superuser_403_on_test_preview(client_as_regular_user):
    resp = await client_as_regular_user.post(
        "/api/v1/admin/global-model-connections/test-preview",
        json={**_BASE_PAYLOAD, "model_id": "gpt-4o-mini"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC-11: _log_admin_action audit log entries
# ---------------------------------------------------------------------------


def _assert_admin_log_entry(record: logging.LogRecord, action: str) -> None:
    """Assert a log record from _log_admin_action has the required fields."""
    msg = record.getMessage()
    assert "actor=" in msg
    assert f"action={action}" in msg
    assert "source=managed" in msg
    assert "success=" in msg


async def test_audit_log_on_create(
    admin_client, _patched_admin_model_service, _clean_catalog, caplog
):
    caplog.set_level(
        logging.INFO,
        logger=admin_global_model_connections_routes.logger.name,
    )
    resp = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=_BASE_PAYLOAD
    )
    assert resp.status_code == 201
    create_records = [
        r
        for r in caplog.records
        if r.name == admin_global_model_connections_routes.logger.name
        and "action=create" in r.getMessage()
    ]
    assert len(create_records) == 1
    _assert_admin_log_entry(create_records[0], "create")


async def test_audit_log_on_update(
    admin_client, _patched_admin_model_service, _clean_catalog, caplog
):
    create_resp = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=_BASE_PAYLOAD
    )
    assert create_resp.status_code == 201
    connection_id = create_resp.json()["id"]

    caplog.clear()
    caplog.set_level(
        logging.INFO,
        logger=admin_global_model_connections_routes.logger.name,
    )
    resp = await admin_client.put(
        f"/api/v1/admin/global-model-connections/{connection_id}",
        json={"base_url": "http://localhost:5678"},
    )
    assert resp.status_code == 200
    update_records = [
        r
        for r in caplog.records
        if r.name == admin_global_model_connections_routes.logger.name
        and "action=update" in r.getMessage()
    ]
    assert len(update_records) == 1
    _assert_admin_log_entry(update_records[0], "update")


async def test_audit_log_on_delete(
    admin_client, _patched_admin_model_service, _clean_catalog, caplog
):
    create_resp = await admin_client.post(
        "/api/v1/admin/global-model-connections", json=_BASE_PAYLOAD
    )
    assert create_resp.status_code == 201
    connection_id = create_resp.json()["id"]

    caplog.clear()
    caplog.set_level(
        logging.INFO,
        logger=admin_global_model_connections_routes.logger.name,
    )
    resp = await admin_client.delete(
        f"/api/v1/admin/global-model-connections/{connection_id}"
    )
    assert resp.status_code == 204
    delete_records = [
        r
        for r in caplog.records
        if r.name == admin_global_model_connections_routes.logger.name
        and "action=delete" in r.getMessage()
    ]
    assert len(delete_records) == 1
    _assert_admin_log_entry(delete_records[0], "delete")
