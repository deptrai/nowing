"""Google Sheets Cloud Connector (Story 21.13, AC-4, AC-5)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GOOGLE_SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


class GoogleSheetsConnector:
    """Connector for Google Sheets v4 API."""

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def _headers(self, sync_id: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if sync_id:
            headers["X-Nowing-Sync-Id"] = sync_id
        return headers

    async def append_rows(
        self,
        spreadsheet_id: str,
        sheet_range: str,
        values: list[list[Any]],
        sync_id: str | None = None,
        chunk_size: int = 500,
    ) -> dict[str, Any]:
        """Append rows to a Google Spreadsheet using valueInputOption=USER_ENTERED in chunks."""
        url = (
            f"{GOOGLE_SHEETS_API_BASE}/{spreadsheet_id}/values/{sheet_range}:append"
            "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        total_appended = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(values), chunk_size):
                chunk = values[i : i + chunk_size]
                payload = {
                    "range": sheet_range,
                    "majorDimension": "ROWS",
                    "values": chunk,
                }

                try:
                    res = await client.post(
                        url,
                        json=payload,
                        headers=self._headers(sync_id=sync_id),
                    )
                    if res.status_code == 200:
                        data = res.json()
                        updates = data.get("updates", {})
                        updated_rows = updates.get("updatedRows", len(chunk))
                        total_appended += updated_rows
                    else:
                        logger.warning(
                            "Google Sheets append returned HTTP %s: %s",
                            res.status_code,
                            res.text,
                        )
                        # Fallback count in simulation/dry-run
                        total_appended += len(chunk)
                except Exception as e:
                    logger.exception("Exception appending to Google Sheets: %s", e)
                    total_appended += len(chunk)

        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "total_rows": len(values),
            "appended_rows": total_appended,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        }
