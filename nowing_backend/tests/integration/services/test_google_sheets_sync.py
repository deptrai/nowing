"""Integration tests for Google Sheets Cloud Connector (Story 21.13)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.google_sheets import GoogleSheetsConnector

pytestmark = pytest.mark.unit


@respx.mock
@pytest.mark.asyncio
async def test_google_sheets_append_rows_success():
    spreadsheet_id = "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    sheet_range = "Sheet1!A1"

    mock_route = respx.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_range}:append"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheetId": spreadsheet_id,
                "tableRange": "Sheet1!A1:D1",
                "updates": {
                    "spreadsheetId": spreadsheet_id,
                    "updatedRange": "Sheet1!A2:D3",
                    "updatedRows": 2,
                    "updatedColumns": 4,
                    "updatedCells": 8,
                },
            },
        )
    )

    values = [
        ["Company Name", "Fit Score", "Location", "Phone"],
        ["VNG Corporation", 95.0, "TP. Hồ Chí Minh", "0908123456"],
    ]

    connector = GoogleSheetsConnector(access_token="test_google_oauth_token")
    result = await connector.append_rows(
        spreadsheet_id=spreadsheet_id,
        sheet_range=sheet_range,
        values=values,
        sync_id="sync-gsheet-001",
    )

    assert mock_route.called
    assert result["success"] is True
    assert result["spreadsheet_id"] == spreadsheet_id
    assert result["appended_rows"] == 2
    assert (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        in result["spreadsheet_url"]
    )


@respx.mock
@pytest.mark.asyncio
async def test_google_sheets_append_rows_chunking():
    spreadsheet_id = "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    sheet_range = "Sheet1!A1"

    mock_route = respx.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_range}:append"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheetId": spreadsheet_id,
                "updates": {"updatedRows": 5},
            },
        )
    )

    # 12 rows with chunk size 5 -> 3 API calls
    values = [[f"Row {i}"] for i in range(12)]

    connector = GoogleSheetsConnector(access_token="test_google_oauth_token")
    result = await connector.append_rows(
        spreadsheet_id=spreadsheet_id,
        sheet_range=sheet_range,
        values=values,
        sync_id="sync-chunk-002",
        chunk_size=5,
    )

    assert mock_route.call_count == 3
    assert result["success"] is True
