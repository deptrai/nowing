"""Composio Google Drive toolkit operations."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from app.services.composio.base import ComposioClientMixin

logger = logging.getLogger(__name__)


class ComposioDriveMixin(ComposioClientMixin):
    """Google Drive operations via Composio tools."""

    async def get_drive_files(
        self,
        connected_account_id: str,
        entity_id: str,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """List files from Google Drive via Composio."""
        try:
            params = {
                "page_size": min(page_size, 100),
                "fields": "files(id,name,mimeType,modifiedTime,createdTime),nextPageToken",
            }
            if folder_id:
                params["q"] = (
                    f"'{folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.shortcut'"
                )
            else:
                params["q"] = (
                    "'root' in parents and trashed = false and mimeType != 'application/vnd.google-apps.shortcut'"
                )
            if page_token:
                params["page_token"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_LIST_FILES",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, result.get("error", "Unknown error")

            data = result.get("data", {})

            files = []
            next_token = None
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                response_data = (
                    inner_data.get("response_data", {})
                    if isinstance(inner_data, dict)
                    else {}
                )
                files = (
                    data.get("files", [])
                    or (
                        inner_data.get("files", [])
                        if isinstance(inner_data, dict)
                        else []
                    )
                    or response_data.get("files", [])
                )
                next_token = (
                    data.get("nextPageToken")
                    or data.get("next_page_token")
                    or (
                        inner_data.get("nextPageToken")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or (
                        inner_data.get("next_page_token")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or response_data.get("nextPageToken")
                    or response_data.get("next_page_token")
                )
            elif isinstance(data, list):
                files = data

            return files, next_token, None

        except Exception as e:
            logger.error(f"Failed to list Drive files: {e!s}")
            return [], None, str(e)

    async def get_drive_file_content(
        self,
        connected_account_id: str,
        entity_id: str,
        file_id: str,
        original_mime_type: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Download file content from Google Drive via Composio."""
        try:
            params = {"file_id": file_id}

            if original_mime_type and original_mime_type.startswith(
                "application/vnd.google-apps."
            ):
                params["mime_type"] = "application/pdf"

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_DOWNLOAD_FILE",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data")
            if not data:
                return None, "No data returned from Composio"

            file_path = None

            if isinstance(data, dict):
                inner_data = data
                if "data" in data and isinstance(data["data"], dict):
                    inner_data = data["data"]
                    logger.debug(
                        f"Found nested data structure. Inner keys: {list(inner_data.keys())}"
                    )
                elif "successful" in data and "data" in data:
                    inner_data = data["data"] if data["data"] else data

                file_path = (
                    inner_data.get("file_path")
                    or inner_data.get("downloaded_file_content")
                    or inner_data.get("path")
                    or inner_data.get("uri")
                )

                if isinstance(file_path, dict):
                    file_path = (
                        file_path.get("file_path")
                        or file_path.get("downloaded_file_content")
                        or file_path.get("path")
                        or file_path.get("uri")
                    )

                if not file_path and isinstance(inner_data, dict):
                    for key in ["downloaded_file_content", "file_path", "path", "uri"]:
                        if key in inner_data:
                            val = inner_data[key]
                            if isinstance(val, str):
                                file_path = val
                                break
                            elif isinstance(val, dict):
                                file_path = (
                                    val.get("file_path")
                                    or val.get("downloaded_file_content")
                                    or val.get("path")
                                    or val.get("uri")
                                )
                                if file_path:
                                    break

                logger.debug(
                    f"Composio response keys: {list(data.keys())}, inner keys: {list(inner_data.keys()) if isinstance(inner_data, dict) else 'N/A'}, extracted path: {file_path}"
                )
            elif isinstance(data, str):
                file_path = data
            elif isinstance(data, bytes):
                return data, None

            if file_path and isinstance(file_path, str):
                path_obj = Path(file_path)

                if path_obj.is_absolute() or ".composio" in str(path_obj):
                    try:
                        if path_obj.exists():
                            content = path_obj.read_bytes()
                            logger.info(
                                f"Successfully read {len(content)} bytes from Composio file: {file_path}"
                            )
                            return content, None
                        else:
                            logger.warning(
                                f"File path from Composio does not exist: {file_path}"
                            )
                            return None, f"File not found at path: {file_path}"
                    except Exception as e:
                        logger.error(
                            f"Failed to read file from Composio path {file_path}: {e!s}"
                        )
                        return None, f"Failed to read file: {e!s}"
                else:
                    try:
                        content = base64.b64decode(file_path)
                        return content, None
                    except Exception:
                        return file_path.encode("utf-8"), None

            if isinstance(data, dict):
                inner_data = data.get("data", {})
                logger.warning(
                    f"Could not extract file path from Composio response. "
                    f"Top keys: {list(data.keys())}, "
                    f"Inner data keys: {list(inner_data.keys()) if isinstance(inner_data, dict) else type(inner_data).__name__}, "
                    f"Full inner data: {inner_data}"
                )
                return (
                    None,
                    f"No file path in Composio response. Keys: {list(data.keys())}, inner: {list(inner_data.keys()) if isinstance(inner_data, dict) else 'N/A'}",
                )

            return None, f"Unexpected data type from Composio: {type(data).__name__}"

        except Exception as e:
            logger.error(f"Failed to get Drive file content: {e!s}")
            return None, str(e)

    async def get_file_metadata(
        self, connected_account_id: str, entity_id: str, file_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Get metadata for a specific file from Google Drive."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_GET_FILE_METADATA",
                params={
                    "file_id": file_id,
                    "fields": "id,name,mimeType,modifiedTime,createdTime,size",
                },
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data", {})

            if isinstance(data, dict):
                inner_data = data.get("data", data)
                if isinstance(inner_data, dict):
                    metadata = {
                        "id": inner_data.get("id") or file_id,
                        "name": inner_data.get("name", ""),
                        "mimeType": inner_data.get("mimeType")
                        or inner_data.get("mime_type", ""),
                        "modifiedTime": inner_data.get("modifiedTime")
                        or inner_data.get("modified_time", ""),
                        "createdTime": inner_data.get("createdTime")
                        or inner_data.get("created_time", ""),
                        "size": inner_data.get("size", ""),
                    }
                    return metadata, None

            return None, "Could not extract metadata from response"

        except Exception as e:
            logger.error(f"Failed to get file metadata: {e!s}")
            return None, str(e)

    async def get_drive_start_page_token(
        self, connected_account_id: str, entity_id: str
    ) -> tuple[str | None, str | None]:
        """Get the starting page token for Google Drive change tracking."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN",
                params={},
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data", {})
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                token = (
                    inner_data.get("startPageToken")
                    or inner_data.get("start_page_token")
                    or data.get("startPageToken")
                    or data.get("start_page_token")
                )
                if token:
                    logger.info(f"Got Drive start page token: {token}")
                    return token, None

            logger.warning(f"Could not extract start page token from response: {data}")
            return None, "No start page token in response"

        except Exception as e:
            logger.error(f"Failed to get Drive start page token: {e!s}")
            return None, str(e)

    async def list_drive_changes(
        self,
        connected_account_id: str,
        entity_id: str,
        page_token: str | None = None,
        page_size: int = 100,
        include_removed: bool = True,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """List changes in Google Drive since the given page token."""
        try:
            params = {
                "pageSize": min(page_size, 100),
                "includeRemoved": include_removed,
            }
            if page_token:
                params["pageToken"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_LIST_CHANGES",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, result.get("error", "Unknown error")

            data = result.get("data", {})

            changes = []
            new_start_token = None

            if isinstance(data, dict):
                inner_data = data.get("data", data)
                changes = inner_data.get("changes", []) or data.get("changes", [])

                new_start_token = (
                    inner_data.get("newStartPageToken")
                    or inner_data.get("new_start_page_token")
                    or inner_data.get("nextPageToken")
                    or inner_data.get("next_page_token")
                    or data.get("newStartPageToken")
                    or data.get("nextPageToken")
                )

            logger.info(
                f"Got {len(changes)} Drive changes, new token: {new_start_token[:20] if new_start_token else 'None'}..."
            )
            return changes, new_start_token, None

        except Exception as e:
            logger.error(f"Failed to list Drive changes: {e!s}")
            return [], None, str(e)

    @staticmethod
    def _drive_web_view_link(file_id: str, mime_type: str | None) -> str:
        """Synthesize a Google Drive webViewLink from id + mimeType."""
        if not file_id:
            return ""
        mt = (mime_type or "").lower()
        if mt == "application/vnd.google-apps.document":
            return f"https://docs.google.com/document/d/{file_id}/edit"
        if mt == "application/vnd.google-apps.spreadsheet":
            return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
        if mt == "application/vnd.google-apps.presentation":
            return f"https://docs.google.com/presentation/d/{file_id}/edit"
        if mt == "application/vnd.google-apps.folder":
            return f"https://drive.google.com/drive/folders/{file_id}"
        return f"https://drive.google.com/file/d/{file_id}/view"

    async def create_drive_file_from_text(
        self,
        connected_account_id: str,
        entity_id: str,
        name: str,
        mime_type: str,
        content: str | None = None,
        parent_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Create a Google Drive file from text via Composio."""
        try:
            params: dict[str, Any] = {
                "file_name": name,
                "mime_type": mime_type,
                "text_content": content if content is not None else "",
            }
            if parent_id:
                params["parent_id"] = parent_id

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_CREATE_FILE_FROM_TEXT",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            file_id: str | None = None
            file_name: str | None = name
            mime: str | None = mime_type
            web_view_link: str | None = None

            if isinstance(payload, dict):
                file_id = (
                    payload.get("id") or payload.get("file_id") or payload.get("fileId")
                )
                file_name = payload.get("name") or payload.get("file_name") or name
                mime = payload.get("mimeType") or payload.get("mime_type") or mime_type
                web_view_link = payload.get("webViewLink") or payload.get(
                    "web_view_link"
                )

            if not file_id:
                return None, "Composio response did not include a file id"

            if not web_view_link:
                web_view_link = self._drive_web_view_link(file_id, mime)

            return (
                {
                    "id": file_id,
                    "name": file_name,
                    "mimeType": mime,
                    "webViewLink": web_view_link,
                },
                None,
            )
        except Exception as e:
            logger.error(f"Failed to create Drive file: {e!s}")
            return None, str(e)

    async def trash_drive_file(
        self,
        connected_account_id: str,
        entity_id: str,
        file_id: str,
    ) -> str | None:
        """Move a Google Drive file to trash via Composio."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_TRASH_FILE",
                params={"file_id": file_id},
                entity_id=entity_id,
            )
            if not result.get("success"):
                return result.get("error", "Unknown error")
            return None
        except Exception as e:
            logger.error(f"Failed to trash Drive file: {e!s}")
            return str(e)
