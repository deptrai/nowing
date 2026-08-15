"""Integration tests for Lark Base (Bitable) Cloud Connector (Story 21.13)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.lark_base import LarkBaseConnector

pytestmark = (
    pytest.mark.unit
)  # mark as unit/mocked network so it can run fast without external API keys


@respx.mock
@pytest.mark.asyncio
async def test_lark_base_batch_create_records_success():
    app_token = "app_token_12345"
    table_id = "tbl_67890"

    mock_route = respx.post(
        f"https://open.larksuite.com/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "success",
                "data": {
                    "records": [
                        {"record_id": "rec_001"},
                        {"record_id": "rec_002"},
                    ]
                },
            },
        )
    )

    records = [
        {"fields": {"Company Name": "VNG", "Fit Score": 95}},
        {"fields": {"Company Name": "FPT", "Fit Score": 88}},
    ]

    connector = LarkBaseConnector(tenant_access_token="test_tenant_token")
    result = await connector.batch_create_records(
        app_token=app_token,
        table_id=table_id,
        records=records,
        sync_id="test-sync-001",
    )

    assert mock_route.called
    assert result["success"] is True
    assert result["created_count"] == 2
    assert result["record_ids"] == ["rec_001", "rec_002"]
    assert (
        f"https://open.larksuite.com/bitable/{app_token}?table={table_id}"
        in result["app_url"]
    )


@respx.mock
@pytest.mark.asyncio
async def test_lark_base_batch_create_chunking():
    app_token = "app_token_12345"
    table_id = "tbl_67890"

    mock_route = respx.post(
        f"https://open.larksuite.com/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "success",
                "data": {"records": [{"record_id": f"rec_{i}"} for i in range(10)]},
            },
        )
    )

    # 15 records with chunk_size 10 -> 2 API calls
    records = [{"fields": {"Company Name": f"Co {i}"}} for i in range(15)]

    connector = LarkBaseConnector(tenant_access_token="test_tenant_token")
    result = await connector.batch_create_records(
        app_token=app_token,
        table_id=table_id,
        records=records,
        sync_id="test-chunk-sync",
        chunk_size=10,
    )

    assert mock_route.call_count == 2
    assert result["success"] is True
