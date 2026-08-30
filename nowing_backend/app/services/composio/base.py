"""Base Composio client and low-level tool execution."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import config

logger = logging.getLogger(__name__)


class ComposioClientMixin:
    """Low-level Composio client wrapper and toolkit helpers."""

    DEFAULT_DOWNLOAD_DIR = "/tmp/composio_downloads"

    def __init__(
        self, api_key: str | None = None, file_download_dir: str | None = None
    ):
        # Look up ``Composio`` via the backward-compatible shim so that
        # ``patch.object(app.services.composio_service, \"Composio\")``
        # continues to intercept client construction for existing tests.
        from app.services import composio_service as _composio_service_mod

        self.api_key = api_key or config.COMPOSIO_API_KEY
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY is required but not configured")

        self.file_download_dir = file_download_dir or self.DEFAULT_DOWNLOAD_DIR
        os.makedirs(self.file_download_dir, exist_ok=True)

        self.client = _composio_service_mod.Composio(
            api_key=self.api_key, file_download_dir=self.file_download_dir
        )

    @staticmethod
    def is_enabled() -> bool:
        """Check if Composio integration is enabled."""
        return config.COMPOSIO_ENABLED and bool(config.COMPOSIO_API_KEY)

    def _get_auth_config_for_toolkit(self, toolkit_id: str) -> str | None:
        """Get the auth_config_id for a specific toolkit."""

        try:
            auth_configs = self.client.auth_configs.list()
            for auth_config in auth_configs.items:
                config_toolkit = getattr(auth_config, "toolkit", None)
                if config_toolkit is None:
                    continue

                toolkit_name = None
                if isinstance(config_toolkit, str):
                    toolkit_name = config_toolkit
                elif hasattr(config_toolkit, "slug"):
                    toolkit_name = config_toolkit.slug
                elif hasattr(config_toolkit, "name"):
                    toolkit_name = config_toolkit.name
                elif hasattr(config_toolkit, "id"):
                    toolkit_name = config_toolkit.id

                if toolkit_name and toolkit_name.lower() == toolkit_id.lower():
                    logger.info(
                        f"Found auth config {auth_config.id} for toolkit {toolkit_id}"
                    )
                    return auth_config.id

            logger.warning(
                f"No auth config found for toolkit '{toolkit_id}'. Available auth configs:"
            )
            for auth_config in auth_configs.items:
                config_toolkit = getattr(auth_config, "toolkit", None)
                logger.warning(f"  - {auth_config.id}: toolkit={config_toolkit}")

            return None
        except Exception as e:
            logger.error(f"Failed to list auth configs: {e!s}")
            return None

    async def initiate_connection(
        self,
        user_id: str,
        toolkit_id: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Initiate OAuth flow for a Composio toolkit."""
        from app.services.composio.constants import COMPOSIO_TOOLKIT_NAMES

        if toolkit_id not in COMPOSIO_TOOLKIT_NAMES:
            raise ValueError(f"Unknown toolkit: {toolkit_id}")

        try:
            auth_config_id = self._get_auth_config_for_toolkit(toolkit_id)

            if not auth_config_id:
                raise ValueError(
                    f"No auth config found for toolkit '{toolkit_id}'. "
                    f"Please create an auth config for {COMPOSIO_TOOLKIT_NAMES.get(toolkit_id, toolkit_id)} "
                    f"in your Composio dashboard at https://app.composio.dev"
                )

            connection_request = self.client.connected_accounts.initiate(
                user_id=user_id,
                auth_config_id=auth_config_id,
                callback_url=redirect_uri,
                allow_multiple=True,
            )

            logger.info(
                f"Initiated Composio connection for user {user_id}, toolkit {toolkit_id}, auth_config {auth_config_id}"
            )

            return {
                "redirect_url": connection_request.redirect_url,
                "connection_id": getattr(connection_request, "id", None),
            }

        except Exception as e:
            logger.error(f"Failed to initiate Composio connection: {e!s}")
            raise

    async def delete_connected_account(self, connected_account_id: str) -> bool:
        """Delete a connected account from Composio."""
        try:
            self.client.connected_accounts.delete(connected_account_id)
            logger.info(
                f"Successfully deleted Composio connected account: {connected_account_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete Composio connected account {connected_account_id}: {e!s}"
            )
            return False

    def refresh_connected_account(
        self,
        connected_account_id: str,
        redirect_url: str | None = None,
    ) -> dict[str, Any]:
        """Refresh an expired Composio connected account."""
        kwargs: dict[str, Any] = {}
        if redirect_url is not None:
            kwargs["body_redirect_url"] = redirect_url
        result = self.client.connected_accounts.refresh(
            nanoid=connected_account_id,
            **kwargs,
        )
        return {
            "id": result.id,
            "status": result.status,
            "redirect_url": result.redirect_url,
        }

    def wait_for_connection(
        self,
        connected_account_id: str,
        timeout: float = 30.0,
    ) -> str:
        """Poll Composio until the connected account reaches ACTIVE status."""
        try:
            account = self.client.connected_accounts.wait_for_connection(
                id=connected_account_id,
                timeout=timeout,
            )
            status = getattr(account, "status", "UNKNOWN")
            logger.info(f"Composio account {connected_account_id} is now {status}")
            return status
        except Exception as e:
            logger.error(
                f"Timeout/error waiting for Composio account {connected_account_id}: {e!s}"
            )
            raise

    def get_access_token(self, connected_account_id: str) -> str:
        """Retrieve the raw OAuth access token for a Composio connected account."""
        account = self.client.connected_accounts.get(nanoid=connected_account_id)
        token = getattr(getattr(account, "state", None), "val", None)
        if token is None:
            raise ValueError(
                f"No state.val on connected account {connected_account_id}"
            )
        access_token = getattr(token, "access_token", None)
        if not access_token:
            raise ValueError(f"No access_token in state.val for {connected_account_id}")
        if len(access_token) < 20:
            raise ValueError(
                f"Composio returned a masked access_token ({len(access_token)} chars) "
                f"for account {connected_account_id}. Disable 'Mask Connected Account "
                f"Secrets' in Composio dashboard: Settings → Project Settings."
            )
        return access_token

    async def execute_tool(
        self,
        connected_account_id: str,
        tool_name: str,
        params: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a Composio tool."""
        try:
            result = self.client.tools.execute(
                slug=tool_name,
                connected_account_id=connected_account_id,
                user_id=entity_id,
                arguments=params or {},
                dangerously_skip_version_check=True,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e!s}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_available_toolkits() -> list[dict[str, Any]]:
        """List all available Composio toolkits for the UI."""
        from app.services.composio.constants import (
            COMPOSIO_TOOLKIT_NAMES,
            INDEXABLE_TOOLKITS,
        )

        return [
            {
                "id": toolkit_id,
                "name": display_name,
                "is_indexable": toolkit_id in INDEXABLE_TOOLKITS,
                "description": f"Connect to {display_name} via Composio",
            }
            for toolkit_id, display_name in COMPOSIO_TOOLKIT_NAMES.items()
        ]

    @staticmethod
    def _unwrap_response_data(data: Any) -> Any:
        """Composio responses often nest the meaningful payload under
        ``data.data.response_data``. Walk that envelope safely and return
        whichever inner dict actually has the result keys."""
        if not isinstance(data, dict):
            return data
        inner = data.get("data", data)
        if isinstance(inner, dict):
            return inner.get("response_data", inner)
        return inner
