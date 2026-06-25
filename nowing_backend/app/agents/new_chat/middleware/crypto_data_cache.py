import json
import logging
import os

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.agents.new_chat.tools.crypto_data_categories import TOOL_CATEGORY_MAP, TTL_SECONDS
from app.db import shielded_async_session
from app.services.crypto_cache_lock import crypto_cache_lock
from app.services.crypto_data_store import CryptoDataStore
from app.services.crypto_project_resolver import CryptoProjectResolver

logger = logging.getLogger(__name__)

_CACHE_ENABLED = os.getenv("CRYPTO_DATA_CACHE_ENABLED", "false").lower() == "true"


class CryptoDataCacheMiddleware(AgentMiddleware):
    """Intercepts crypto tool calls to serve cached results from DB.

    Placed AFTER SourceAttributionMiddleware so narration events always fire
    regardless of whether data is served from cache or fetched live.

    Uses shielded_async_session() per DB op — independent short-lived sessions,
    NOT the HTTP-request-scoped session from create_nowing_deep_agent().

    Thundering herd protection via distributed Redis lock (Story 10.3).
    If Redis unavailable, falls back to per-process asyncio.Lock.
    """

    def __init__(self, search_space_id: int, redis_client=None):
        self.search_space_id = search_space_id
        self._redis = redis_client

    async def awrap_tool_call(self, request, handler):
        if not _CACHE_ENABLED:
            return await handler(request)

        tool_call = request.tool_call if hasattr(request, "tool_call") else {}
        tool_name = (
            tool_call.get("name") if isinstance(tool_call, dict)
            else getattr(tool_call, "name", None)
        ) or ""

        if tool_name not in TOOL_CATEGORY_MAP:
            return await handler(request)

        try:
            return await self._cached_tool_call(request, handler, tool_name, tool_call)
        except Exception as exc:
            logger.warning("CryptoDataCache error, falling back to direct API: %s", exc)
            return await handler(request)

    async def _cached_tool_call(self, request, handler, tool_name: str, tool_call):
        category, api_source = TOOL_CATEGORY_MAP[tool_name]
        ttl = TTL_SECONDS[category]
        tool_args = (
            tool_call.get("args") if isinstance(tool_call, dict)
            else getattr(tool_call, "args", {})
        ) or {}
        args_hash = CryptoDataStore.compute_args_hash(tool_args)
        tool_call_id = (
            tool_call.get("id") if isinstance(tool_call, dict)
            else getattr(tool_call, "id", None)
        ) or ""

        project_id: int | None = None
        async with shielded_async_session() as db:
            resolver = CryptoProjectResolver(db)
            store = CryptoDataStore(db)

            project_id = await resolver.resolve(tool_name, tool_args)
            if project_id is None:
                return await handler(request)

            cached = await store.get_fresh_snapshot(
                self.search_space_id, project_id, category, tool_name, args_hash
            )
            if cached is not None:
                logger.debug(
                    "CryptoDataCache HIT: %s/%s project_id=%s workspace=%s",
                    tool_name, category, project_id, self.search_space_id
                )
                await db.commit()
                return ToolMessage(
                    content=json.dumps(cached),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            await db.commit()

        # MISS → acquire distributed lock → double-check → call API
        lock_key = f"crypto_lock:{tool_name}:{project_id}:{args_hash}"
        async with crypto_cache_lock(lock_key, self._redis):
            # Double-check: another process may have filled cache while we waited for the lock
            async with shielded_async_session() as db:
                store = CryptoDataStore(db)
                cached = await store.get_fresh_snapshot(
                    self.search_space_id, project_id, category, tool_name, args_hash
                )
                if cached is not None:
                    logger.debug(
                        "CryptoDataCache DOUBLE-CHECK HIT: %s/%s project_id=%s workspace=%s",
                        tool_name, category, project_id, self.search_space_id
                    )
                    return ToolMessage(
                        content=json.dumps(cached),
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )

            logger.debug("CryptoDataCache MISS: %s/%s", tool_name, category)
            result = await handler(request)
            data = self._extract_data(result)

            try:
                async with shielded_async_session() as db:
                    store = CryptoDataStore(db)
                    is_error = isinstance(data, dict) and bool(data.get("error"))
                    await store.write_snapshot(
                        search_space_id=self.search_space_id,
                        project_id=project_id,
                        category=category,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        data=data if isinstance(data, dict) else {"content": str(data)},
                        ttl_seconds=300 if is_error else ttl,
                        api_source=api_source,
                        is_error=is_error,
                    )
                    await db.commit()
            except Exception as write_exc:
                logger.warning("CryptoDataCache write failed (non-fatal): %s", write_exc)

        return result

    @staticmethod
    def _extract_data(result) -> dict | str:
        if isinstance(result, ToolMessage):
            content = result.content
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    return content
            return content
        if isinstance(result, dict):
            return result
        content = getattr(result, "content", None)
        if isinstance(content, str):
            try:
                return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                return content
        return {}
