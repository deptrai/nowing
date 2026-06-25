import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.crypto_data_categories import DataCategory
from app.db import CryptoDataSnapshot

logger = logging.getLogger(__name__)


class CryptoDataStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_fresh_snapshot(
        self,
        search_space_id: int,
        project_id: int,
        category: DataCategory,
        tool_name: str,
        args_hash: str,
    ) -> dict | None:
        """Returns cached data dict if a fresh (non-expired, non-error) snapshot exists."""
        now = datetime.now(UTC)
        result = await self._db.execute(
            select(CryptoDataSnapshot.data)
            .where(
                CryptoDataSnapshot.search_space_id == search_space_id,
                CryptoDataSnapshot.project_id == project_id,
                CryptoDataSnapshot.data_category == category,
                CryptoDataSnapshot.tool_name == tool_name,
                CryptoDataSnapshot.args_hash == args_hash,
                CryptoDataSnapshot.expires_at > now,
                CryptoDataSnapshot.is_error.is_(False),
            )
            .order_by(CryptoDataSnapshot.fetched_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row  # JSONB column returns dict directly

    async def write_snapshot(
        self,
        search_space_id: int,
        project_id: int,
        category: DataCategory,
        tool_name: str,
        tool_args: dict | None,
        data: dict,
        ttl_seconds: int,
        api_source: str,
        is_error: bool = False,
    ) -> int:
        """Writes a new snapshot row. Returns the new snapshot id."""
        now = datetime.now(UTC)
        data_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        args_hash = self.compute_args_hash(tool_args)
        expires_at = now + timedelta(seconds=ttl_seconds)

        snapshot = CryptoDataSnapshot(
            search_space_id=search_space_id,
            project_id=project_id,
            data_category=category,
            tool_name=tool_name,
            tool_args=tool_args,
            data=data,
            data_hash=data_hash,
            args_hash=args_hash,
            fetched_at=now,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            is_error=is_error,
            api_source=api_source,
            created_at=now,
        )
        self._db.add(snapshot)
        await self._db.flush()
        return snapshot.id

    async def get_project_timeline(
        self,
        project_id: int,
        category: DataCategory,
        since: datetime,
        limit: int = 100,
        cursor: int | None = None,
    ) -> list[dict]:
        """Returns historical snapshots for a project/category since a given timestamp."""
        stmt = (
            select(
                CryptoDataSnapshot.id,
                CryptoDataSnapshot.fetched_at,
                CryptoDataSnapshot.expires_at,
                CryptoDataSnapshot.data,
                CryptoDataSnapshot.is_error,
                CryptoDataSnapshot.api_source,
            )
            .where(
                CryptoDataSnapshot.project_id == project_id,
                CryptoDataSnapshot.data_category == category,
                CryptoDataSnapshot.fetched_at >= since,
            )
            .order_by(CryptoDataSnapshot.fetched_at.desc())
            .limit(limit)
        )
        if cursor is not None:
            stmt = stmt.where(CryptoDataSnapshot.id < cursor)

        result = await self._db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": r.id,
                "fetched_at": r.fetched_at.isoformat(),
                "expires_at": r.expires_at.isoformat(),
                "data": r.data,
                "is_error": r.is_error,
                "api_source": r.api_source,
            }
            for r in rows
        ]

    @staticmethod
    def compute_args_hash(tool_args: dict | None) -> str:
        """SHA-256 of canonical JSON of tool args. Used as cache key component."""
        return hashlib.sha256(
            json.dumps(tool_args or {}, sort_keys=True).encode()
        ).hexdigest()
