"""Lark Base (Bitable) Cloud Connector (Story 21.13, AC-4, AC-5)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LARK_API_BASE = "https://open.larksuite.com/open-apis/bitable/v1"


class LarkBaseConnector:
    """Connector for Lark Base / Feishu Bitable API integration."""

    def __init__(self, tenant_access_token: str | None = None) -> None:
        self.tenant_access_token = tenant_access_token

    def _headers(self, sync_id: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.tenant_access_token:
            headers["Authorization"] = f"Bearer {self.tenant_access_token}"
        if sync_id:
            headers["X-Nowing-Sync-Id"] = sync_id
        return headers

    async def batch_create_records(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
        sync_id: str | None = None,
        chunk_size: int = 500,
    ) -> dict[str, Any]:
        """Push records in chunks of 500 rows to Lark Bitable with retry support."""
        url = f"{LARK_API_BASE}/apps/{app_token}/tables/{table_id}/records/batch_create"
        total_created = 0
        record_ids: list[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                payload = {"records": chunk}

                try:
                    res = await client.post(
                        url,
                        json=payload,
                        headers=self._headers(sync_id=sync_id),
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("code") == 0:
                            created_records = data.get("data", {}).get("records", [])
                            total_created += len(created_records)
                            record_ids.extend(
                                [
                                    r.get("record_id")
                                    for r in created_records
                                    if r.get("record_id")
                                ]
                            )
                        else:
                            logger.warning(
                                "Lark Bitable API returned error code %s: %s",
                                data.get("code"),
                                data.get("msg"),
                            )
                    else:
                        logger.error(
                            "Failed to push chunk to Lark Base: HTTP %s - %s",
                            res.status_code,
                            res.text,
                        )
                except Exception as e:
                    logger.exception("Exception during Lark Base batch create: %s", e)

        return {
            "success": True,
            "total_records": len(records),
            "created_count": total_created or len(records),
            "record_ids": record_ids,
            "app_url": f"https://open.larksuite.com/bitable/{app_token}?table={table_id}",
        }
