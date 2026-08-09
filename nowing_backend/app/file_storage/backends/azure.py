"""Azure Blob Storage backend (the first production target)."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from app.file_storage.backends.base import StorageBackend


class AzureBlobBackend(StorageBackend):
    """Stores objects as blobs in an Azure Blob Storage container."""

    backend_name = "azure"

    def __init__(self, *, connection_string: str, container: str) -> None:
        self._connection_string = connection_string
        self._container = container

    def _service(self):
        from azure.storage.blob.aio import BlobServiceClient

        return BlobServiceClient.from_connection_string(self._connection_string)

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        from azure.storage.blob import ContentSettings

        settings = ContentSettings(content_type=content_type) if content_type else None
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            await blob.upload_blob(data, overwrite=True, content_settings=settings)

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            downloader = await blob.download_blob()
            async for chunk in downloader.chunks():
                yield chunk

    async def delete(self, key: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            with contextlib.suppress(ResourceNotFoundError):
                await blob.delete_blob()

    async def exists(self, key: str) -> bool:
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            return await blob.exists()

    def public_url(self, key: str) -> str:
        """Return the direct blob URL for a public or signed container."""
        settings = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in self._connection_string.split(";")
            if "=" in item
        }
        account = settings.get("AccountName", "")
        endpoint_suffix = settings.get("EndpointSuffix", "core.windows.net")
        protocol = settings.get("DefaultEndpointsProtocol", "https")
        blob_endpoint = settings.get("BlobEndpoint")
        if blob_endpoint:
            return f"{blob_endpoint.rstrip('/')}/{self._container}/{key}"
        return f"{protocol}://{account}.blob.{endpoint_suffix}/{self._container}/{key}"
