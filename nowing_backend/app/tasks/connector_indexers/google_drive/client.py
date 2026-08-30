"""Google Drive client facade and connector client factory."""

from __future__ import annotations

import base64
import logging
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.google_drive import GoogleDriveClient
from app.services.composio_service import ComposioService
from app.utils.google_credentials import COMPOSIO_GOOGLE_CONNECTOR_TYPES

logger = logging.getLogger(__name__)


class ComposioDriveClient:
    """Google Drive client facade backed by Composio tool execution.

    Composio-managed OAuth connections can execute tools without exposing raw
    OAuth tokens through connected account state.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        connected_account_id: str,
        entity_id: str,
    ):
        self.session = session
        self.connector_id = connector_id
        self.connected_account_id = connected_account_id
        self.entity_id = entity_id
        self.composio = ComposioService()

    async def list_files(
        self,
        query: str = "",
        fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum, size, webViewLink, parents, owners, createdTime, description)",
        page_size: int = 100,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        params: dict[str, Any] = {
            "page_size": min(page_size, 100),
            "fields": fields,
        }
        if query:
            params["q"] = query
        if page_token:
            params["page_token"] = page_token

        result = await self.composio.execute_tool(
            connected_account_id=self.connected_account_id,
            tool_name="GOOGLEDRIVE_LIST_FILES",
            params=params,
            entity_id=self.entity_id,
        )
        if not result.get("success"):
            return [], None, result.get("error", "Unknown error")

        data = result.get("data", {})
        files = []
        next_token = None
        if isinstance(data, dict):
            inner_data = data.get("data", data)
            if isinstance(inner_data, dict):
                files = inner_data.get("files", [])
                next_token = inner_data.get("nextPageToken") or inner_data.get(
                    "next_page_token"
                )
        elif isinstance(data, list):
            files = data

        return files, next_token, None

    async def get_file_metadata(
        self, file_id: str, fields: str = "*"
    ) -> tuple[dict[str, Any] | None, str | None]:
        result = await self.composio.execute_tool(
            connected_account_id=self.connected_account_id,
            tool_name="GOOGLEDRIVE_GET_FILE_METADATA",
            params={"file_id": file_id, "fields": fields},
            entity_id=self.entity_id,
        )
        if not result.get("success"):
            return None, result.get("error", "Unknown error")

        data = result.get("data", {})
        if isinstance(data, dict):
            inner_data = data.get("data", data)
            if isinstance(inner_data, dict):
                return inner_data, None

        return None, "Could not extract metadata from Composio response"

    async def download_file(self, file_id: str) -> tuple[bytes | None, str | None]:
        return await self._download_file_content(file_id)

    async def download_file_to_disk(
        self,
        file_id: str,
        dest_path: str,
        chunksize: int = 5 * 1024 * 1024,
    ) -> str | None:
        del chunksize
        content, error = await self.download_file(file_id)
        if error:
            return error
        if content is None:
            return "No content returned from Composio"
        Path(dest_path).write_bytes(content)
        return None

    async def export_google_file(
        self, file_id: str, mime_type: str
    ) -> tuple[bytes | None, str | None]:
        return await self._download_file_content(file_id, mime_type=mime_type)

    async def _download_file_content(
        self, file_id: str, mime_type: str | None = None
    ) -> tuple[bytes | None, str | None]:
        params: dict[str, Any] = {"file_id": file_id}
        if mime_type:
            params["mime_type"] = mime_type

        result = await self.composio.execute_tool(
            connected_account_id=self.connected_account_id,
            tool_name="GOOGLEDRIVE_DOWNLOAD_FILE",
            params=params,
            entity_id=self.entity_id,
        )
        if not result.get("success"):
            return None, result.get("error", "Unknown error")

        return self._read_download_result(result.get("data"))

    def _read_download_result(self, data: Any) -> tuple[bytes | None, str | None]:
        if isinstance(data, bytes):
            return data, None

        file_path: str | None = None
        if isinstance(data, str):
            file_path = data
        elif isinstance(data, dict):
            inner_data = data.get("data", data)
            if isinstance(inner_data, dict):
                for key in ("file_path", "downloaded_file_content", "path", "uri"):
                    value = inner_data.get(key)
                    if isinstance(value, str):
                        file_path = value
                        break
                    if isinstance(value, dict):
                        nested = (
                            value.get("file_path")
                            or value.get("downloaded_file_content")
                            or value.get("path")
                            or value.get("uri")
                            or value.get("s3url")
                        )
                        if isinstance(nested, str):
                            file_path = nested
                            break

        if not file_path:
            return None, "No file path/content returned from Composio"

        if file_path.startswith(("http://", "https://")):
            try:
                with urllib.request.urlopen(file_path, timeout=60) as response:
                    return response.read(), None
            except Exception as e:
                return None, f"Failed to download Composio file URL: {e!s}"

        path_obj = Path(file_path)
        if path_obj.is_absolute() or ".composio" in str(path_obj):
            if not path_obj.exists():
                return None, f"File not found at path: {file_path}"
            return path_obj.read_bytes(), None

        try:
            return base64.b64decode(file_path), None
        except Exception:
            return file_path.encode("utf-8"), None


async def _build_drive_client_for_connector(
    session: AsyncSession,
    connector_id: int,
    connector: object,
    user_id: str,
) -> tuple[GoogleDriveClient | ComposioDriveClient | None, str | None]:
    if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
        connected_account_id = connector.config.get("composio_connected_account_id")
        if not connected_account_id:
            return None, (
                f"Composio connected_account_id not found for connector {connector_id}"
            )
        return (
            ComposioDriveClient(
                session,
                connector_id,
                connected_account_id,
                entity_id=f"nowing_{user_id}",
            ),
            None,
        )

    token_encrypted = connector.config.get("_token_encrypted", False)
    if token_encrypted and not config.SECRET_KEY:
        return None, "SECRET_KEY not configured but credentials are marked as encrypted"

    return GoogleDriveClient(session, connector_id), None
