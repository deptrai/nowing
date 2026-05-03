---
storyId: 10.1
storyTitle: Crypto Data Schema & Core Services
epicParent: epic-10-crypto-data-layer
blocks: [Story 10.2, Story 10.4, Story 10.5]
relatedFRs: [FR36]
relatedNFRs: [NFR-CS6]
priority: P0 (BLOCKING for Epic 10)
estimatedEffort: 3-4 days
status: ready-for-dev
createdAt: 2026-04-29
author: Winston (Architect)
---

# Story 10.1: Crypto Data Schema & Core Services

## User Story

**As a** backend developer,
**I want** 3 new DB tables (crypto_projects, crypto_data_snapshots, search_space_crypto_watchlist) + CryptoProjectResolver + CryptoDataStore services with Alembic migration,
**So that** Stories 10.2-10.5 have a stable data foundation to build on.

---

## Context

Epic 10 goal: eliminate redundant external API calls by storing tool results in PostgreSQL. This story creates the schema and read/write services. No agent behavior changes yet — those come in Story 10.2.

Architecture reference: `/Users/luisphan/.claude/plans/partitioned-crafting-phoenix.md` Section 1-3.

---

## Deliverables

### 📄 Files to Create (4 files)

#### 1. `nowing_backend/app/models/crypto.py`

```python
from sqlalchemy import (
    BigInteger, Boolean, Column, ForeignKey, Integer,
    String, Text, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin  # or app.db import Base

class CryptoProject(Base, TimestampMixin):
    __tablename__ = "crypto_projects"
    id               = Column(Integer, primary_key=True)
    project_id       = Column(String(128), unique=True, nullable=False)
    symbol           = Column(String(32))
    name             = Column(String(256))
    chain            = Column(String(64))
    contract_address = Column(String(128))
    coingecko_id     = Column(String(128))
    defillama_slug   = Column(String(128))
    metadata_        = Column("metadata", JSONB)
    snapshots        = relationship("CryptoDataSnapshot", back_populates="project")
    __table_args__ = (
        Index("ix_crypto_projects_symbol", "symbol"),
        Index("ix_crypto_projects_contract_address", "contract_address"),
    )

class CryptoDataSnapshot(Base):
    __tablename__ = "crypto_data_snapshots"
    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id    = Column(Integer, ForeignKey("crypto_projects.id", ondelete="CASCADE"), nullable=False)
    data_category = Column(String(64), nullable=False)
    tool_name     = Column(String(128), nullable=False)
    tool_args     = Column(JSONB)
    data          = Column(JSONB, nullable=False)
    data_hash     = Column(String(64), nullable=False)
    fetched_at    = Column(..., nullable=False, server_default="NOW()")
    ttl_seconds   = Column(Integer, nullable=False)
    expires_at    = Column(..., nullable=False)
    is_error      = Column(Boolean, nullable=False, default=False)
    api_source    = Column(String(64), nullable=False)
    created_at    = Column(..., nullable=False, server_default="NOW()")
    project       = relationship("CryptoProject", back_populates="snapshots")
    __table_args__ = (
        Index("ix_crypto_snapshots_project_category_fetched",
              "project_id", "data_category", "fetched_at"),
        Index("ix_crypto_snapshots_expires_at", "expires_at"),
    )

class SearchSpaceCryptoWatchlist(Base):
    __tablename__ = "search_space_crypto_watchlist"
    id              = Column(Integer, primary_key=True)
    search_space_id = Column(Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False)
    project_id      = Column(Integer, ForeignKey("crypto_projects.id", ondelete="CASCADE"), nullable=False)
    added_at        = Column(..., nullable=False, server_default="NOW()")
    added_by_id     = Column(UUID, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    pin_order       = Column(Integer)
    __table_args__ = (UniqueConstraint("search_space_id", "project_id"),)
```

Use exact same import patterns as existing models in `app/db.py` (TimestampMixin, UUID type).

#### 2. `nowing_backend/app/agents/new_chat/tools/crypto_data_categories.py`

```python
from enum import Enum

class DataCategory(str, Enum):
    PRICE_REALTIME   = "price_realtime"
    SENTIMENT_INDEX  = "sentiment_index"
    DEFI_TVL         = "defi_tvl"
    DEFI_YIELDS      = "defi_yields"
    DEFI_OVERVIEW    = "defi_overview"
    NEWS             = "news"
    TOKEN_FUNDAMENTALS = "token_fundamentals"
    SMART_MONEY      = "smart_money"
    SECURITY_AUDIT   = "security_audit"
    CONTRACT_INFO    = "contract_info"
    TOKENINSIGHT     = "tokeninsight"
    CERTIK_INCIDENTS = "certik_incidents"

TTL_SECONDS: dict[DataCategory, int] = {
    DataCategory.PRICE_REALTIME:    5 * 60,
    DataCategory.SENTIMENT_INDEX:   15 * 60,
    DataCategory.DEFI_TVL:          60 * 60,
    DataCategory.DEFI_YIELDS:       2 * 60 * 60,
    DataCategory.DEFI_OVERVIEW:     2 * 60 * 60,
    DataCategory.NEWS:              60 * 60,
    DataCategory.TOKEN_FUNDAMENTALS: 60 * 60,
    DataCategory.SMART_MONEY:       2 * 60 * 60,
    DataCategory.SECURITY_AUDIT:    24 * 60 * 60,
    DataCategory.CONTRACT_INFO:     24 * 60 * 60,
    DataCategory.TOKENINSIGHT:      24 * 60 * 60,
    DataCategory.CERTIK_INCIDENTS:  24 * 60 * 60,
}

# Maps tool_name → (category, api_source)
TOOL_CATEGORY_MAP: dict[str, tuple[DataCategory, str]] = {
    "get_live_token_price":             (DataCategory.PRICE_REALTIME, "dexscreener"),
    "get_live_token_data":              (DataCategory.PRICE_REALTIME, "dexscreener"),
    "get_cmc_sentiment":                (DataCategory.SENTIMENT_INDEX, "coinmarketcap"),
    "get_reddit_crypto_sentiment":      (DataCategory.SENTIMENT_INDEX, "reddit"),
    "get_fear_greed_index":             (DataCategory.SENTIMENT_INDEX, "alternative.me"),
    "get_defillama_protocol":           (DataCategory.DEFI_TVL, "defillama"),
    "get_defillama_yields":             (DataCategory.DEFI_YIELDS, "defillama"),
    "get_defillama_tvl_overview":       (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_defillama_stablecoins":        (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_defillama_bridges":            (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_crypto_news":                  (DataCategory.NEWS, "cryptopanic"),
    "get_coingecko_token_info":         (DataCategory.TOKEN_FUNDAMENTALS, "coingecko"),
    "get_nansen_smart_money":           (DataCategory.SMART_MONEY, "nansen"),
    "get_nansen_wallet_label":          (DataCategory.SMART_MONEY, "nansen"),
    "get_nansen_token_god_mode":        (DataCategory.SMART_MONEY, "nansen"),
    # run_dune_query intentionally excluded: Dune query IDs are not token-specific.
    # A query_id alone cannot resolve to a crypto_project — would require the caller
    # to tag the query with a token identifier, which is out of scope for this epic.
    "check_token_security":             (DataCategory.SECURITY_AUDIT, "goplus"),
    "get_token_security":               (DataCategory.SECURITY_AUDIT, "goplus"),
    "get_certik_audit_score":           (DataCategory.SECURITY_AUDIT, "certik"),
    "get_contract_info":                (DataCategory.CONTRACT_INFO, "etherscan"),
    "get_tokeninsight_rating":          (DataCategory.TOKENINSIGHT, "tokeninsight"),
    "get_tokeninsight_research_snippet": (DataCategory.TOKENINSIGHT, "tokeninsight"),
    "get_certik_incident_history":      (DataCategory.CERTIK_INCIDENTS, "certik"),
}
```

#### 3. `nowing_backend/app/services/crypto_project_resolver.py`

```python
class CryptoProjectResolver:
    """Maps heterogeneous tool args to canonical crypto_projects.id."""

    def __init__(self, db: AsyncSession): ...

    async def resolve(self, tool_name: str, tool_args: dict) -> int | None:
        """
        Returns crypto_projects.id, creating new project if needed.
        Returns None if args don't contain recognizable identifier.
        """

    async def _extract_identifier(self, tool_name: str, tool_args: dict) -> tuple[str, str] | None:
        """Returns (field_name, value) or None."""
        # DeFiLlama: protocol_slug
        # CoinGecko: token_id
        # DexScreener: chain + token_address → "chain/address"
        # GoPlus/Etherscan: contract_address
        # Nansen/TokenInsight: token_symbol

    async def _find_or_create(self, project_id: str, symbol: str | None) -> int:
        # SELECT existing by project_id → return id
        # INSERT new row if not found → return new id
```

#### 4. `nowing_backend/app/services/crypto_data_store.py`

```python
import hashlib, json
from datetime import datetime, timezone, timedelta

class CryptoDataStore:
    def __init__(self, db: AsyncSession): ...

    async def get_fresh_snapshot(
        self,
        project_id: int,
        category: DataCategory,
        tool_name: str,
        args_hash: str,
    ) -> dict | None:
        """Returns data dict if fresh snapshot exists, None if miss/expired."""
        # SELECT data FROM crypto_data_snapshots
        # WHERE project_id=? AND data_category=? AND tool_name=?
        #   AND expires_at > NOW() AND is_error=false
        # ORDER BY fetched_at DESC LIMIT 1

    async def write_snapshot(
        self,
        project_id: int,
        category: DataCategory,
        tool_name: str,
        tool_args: dict,
        data: dict,
        ttl_seconds: int,
        api_source: str,
        is_error: bool = False,
    ) -> int:
        """Writes new snapshot row. Returns snapshot id."""
        data_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        # INSERT INTO crypto_data_snapshots ...
        # Return snapshot.id

    async def get_project_timeline(
        self,
        project_id: int,
        category: DataCategory,
        since: datetime,
        limit: int = 100,
        cursor: int | None = None,
    ) -> list[dict]:
        """Returns historical snapshots for project/category since timestamp."""
```

#### 5. `alembic/versions/XXX_add_crypto_data_tables.py`

Standard Alembic migration creating the 3 tables with indexes. Follow pattern from most recent migration in `alembic/versions/`.

### 📄 Files to Modify (2 files)

#### `nowing_backend/app/db.py`
Add at end of model imports section (for Alembic discovery):
```python
from app.models.crypto import CryptoProject, CryptoDataSnapshot, SearchSpaceCryptoWatchlist
```

---

## Acceptance Criteria

### AC1: Migration runs clean

**Given** clean DB (no crypto tables)
**When** `alembic upgrade head`
**Then** `crypto_projects`, `crypto_data_snapshots`, `search_space_crypto_watchlist` created
**And** composite index `(project_id, data_category, fetched_at DESC)` exists on snapshots
**And** index on `expires_at` exists
**And** `alembic downgrade -1` drops tables cleanly

### AC2: CryptoProjectResolver — symbol resolution

**Given** no crypto_projects rows
**When** `resolver.resolve("get_coingecko_token_info", {"token_id": "ethereum"})`
**Then** creates row with `project_id="ethereum"`, returns new id
**When** called again with same args
**Then** returns same id (no duplicate row)

### AC3: CryptoProjectResolver — DeFiLlama slug

**When** `resolver.resolve("get_defillama_protocol", {"protocol_slug": "uniswap"})`
**Then** creates/returns project with `defillama_slug="uniswap"`

### AC4: CryptoDataStore — write + read within TTL

**Given** snapshot written with ttl=3600
**When** `get_fresh_snapshot()` called 1 minute later
**Then** returns data dict (cache hit)

### AC5: CryptoDataStore — expired snapshot

**Given** snapshot written with ttl=1 (expires immediately)
**When** `get_fresh_snapshot()` called
**Then** returns None (cache miss)

### AC6: CryptoDataStore — error snapshots not served

**Given** snapshot written with `is_error=True`
**When** `get_fresh_snapshot()` called
**Then** returns None (error snapshots never served as cache hits)

### AC7: TOOL_CATEGORY_MAP covers cacheable crypto tools

**Given** `registry.py` list of tool names for crypto tools
**When** cross-checking against `TOOL_CATEGORY_MAP.keys()`
**Then** all 21 cacheable crypto tool names have entry in map
**And** `run_dune_query` is intentionally absent (Dune query IDs are not token-resolvable)

---

## Dev Notes

- Use `TIMESTAMPTZ` for all datetime columns (avoid naive datetimes)
- `data_hash` field enables dedup: if new fetch returns identical JSON, can skip write (optional optimization — not required for AC)
- `TimestampMixin` from existing db.py provides `created_at`/`updated_at` — use it for `CryptoProject`
- Alembic migration number: check latest in `alembic/versions/` and increment
- `metadata` is reserved in SQLAlchemy — use `metadata_` as Python attr, map to column name `metadata`
