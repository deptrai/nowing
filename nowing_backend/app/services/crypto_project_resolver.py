import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CryptoProject

logger = logging.getLogger(__name__)

# Maps tool_name → (identifier_field, project_id_key_fn)
# Each entry describes how to extract a canonical project_id from tool_args.
_EXTRACTOR_MAP: dict[str, tuple[str, str]] = {
    # DeFiLlama: uses protocol_slug as canonical id
    "get_defillama_protocol": ("protocol_slug", "defillama:{}"),
    "get_defillama_yields": ("protocol_slug", "defillama:{}"),
    # CoinGecko: uses token_id (slug like "ethereum", "uniswap")
    "get_coingecko_token_info": ("token_id", "coingecko:{}"),
    # DexScreener: uses token_address (chain/address pair not available as single field)
    "get_live_token_price": ("token_address", "dex:{}"),
    "get_live_token_data": ("token_address", "dex:{}"),
    # GoPlus / Etherscan: contract_address
    "check_token_security": ("contract_address", "contract:{}"),
    "get_token_security": ("contract_address", "contract:{}"),
    "get_contract_info": ("contract_address", "contract:{}"),
    # Nansen: token_address (EVM address)
    "get_nansen_smart_money": ("token_address", "dex:{}"),
    "get_nansen_token_god_mode": ("token_address", "dex:{}"),
    "get_nansen_wallet_label": ("wallet_address", "wallet:{}"),
    # TokenInsight / CertiK: token_symbol
    "get_tokeninsight_rating": ("token_symbol", "symbol:{}"),
    "get_tokeninsight_research_snippet": ("token_symbol", "symbol:{}"),
    "get_certik_audit_score": ("token_symbol", "symbol:{}"),
    "get_certik_incident_history": ("token_symbol", "symbol:{}"),
    # Sentiment / news: symbol-based
    "get_cmc_sentiment": ("symbol", "symbol:{}"),
    "get_reddit_crypto_sentiment": ("symbol", "symbol:{}"),
    "get_fear_greed_index": ("_global", "global:fear_greed"),
    "get_crypto_news": ("symbol", "symbol:{}"),
    # DeFiLlama overview tools have no per-token identifier — resolved as market-wide
    "get_defillama_tvl_overview": ("_global", "global:defi_overview"),
    "get_defillama_stablecoins": ("_global", "global:stablecoins"),
    "get_defillama_bridges": ("_global", "global:bridges"),
}


class CryptoProjectResolver:
    """Maps heterogeneous tool args to canonical crypto_projects.id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve(self, tool_name: str, tool_args: dict) -> int | None:
        """
        Returns crypto_projects.id, creating new project row if needed.
        Returns None if args don't contain a recognizable identifier.
        """
        extracted = self._extract_identifier(tool_name, tool_args or {})
        if extracted is None:
            return None
        project_id_str, symbol = extracted
        return await self._find_or_create(project_id_str, symbol, tool_name, tool_args or {})

    def _extract_identifier(
        self, tool_name: str, tool_args: dict
    ) -> tuple[str, str | None] | None:
        """Returns (project_id_str, symbol_hint) or None."""
        entry = _EXTRACTOR_MAP.get(tool_name)
        if entry is None:
            return None

        field, id_template = entry

        # Global tools (no per-token args)
        if field == "_global":
            return id_template, None

        value = tool_args.get(field)
        if not value:
            # Try common fallback fields
            for fallback in ("token_symbol", "symbol", "token_address", "contract_address"):
                value = tool_args.get(fallback)
                if value:
                    break
        if not value:
            return None

        value = str(value).strip().lower()
        project_id_str = id_template.format(value)
        symbol = tool_args.get("token_symbol") or tool_args.get("symbol")
        if symbol:
            symbol = str(symbol).upper()
        return project_id_str, symbol

    async def _find_or_create(
        self,
        project_id_str: str,
        symbol: str | None,
        tool_name: str,
        tool_args: dict,
    ) -> int:
        # SELECT existing row
        result = await self._db.execute(
            select(CryptoProject.id).where(CryptoProject.project_id == project_id_str)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row

        # INSERT new row — use ON CONFLICT DO NOTHING + re-select for race safety
        values: dict = {"project_id": project_id_str}
        if symbol:
            values["symbol"] = symbol

        # Populate extra identifier columns from tool_args
        if tool_args.get("contract_address"):
            values["contract_address"] = str(tool_args["contract_address"]).lower()
        if tool_args.get("token_id"):
            values["coingecko_id"] = str(tool_args["token_id"])
        if tool_args.get("protocol_slug"):
            values["defillama_slug"] = str(tool_args["protocol_slug"])

        stmt = (
            pg_insert(CryptoProject)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["project_id"])
            .returning(CryptoProject.id)
        )
        result = await self._db.execute(stmt)
        new_id = result.scalar_one_or_none()
        if new_id is not None:
            await self._db.flush()
            return new_id

        # Concurrent insert won — re-fetch
        result = await self._db.execute(
            select(CryptoProject.id).where(CryptoProject.project_id == project_id_str)
        )
        return result.scalar_one()
