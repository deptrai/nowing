"""MCP connector routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    Permission,
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.schemas import (
    MCPConnectorCreate,
    MCPConnectorRead,
    MCPConnectorUpdate,
    SearchSourceConnectorRead,
)
from app.services.composio_service import get_composio_service
from app.users import get_auth_context
from app.utils.connector_naming import ensure_unique_connector_name
from app.utils.rbac import check_permission

from ._shared import (
    DRIVE_CONNECTOR_TYPES,
    _is_auth_error,
    _persist_auth_expired,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# MCP Connector Routes
# =============================================================================


@router.post("/connectors/mcp", response_model=MCPConnectorRead, status_code=201)
async def create_mcp_connector(
    connector_data: MCPConnectorCreate,
    workspace_id: int = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create a new MCP (Model Context Protocol) connector.

    MCP connectors allow users to connect to MCP servers (like in Cursor).
    Tools are auto-discovered from the server - no manual configuration needed.

    Args:
        connector_data: MCP server configuration (command, args, env)
        workspace_id: ID of the workspace to attach the connector to
        session: Database session
        user: Current authenticated user

    Returns:
        Created MCP connector with server configuration

    Raises:
        HTTPException: If workspace not found or permission denied
    """
    try:
        # Check user has permission to create connectors
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this workspace",
        )

        # Ensure unique name across MCP connectors in this workspace
        unique_name = await ensure_unique_connector_name(
            session, connector_data.name, workspace_id, user.id
        )

        # Create the connector with single server config
        db_connector = SearchSourceConnector(
            name=unique_name,
            connector_type=SearchSourceConnectorType.MCP_CONNECTOR,
            is_indexable=False,  # MCP connectors are not indexable
            config={"server_config": connector_data.server_config.model_dump()},
            periodic_indexing_enabled=False,
            indexing_frequency_minutes=None,
            workspace_id=workspace_id,
            user_id=user.id,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        logger.info(
            f"Created MCP connector {db_connector.id} "
            f"for user {user.id} in workspace {workspace_id}"
        )

        from app.agents.chat.multi_agent_chat.shared.tools.mcp.cache import (
            refresh_mcp_tools_cache_for_connector,
        )

        refresh_mcp_tools_cache_for_connector(db_connector.id, workspace_id)

        connector_read = SearchSourceConnectorRead.model_validate(db_connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to create MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create MCP connector: {e!s}"
        ) from e


@router.get("/connectors/mcp", response_model=list[MCPConnectorRead])
async def list_mcp_connectors(
    workspace_id: int = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all MCP connectors for a workspace.

    Args:
        workspace_id: ID of the workspace
        session: Database session
        user: Current authenticated user

    Returns:
        List of MCP connectors with their tool configurations
    """
    try:
        # Check user has permission to read connectors
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this workspace",
        )

        # Fetch MCP connectors
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
                SearchSourceConnector.workspace_id == workspace_id,
            )
        )

        connectors = result.scalars().all()
        return [
            MCPConnectorRead.from_connector(SearchSourceConnectorRead.model_validate(c))
            for c in connectors
        ]

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to list MCP connectors: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list MCP connectors: {e!s}"
        ) from e


@router.get("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def get_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific MCP connector by ID.

    Args:
        connector_id: ID of the connector
        session: Database session
        user: Current authenticated user

    Returns:
        MCP connector with tool configurations
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to read connectors
        await check_permission(
            session,
            auth,
            connector.workspace_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to get MCP connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get MCP connector: {e!s}"
        ) from e


@router.put("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def update_mcp_connector(
    connector_id: int,
    connector_update: MCPConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update an MCP connector.

    Args:
        connector_id: ID of the connector to update
        connector_update: Updated connector data
        session: Database session
        user: Current authenticated user

    Returns:
        Updated MCP connector
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to update connectors
        await check_permission(
            session,
            auth,
            connector.workspace_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to update this connector",
        )

        # Update fields
        if connector_update.name is not None:
            connector.name = connector_update.name

        if connector_update.server_config is not None:
            connector.config = {
                "server_config": connector_update.server_config.model_dump()
            }

        connector.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(connector)

        logger.info(f"Updated MCP connector {connector_id}")

        from app.agents.chat.multi_agent_chat.shared.tools.mcp.cache import (
            refresh_mcp_tools_cache_for_connector,
        )

        refresh_mcp_tools_cache_for_connector(connector.id, connector.workspace_id)

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to update MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update MCP connector: {e!s}"
        ) from e


@router.delete("/connectors/mcp/{connector_id}", status_code=204)
async def delete_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete an MCP connector.

    Args:
        connector_id: ID of the connector to delete
        session: Database session
        user: Current authenticated user
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to delete connectors
        await check_permission(
            session,
            auth,
            connector.workspace_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        workspace_id = connector.workspace_id
        await session.delete(connector)
        await session.commit()

        from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
            invalidate_mcp_tools_cache,
        )

        invalidate_mcp_tools_cache(workspace_id)

        logger.info(f"Deleted MCP connector {connector_id}")

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to delete MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete MCP connector: {e!s}"
        ) from e


@router.post("/connectors/mcp/test")
async def test_mcp_server_connection(
    server_config: dict = Body(...),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Test connection to an MCP server and fetch available tools.

    This endpoint allows users to test their MCP server configuration
    before saving it, similar to Cursor's flow.

    Supports two transport types:
    - stdio: Local process with command, args, env
    - streamable-http/http/sse: Remote HTTP server with url, headers

    Args:
        server_config: Server configuration
        user: Current authenticated user

    Returns:
        Connection status and list of available tools
    """
    try:
        from app.agents.chat.multi_agent_chat.shared.tools.mcp.client import (
            test_mcp_connection,
            test_mcp_http_connection,
        )

        transport = server_config.get("transport", "stdio")

        # HTTP transport (streamable-http, http, sse)
        if transport in ("streamable-http", "http", "sse"):
            url = server_config.get("url")
            headers = server_config.get("headers", {})

            if not url:
                raise HTTPException(
                    status_code=400, detail="Server URL is required for HTTP transport"
                )

            result = await test_mcp_http_connection(url, headers, transport)
            return result

        # stdio transport (default)
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not command:
            raise HTTPException(
                status_code=400, detail="Server command is required for stdio transport"
            )

        # Test the connection
        result = await test_mcp_connection(command, args, env)

        return result

    except HTTPException:
        raise
    except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as e:
        logger.error(f"Failed to test MCP connection: {e!s}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to test connection: {e!s}",
            "tools": [],
        }


# ---------------------------------------------------------------------------
# Google Picker token endpoint (unified for native & Composio Drive)
# ---------------------------------------------------------------------------

@router.get("/connectors/{connector_id}/drive-picker-token")
async def get_drive_picker_token(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return an OAuth access token + client ID for the Google Picker API."""
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    connector = result.scalars().first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    await check_permission(
        session,
        auth,
        connector.workspace_id,
        Permission.CONNECTORS_READ.value,
        "You don't have permission to access this connector",
    )

    if connector.connector_type not in DRIVE_CONNECTOR_TYPES:
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for Google Drive connectors",
        )

    picker_api_key = config.GOOGLE_PICKER_API_KEY
    if not picker_api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_PICKER_API_KEY is not configured on the server",
        )

    try:
        if connector.connector_type == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR:
            from app.connectors.google_drive.credentials import get_valid_credentials

            credentials = await get_valid_credentials(session, connector_id)
            return {
                "access_token": credentials.token,
                "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                "picker_api_key": picker_api_key,
            }

        # Composio path
        composio_account_id = (connector.config or {}).get(
            "composio_connected_account_id"
        )
        if not composio_account_id:
            raise HTTPException(
                status_code=400,
                detail="Composio connected account not found. Please reconnect.",
            )
        service = get_composio_service()
        access_token = await asyncio.to_thread(
            service.get_access_token, composio_account_id
        )
        return {
            "access_token": access_token,
            "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
            "picker_api_key": picker_api_key,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to get Drive picker token: {e!s}", exc_info=True)
        if _is_auth_error(str(e)):
            await _persist_auth_expired(session, connector_id)
            raise HTTPException(
                status_code=400,
                detail="Google Drive authentication expired. Please re-authenticate.",
            ) from e
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve access token. Check server logs for details.",
        ) from e


# =============================================================================
# MCP Tool Trust (Allow-List) Routes
# =============================================================================


class MCPTrustToolRequest(BaseModel):
    tool_name: str


async def _ensure_mcp_connector_for_user(
    session: AsyncSession, *, user_id, connector_id: int
) -> int:
    """Verify ``connector_id`` is an MCP-backed connector owned by ``user_id``.

    The trust-list feature is intentionally MCP-only; native connectors
    (Gmail, Calendar, Notion, ...) do not have a "trust this tool" UI.
    The JSONB ``has_key("server_config")`` filter is the same MCP marker
    used elsewhere in this module.

    Returns the connector's ``workspace_id`` (needed downstream for
    MCP tool cache invalidation). Raises ``HTTPException(404)`` when the
    connector does not exist, is not owned by the user, or is not
    MCP-backed.
    """
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    result = await session.execute(
        select(SearchSourceConnector.workspace_id).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user_id,
            cast(SearchSourceConnector.config, PG_JSONB).has_key("server_config"),
        )
    )
    workspace_id = result.scalar_one_or_none()
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="MCP connector not found")
    return workspace_id


@router.post("/connectors/mcp/{connector_id}/trust-tool")
async def trust_mcp_tool(
    connector_id: int,
    body: MCPTrustToolRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Add a tool to the MCP connector's trusted (always-allow) list.

    Once trusted, the tool executes without HITL approval on subsequent
    calls. Works for both generic ``MCP_CONNECTOR`` and OAuth-backed MCP
    connectors (``LINEAR_CONNECTOR``, ``JIRA_CONNECTOR``, ...) — the
    storage primitive is the same JSON list under ``config.trusted_tools``.
    """
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        invalidate_mcp_tools_cache,
    )
    from app.services.user_tool_allowlist import add_user_trust

    try:
        workspace_id = await _ensure_mcp_connector_for_user(
            session, user_id=user.id, connector_id=connector_id
        )
        trusted = await add_user_trust(
            session,
            user_id=user.id,
            connector_id=connector_id,
            tool_name=body.tool_name,
        )
        await session.commit()
        invalidate_mcp_tools_cache(workspace_id)
        return {"status": "ok", "trusted_tools": trusted}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail="MCP connector not found") from e
    except SQLAlchemyError as e:
        logger.error(f"Failed to trust MCP tool: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to trust tool: {e!s}"
        ) from e


@router.post("/connectors/mcp/{connector_id}/untrust-tool")
async def untrust_mcp_tool(
    connector_id: int,
    body: MCPTrustToolRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Remove a tool from the MCP connector's trusted list.

    The tool will require HITL approval again on subsequent calls.
    """
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        invalidate_mcp_tools_cache,
    )
    from app.services.user_tool_allowlist import remove_user_trust

    try:
        workspace_id = await _ensure_mcp_connector_for_user(
            session, user_id=user.id, connector_id=connector_id
        )
        trusted = await remove_user_trust(
            session,
            user_id=user.id,
            connector_id=connector_id,
            tool_name=body.tool_name,
        )
        await session.commit()
        invalidate_mcp_tools_cache(workspace_id)
        return {"status": "ok", "trusted_tools": trusted}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail="MCP connector not found") from e
    except SQLAlchemyError as e:
        logger.error(f"Failed to untrust MCP tool: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to untrust tool: {e!s}"
        ) from e
