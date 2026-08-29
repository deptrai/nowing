"""SearchSourceConnector CRUD routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.connectors.github_connector import GitHubConnector
from app.db import (
    Permission,
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.schemas import (
    SearchSourceConnectorBase,
    SearchSourceConnectorCreate,
    SearchSourceConnectorRead,
    SearchSourceConnectorUpdate,
)
from app.services.composio_service import ComposioService
from app.services.mcp_oauth.registry import get_service
from app.users import get_auth_context
from app.utils.connector_naming import ensure_unique_connector_name
from app.utils.periodic_scheduler import (
    create_periodic_schedule,
    delete_periodic_schedule,
    update_periodic_schedule,
)
from app.utils.rbac import check_permission
from app.utils.validators import raise_if_connector_deprecated

from ._shared import GitHubPATRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/github/repositories", response_model=list[dict[str, Any]])
async def list_github_repositories(
    pat_request: GitHubPATRequest,
    auth: AuthContext = Depends(get_auth_context),  # Ensure the user is logged in
):
    user = auth.user
    """
    Fetches a list of repositories accessible by the provided GitHub PAT.
    The PAT is used for this request only and is not stored.
    """
    try:
        # Initialize GitHubConnector with the provided PAT
        github_client = GitHubConnector(token=pat_request.github_pat)
        # Fetch repositories
        repositories = github_client.get_user_repositories()
        return repositories
    except ValueError as e:
        # Handle invalid token error specifically
        logger.error(f"GitHub PAT validation failed for user {user.id}: {e!s}")
        raise HTTPException(status_code=400, detail=f"Invalid GitHub PAT: {e!s}") from e
    except (ConnectionError, OSError, RuntimeError, TypeError) as e:
        logger.error(f"Failed to fetch GitHub repositories for user {user.id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch GitHub repositories."
        ) from e


@router.post("/search-source-connectors", response_model=SearchSourceConnectorRead)
async def create_search_source_connector(
    connector: SearchSourceConnectorCreate,
    workspace_id: int = Query(
        ..., description="ID of the workspace to associate the connector with"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create a new search source connector.
    Requires CONNECTORS_CREATE permission.

    Each workspace can have only one connector of each type (based on workspace_id and connector_type).
    The config must contain the appropriate keys for the connector type.
    """
    try:
        # Refuse new connections for deprecated connector types (HTTP 410). The
        # search APIs (Tavily/SearXNG/Linkup/Baidu) are created through this
        # generic route rather than a dedicated OAuth route, so this is the
        # single choke point that must enforce the deprecation.
        raise_if_connector_deprecated(connector.connector_type)

        # Check if user has permission to create connectors
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this workspace",
        )

        # Check if a connector with the same type already exists for this workspace
        # (for non-OAuth connectors that don't support multiple accounts)
        # Exception: MCP_CONNECTOR can have multiple instances with different names
        if connector.connector_type != SearchSourceConnectorType.MCP_CONNECTOR:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.workspace_id == workspace_id,
                    SearchSourceConnector.connector_type == connector.connector_type,
                )
            )
            existing_connector = result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {connector.connector_type} already exists in this workspace.",
                )

        # Prepare connector data
        connector_data = connector.model_dump()

        # MCP connectors support multiple instances — ensure unique name
        if connector.connector_type == SearchSourceConnectorType.MCP_CONNECTOR:
            connector_data["name"] = await ensure_unique_connector_name(
                session, connector_data["name"], workspace_id, user.id
            )

        # Exa MCP connector: build server_config from service URL + API key.
        # The raw exa_api_key is embedded into a request header and then removed
        # from the persisted config so the API key never sits at the top level.
        if connector.connector_type == SearchSourceConnectorType.EXA_MCP_CONNECTOR:
            exa_svc = get_service("exa")
            exa_url = exa_svc.mcp_url if exa_svc else "https://mcp.exa.ai/mcp"
            cfg = connector_data.setdefault("config", {})
            exa_api_key = cfg.pop("exa_api_key", None)
            user_server_config = cfg.get("server_config") or {}
            server_config = {
                "transport": user_server_config.get("transport", "streamable-http"),
                "url": user_server_config.get("url") or exa_url,
            }
            if exa_api_key:
                headers = user_server_config.get("headers") or {}
                headers["x-api-key"] = exa_api_key
                server_config["headers"] = headers
            elif user_server_config.get("headers"):
                server_config["headers"] = user_server_config["headers"]
            cfg["server_config"] = server_config
            connector_data["is_indexable"] = False
            connector_data["periodic_indexing_enabled"] = False
            connector_data["indexing_frequency_minutes"] = None

        # Automatically set next_scheduled_at if periodic indexing is enabled
        if (
            connector.periodic_indexing_enabled
            and connector.indexing_frequency_minutes
            and connector.next_scheduled_at is None
        ):
            connector_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=connector.indexing_frequency_minutes
            )

        db_connector = SearchSourceConnector(
            **connector_data, workspace_id=workspace_id, user_id=user.id
        )
        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        # Create periodic schedule if periodic indexing is enabled
        if (
            db_connector.periodic_indexing_enabled
            and db_connector.indexing_frequency_minutes
        ):
            success = create_periodic_schedule(
                connector_id=db_connector.id,
                workspace_id=workspace_id,
                user_id=str(user.id),
                connector_type=db_connector.connector_type,
                frequency_minutes=db_connector.indexing_frequency_minutes,
                connector_config=db_connector.config,
            )
            if not success:
                logger.warning(
                    f"Failed to create periodic schedule for connector {db_connector.id}"
                )

        return db_connector
    except ValidationError as e:
        await session.rollback()
        raise HTTPException(status_code=422, detail=f"Validation error: {e!s}") from e
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Integrity error: A connector with this type already exists in this workspace. {e!s}",
        ) from e
    except HTTPException:
        await session.rollback()
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to create search source connector: {e!s}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create search source connector: {e!s}",
        ) from e


@router.get("/search-source-connectors", response_model=list[SearchSourceConnectorRead])
async def read_search_source_connectors(
    skip: int = 0,
    limit: int = 100,
    workspace_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all search source connectors for a workspace.
    Requires CONNECTORS_READ permission.
    """
    try:
        if workspace_id is None:
            raise HTTPException(
                status_code=400,
                detail="workspace_id is required",
            )

        # Check if user has permission to read connectors
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this workspace",
        )

        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.workspace_id == workspace_id
        )

        result = await session.execute(query.offset(skip).limit(limit))
        return result.scalars().all()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search source connectors: {e!s}",
        ) from e


@router.get(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def read_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific search source connector by ID.
    Requires CONNECTORS_READ permission.
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            auth,
            connector.workspace_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        return connector
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search source connector: {e!s}"
        ) from e


@router.put(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def update_search_source_connector(
    connector_id: int,
    connector_update: SearchSourceConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Update a search source connector.
    Requires CONNECTORS_UPDATE permission.
    Handles partial updates, including merging changes into the 'config' field.
    """
    # Get the connector first
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    db_connector = result.scalars().first()

    if not db_connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Check permission
    await check_permission(
        session,
        auth,
        db_connector.workspace_id,
        Permission.CONNECTORS_UPDATE.value,
        "You don't have permission to update this connector",
    )

    # Convert the sparse update data (only fields present in request) to a dict
    update_data = connector_update.model_dump(exclude_unset=True)

    # Exa MCP connector is a live search tool: it is not indexable and never
    # runs on a schedule. Force these fields to their safe values so the
    # validation below and the final persisted state are consistent.
    if db_connector.connector_type == SearchSourceConnectorType.EXA_MCP_CONNECTOR:
        update_data["is_indexable"] = False
        update_data["periodic_indexing_enabled"] = False
        update_data["indexing_frequency_minutes"] = None
        update_data.pop("next_scheduled_at", None)

    # Validate periodic indexing fields
    # Get the effective values after update
    effective_is_indexable = update_data.get("is_indexable", db_connector.is_indexable)
    effective_periodic_enabled = update_data.get(
        "periodic_indexing_enabled", db_connector.periodic_indexing_enabled
    )
    effective_frequency = update_data.get(
        "indexing_frequency_minutes", db_connector.indexing_frequency_minutes
    )

    # Validate periodic indexing configuration
    if effective_periodic_enabled:
        if not effective_is_indexable:
            raise HTTPException(
                status_code=422,
                detail="periodic_indexing_enabled can only be True for indexable connectors",
            )
        if effective_frequency is None:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes is required when periodic_indexing_enabled is True",
            )
        if effective_frequency <= 0:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes must be greater than 0",
            )

        # Automatically set next_scheduled_at if not provided and periodic indexing is being enabled
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ) and "next_scheduled_at" not in update_data:
            # Schedule the next indexing based on the frequency
            update_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=effective_frequency
            )
    elif (
        effective_periodic_enabled is False
        and "periodic_indexing_enabled" in update_data
    ):
        # If disabling periodic indexing, clear the next_scheduled_at
        update_data["next_scheduled_at"] = None

    # Special handling for 'config' field
    if "config" in update_data:
        incoming_config = update_data["config"]  # Config data from the request
        existing_config = (
            db_connector.config if db_connector.config else {}
        )  # Current config from DB

        # Merge incoming config into existing config
        # This preserves existing keys (like GITHUB_PAT) if they are not in the incoming data
        merged_config = existing_config.copy()
        merged_config.update(incoming_config)

        # -- Validation after merging --
        # Validate the *merged* config based on the connector type
        # We need the connector type - use the one from the update if provided, else the existing one
        current_connector_type = (
            connector_update.connector_type
            if connector_update.connector_type is not None
            else db_connector.connector_type
        )

        try:
            # We can reuse the base validator by creating a temporary base model instance
            # Note: This assumes 'name' and 'is_indexable' are not crucial for config validation itself
            temp_data_for_validation = {
                "name": db_connector.name,  # Use existing name
                "connector_type": current_connector_type,
                "is_indexable": db_connector.is_indexable,  # Use existing value
                "last_indexed_at": db_connector.last_indexed_at,  # Not used by validator
                "config": merged_config,
            }
            SearchSourceConnectorBase.model_validate(temp_data_for_validation)
        except ValidationError as e:
            # Raise specific validation error for the merged config
            raise HTTPException(
                status_code=422, detail=f"Validation error for merged config: {e!s}"
            ) from e

        # If validation passes, update the main update_data dict with the merged config
        update_data["config"] = merged_config

    # Exa MCP connector: rebuild server_config from service URL + API key on update.
    if (
        db_connector.connector_type == SearchSourceConnectorType.EXA_MCP_CONNECTOR
        and "config" in update_data
    ):
        exa_svc = get_service("exa")
        exa_url = exa_svc.mcp_url if exa_svc else "https://mcp.exa.ai/mcp"
        cfg = update_data["config"]
        exa_api_key = cfg.pop("exa_api_key", None)
        user_server_config = cfg.get("server_config") or {}
        server_config = {
            "transport": user_server_config.get("transport", "streamable-http"),
            "url": user_server_config.get("url") or exa_url,
        }
        if exa_api_key:
            headers = user_server_config.get("headers") or {}
            headers["x-api-key"] = exa_api_key
            server_config["headers"] = headers
        elif user_server_config.get("headers"):
            server_config["headers"] = user_server_config["headers"]
        cfg["server_config"] = server_config
        update_data["config"] = cfg

        # The cached MCP tools for this workspace were built with the old
        # server_config (including the old API key). Evict them immediately so
        # the next chat turn loads fresh tool closures.
        from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
            invalidate_mcp_tools_cache,
        )

        invalidate_mcp_tools_cache(db_connector.workspace_id)

    # Apply all updates (including the potentially merged config)
    for key, value in update_data.items():
        # Prevent changing connector_type if it causes a duplicate (check moved here)
        if key == "connector_type" and value != db_connector.connector_type:
            check_result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.workspace_id == db_connector.workspace_id,
                    SearchSourceConnector.connector_type == value,
                    SearchSourceConnector.id != connector_id,
                )
            )
            existing_connector = check_result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {value} already exists in this workspace.",
                )

        setattr(db_connector, key, value)

    try:
        await session.commit()
        await session.refresh(db_connector)

        # Handle periodic schedule updates
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ):
            if (
                db_connector.periodic_indexing_enabled
                and db_connector.indexing_frequency_minutes
            ):
                # Create or update the periodic schedule
                success = update_periodic_schedule(
                    connector_id=db_connector.id,
                    workspace_id=db_connector.workspace_id,
                    user_id=str(user.id),
                    connector_type=db_connector.connector_type,
                    frequency_minutes=db_connector.indexing_frequency_minutes,
                )
                if not success:
                    logger.warning(
                        f"Failed to update periodic schedule for connector {db_connector.id}"
                    )
            else:
                # Delete the periodic schedule if disabled
                success = delete_periodic_schedule(db_connector.id)
                if not success:
                    logger.warning(
                        f"Failed to delete periodic schedule for connector {db_connector.id}"
                    )

        return db_connector
    except IntegrityError as e:
        await session.rollback()
        # This might occur if connector_type constraint is violated somehow after the check
        raise HTTPException(
            status_code=409, detail=f"Database integrity error during update: {e!s}"
        ) from e
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"Failed to update search source connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update search source connector: {e!s}",
        ) from e


@router.delete("/search-source-connectors/{connector_id}", response_model=dict)
async def delete_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a search source connector and all its associated documents.

    The deletion happens inline (documents are deleted in batches,
    then the connector record is removed).

    Requires CONNECTORS_DELETE permission.
    """
    from sqlalchemy import delete as sa_delete, func

    from app.db import Document

    deletion_batch_size = 500
    pruned_links: list[str] = []

    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        db_connector = result.scalars().first()

        if not db_connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            auth,
            db_connector.workspace_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        # Store connector info before deletion
        connector_name = db_connector.name

        # Delete any periodic schedule associated with this connector
        if db_connector.periodic_indexing_enabled:
            success = delete_periodic_schedule(connector_id)
            if not success:
                logger.warning(
                    f"Failed to delete periodic schedule for connector {connector_id}"
                )

        # For Composio connectors, delete the connected account in Composio
        composio_connector_types = [
            SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        ]
        if db_connector.connector_type in composio_connector_types:
            composio_connected_account_id = db_connector.config.get(
                "composio_connected_account_id"
            )
            if composio_connected_account_id and ComposioService.is_enabled():
                try:
                    service = ComposioService()
                    deleted = await service.delete_connected_account(
                        composio_connected_account_id
                    )
                    if deleted:
                        logger.info(
                            f"Successfully deleted Composio connected account {composio_connected_account_id} "
                            f"for connector {connector_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to delete Composio connected account {composio_connected_account_id} "
                            f"for connector {connector_id}"
                        )
                except (OSError, RuntimeError, TypeError, ValueError) as composio_error:
                    logger.warning(
                        f"Error deleting Composio connected account {composio_connected_account_id}: {composio_error!s}"
                    )

        # Delete documents in batches (chunks are deleted via CASCADE)
        total_deleted = 0
        count_result = await session.execute(
            select(func.count(Document.id)).where(Document.connector_id == connector_id)
        )
        total_docs = count_result.scalar() or 0

        logger.info(
            f"Starting deletion of connector {connector_id} ({connector_name}). "
            f"Documents to delete: {total_docs}"
        )

        while True:
            result = await session.execute(
                select(Document.id, Document.document_metadata["link"].as_string())
                .where(Document.connector_id == connector_id)
                .limit(deletion_batch_size)
            )
            rows = result.fetchall()
            doc_ids = [row[0] for row in rows]

            if not doc_ids:
                break

            pruned_links.extend(row[1] for row in rows if row[1])

            await session.execute(sa_delete(Document).where(Document.id.in_(doc_ids)))
            await session.commit()

            total_deleted += len(doc_ids)
            logger.info(
                f"Deleted batch of {len(doc_ids)} documents. "
                f"Progress: {total_deleted}/{total_docs}"
            )

        # chainlens-research owns canonical indexing; Nowing only deletes its
        # own documents here. No local canonical cleanup is required.

        # Delete the connector record
        workspace_id = db_connector.workspace_id
        is_mcp = db_connector.connector_type in (
            SearchSourceConnectorType.MCP_CONNECTOR,
            SearchSourceConnectorType.EXA_MCP_CONNECTOR,
        )
        await session.delete(db_connector)
        await session.commit()

        if is_mcp:
            from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
                invalidate_mcp_tools_cache,
            )

            invalidate_mcp_tools_cache(workspace_id)

        logger.info(
            f"Connector {connector_id} ({connector_name}) deleted successfully. "
            f"Total documents deleted: {total_deleted}"
        )

        doc_text = "document" if total_deleted == 1 else "documents"
        return {
            "message": f"Connector '{connector_name}' deleted. {total_deleted} {doc_text} removed.",
            "status": "completed",
            "connector_id": connector_id,
            "connector_name": connector_name,
            "documents_deleted": total_deleted,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start connector deletion: {e!s}",
        ) from e