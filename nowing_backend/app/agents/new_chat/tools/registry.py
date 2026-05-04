"""Tools registry for Nowing deep agent.

This module provides a registry pattern for managing tools in the Nowing agent.
It makes it easy for OSS contributors to add new tools by:
1. Creating a tool factory function in a new file in this directory
2. Registering the tool in the BUILTIN_TOOLS list below

Example of adding a new tool:
------------------------------
1. Create your tool file (e.g., `tools/my_tool.py`):

    from langchain_core.tools import tool
    from sqlalchemy.ext.asyncio import AsyncSession

    def create_my_tool(search_space_id: int, db_session: AsyncSession):
        @tool
        async def my_tool(param: str) -> dict:
            '''My tool description.'''
            # Your implementation
            return {"result": "success"}
        return my_tool

2. Import and register in this file:

    from .my_tool import create_my_tool

    # Add to BUILTIN_TOOLS list:
    ToolDefinition(
        name="my_tool",
        description="Description of what your tool does",
        factory=lambda deps: create_my_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from app.config import config
from app.db import ChatVisibility

from .confluence import (
    create_create_confluence_page_tool,
    create_delete_confluence_page_tool,
    create_update_confluence_page_tool,
)
from .crypto_realtime import (
    create_get_live_token_data_tool,
    create_get_live_token_price_tool,
)
from .dropbox import (
    create_create_dropbox_file_tool,
    create_delete_dropbox_file_tool,
)
from .generate_image import create_generate_image_tool
from .gmail import (
    create_create_gmail_draft_tool,
    create_send_gmail_email_tool,
    create_trash_gmail_email_tool,
    create_update_gmail_draft_tool,
)
from .google_calendar import (
    create_create_calendar_event_tool,
    create_delete_calendar_event_tool,
    create_update_calendar_event_tool,
)
from .google_drive import (
    create_create_google_drive_file_tool,
    create_delete_google_drive_file_tool,
)
from .jira import (
    create_create_jira_issue_tool,
    create_delete_jira_issue_tool,
    create_update_jira_issue_tool,
)
from .linear import (
    create_create_linear_issue_tool,
    create_delete_linear_issue_tool,
    create_update_linear_issue_tool,
)
from .mcp_tool import load_mcp_tools
from .notion import (
    create_create_notion_page_tool,
    create_delete_notion_page_tool,
    create_update_notion_page_tool,
)
from .onedrive import (
    create_create_onedrive_file_tool,
    create_delete_onedrive_file_tool,
)
from .podcast import create_generate_podcast_tool
from .report import create_generate_report_tool
from .scrape_webpage import create_scrape_webpage_tool
from .search_nowing_docs import create_search_nowing_docs_tool
from .update_memory import create_update_memory_tool, create_update_team_memory_tool
from .video_presentation import create_generate_video_presentation_tool
from .chainlens_research import create_chainlens_research_tool
from .web_search import create_web_search_tool
from .defillama import (
    create_defillama_protocol_tool,
    create_defillama_tvl_overview_tool,
    create_defillama_yields_tool,
    create_defillama_stablecoins_tool,
    create_defillama_bridges_tool,
)
from .crypto_sentiment import (
    create_cmc_sentiment_tool,
    create_reddit_crypto_sentiment_tool,
)
from .crypto_news import (
    create_crypto_news_tool,
    create_coingecko_token_info_tool,
)
from .contract_analysis import (
    create_contract_info_tool,
    create_check_token_security_tool,
)
from .nansen_smart_money import (  # Story 9-UX-4 AC1
    create_nansen_smart_money_tool,
    create_nansen_wallet_label_tool,
    create_nansen_token_god_mode_tool,
)
from .crypto_smart_money_flow import create_smart_money_flow_tool
from .certik_skynet import (  # Story 9-UX-4 AC2
    create_certik_audit_score_tool,
    create_certik_incident_history_tool,
)
from .dune_query import create_run_dune_query_tool  # Story 9-UX-4 AC3
from .tokeninsight_rating import (  # Story 9-UX-4 AC4
    create_tokeninsight_rating_tool,
    create_tokeninsight_research_snippet_tool,
)

# =============================================================================
# Tool Definition
# =============================================================================


@dataclass
class ToolDefinition:
    """Definition of a tool that can be added to the agent.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        factory: Callable that creates the tool. Receives a dict of dependencies.
        requires: List of dependency names this tool needs (e.g., "search_space_id", "db_session")
        enabled_by_default: Whether the tool is enabled when no explicit config is provided

    """

    name: str
    description: str
    factory: Callable[[dict[str, Any]], BaseTool]
    requires: list[str] = field(default_factory=list)
    enabled_by_default: bool = True
    hidden: bool = False


# =============================================================================
# Built-in Tools Registry
# =============================================================================

# Registry of all built-in tools
# Contributors: Add your new tools here!
BUILTIN_TOOLS: list[ToolDefinition] = [
    # Podcast generation tool
    ToolDefinition(
        name="generate_podcast",
        description="Generate an audio podcast from provided content",
        factory=lambda deps: create_generate_podcast_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            thread_id=deps["thread_id"],
        ),
        requires=["search_space_id", "db_session", "thread_id"],
    ),
    # Video presentation generation tool
    ToolDefinition(
        name="generate_video_presentation",
        description="Generate a video presentation with slides and narration from provided content",
        factory=lambda deps: create_generate_video_presentation_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            thread_id=deps["thread_id"],
        ),
        requires=["search_space_id", "db_session", "thread_id"],
    ),
    # Report generation tool (inline, short-lived sessions for DB ops)
    # Supports internal KB search via source_strategy so the agent does not
    # need a separate search step before generating.
    ToolDefinition(
        name="generate_report",
        description="Generate a structured report from provided content and export it",
        factory=lambda deps: create_generate_report_tool(
            search_space_id=deps["search_space_id"],
            thread_id=deps["thread_id"],
            connector_service=deps.get("connector_service"),
            available_connectors=deps.get("available_connectors"),
            available_document_types=deps.get("available_document_types"),
        ),
        requires=["search_space_id", "thread_id"],
        # connector_service, available_connectors, and available_document_types
        # are optional — when missing, source_strategy="kb_search" degrades
        # gracefully to "provided"
    ),
    # Generate image tool - creates images using AI models (DALL-E, GPT Image, etc.)
    ToolDefinition(
        name="generate_image",
        description="Generate images from text descriptions using AI image models",
        factory=lambda deps: create_generate_image_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
    # Web scraping tool - extracts content from webpages
    ToolDefinition(
        name="scrape_webpage",
        description="Scrape and extract the main content from a webpage",
        factory=lambda deps: create_scrape_webpage_tool(
            firecrawl_api_key=deps.get("firecrawl_api_key"),
        ),
        requires=[],  # firecrawl_api_key is optional
    ),
    # Web search tool — real-time web search via SearXNG + user-configured engines
    ToolDefinition(
        name="web_search",
        description="Search the web for real-time information using configured search engines",
        factory=lambda deps: create_web_search_tool(
            search_space_id=deps.get("search_space_id"),
            available_connectors=deps.get("available_connectors"),
        ),
        requires=[],
    ),
    # Chainlens deep research tool — auto-fallback to generate_report when unavailable.
    # `enabled_by_default` is gated on feature flag + URL so the tool (and its ~600 tokens of
    # prompt instructions) is excluded from the default system prompt when not configured.
    ToolDefinition(
        name="chainlens_deep_research",
        description="Perform deep web research using Chainlens engine with auto-fallback to built-in research",
        factory=lambda deps: create_chainlens_research_tool(),
        requires=[],  # No DB/connector deps — uses external API + Config
        enabled_by_default=bool(
            config.CHAINLENS_RESEARCH_ENABLED and config.CHAINLENS_RESEARCH_API_URL
        ),
    ),
    # Nowing documentation search tool
    ToolDefinition(
        name="search_nowing_docs",
        description="Search Nowing documentation for help with using the application",
        factory=lambda deps: create_search_nowing_docs_tool(
            db_session=deps["db_session"],
        ),
        requires=["db_session"],
    ),
    # =========================================================================
    # MEMORY TOOL - single update_memory, private or team by thread_visibility
    # =========================================================================
    ToolDefinition(
        name="update_memory",
        description="Save important long-term facts, preferences, and instructions to the (personal or team) memory",
        factory=lambda deps: (
            create_update_team_memory_tool(
                search_space_id=deps["search_space_id"],
                db_session=deps["db_session"],
                llm=deps.get("llm"),
            )
            if deps["thread_visibility"] == ChatVisibility.SEARCH_SPACE
            else create_update_memory_tool(
                user_id=deps["user_id"],
                db_session=deps["db_session"],
                llm=deps.get("llm"),
            )
        ),
        requires=[
            "user_id",
            "search_space_id",
            "db_session",
            "thread_visibility",
            "llm",
        ],
    ),
    # =========================================================================
    # LINEAR TOOLS - create, update, delete issues
    # Auto-disabled when no Linear connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_linear_issue",
        description="Create a new issue in the user's Linear workspace",
        factory=lambda deps: create_create_linear_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_linear_issue",
        description="Update an existing indexed Linear issue",
        factory=lambda deps: create_update_linear_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_linear_issue",
        description="Archive (delete) an existing indexed Linear issue",
        factory=lambda deps: create_delete_linear_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # NOTION TOOLS - create, update, delete pages
    # Auto-disabled when no Notion connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_notion_page",
        description="Create a new page in the user's Notion workspace",
        factory=lambda deps: create_create_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_notion_page",
        description="Append new content to an existing Notion page",
        factory=lambda deps: create_update_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_notion_page",
        description="Delete an existing Notion page",
        factory=lambda deps: create_delete_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # GOOGLE DRIVE TOOLS - create files, delete files
    # Auto-disabled when no Google Drive connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_google_drive_file",
        description="Create a new Google Doc or Google Sheet in Google Drive",
        factory=lambda deps: create_create_google_drive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_google_drive_file",
        description="Move an indexed Google Drive file to trash",
        factory=lambda deps: create_delete_google_drive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # DROPBOX TOOLS - create and trash files
    # Auto-disabled when no Dropbox connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_dropbox_file",
        description="Create a new file in Dropbox",
        factory=lambda deps: create_create_dropbox_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_dropbox_file",
        description="Delete a file from Dropbox",
        factory=lambda deps: create_delete_dropbox_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # ONEDRIVE TOOLS - create and trash files
    # Auto-disabled when no OneDrive connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_onedrive_file",
        description="Create a new file in Microsoft OneDrive",
        factory=lambda deps: create_create_onedrive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_onedrive_file",
        description="Move a OneDrive file to the recycle bin",
        factory=lambda deps: create_delete_onedrive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # GOOGLE CALENDAR TOOLS - create, update, delete events
    # Auto-disabled when no Google Calendar connector is configured
    # =========================================================================
    ToolDefinition(
        name="create_calendar_event",
        description="Create a new event on Google Calendar",
        factory=lambda deps: create_create_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_calendar_event",
        description="Update an existing indexed Google Calendar event",
        factory=lambda deps: create_update_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_calendar_event",
        description="Delete an existing indexed Google Calendar event",
        factory=lambda deps: create_delete_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # GMAIL TOOLS - create drafts, update drafts, send emails, trash emails
    # Auto-disabled when no Gmail connector is configured
    # =========================================================================
    ToolDefinition(
        name="create_gmail_draft",
        description="Create a draft email in Gmail",
        factory=lambda deps: create_create_gmail_draft_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="send_gmail_email",
        description="Send an email via Gmail",
        factory=lambda deps: create_send_gmail_email_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="trash_gmail_email",
        description="Move an indexed email to trash in Gmail",
        factory=lambda deps: create_trash_gmail_email_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_gmail_draft",
        description="Update an existing Gmail draft",
        factory=lambda deps: create_update_gmail_draft_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # JIRA TOOLS - create, update, delete issues
    # Auto-disabled when no Jira connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_jira_issue",
        description="Create a new issue in the user's Jira project",
        factory=lambda deps: create_create_jira_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_jira_issue",
        description="Update an existing indexed Jira issue",
        factory=lambda deps: create_update_jira_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_jira_issue",
        description="Delete an existing indexed Jira issue",
        factory=lambda deps: create_delete_jira_issue_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # CONFLUENCE TOOLS - create, update, delete pages
    # Auto-disabled when no Confluence connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_confluence_page",
        description="Create a new page in the user's Confluence space",
        factory=lambda deps: create_create_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="update_confluence_page",
        description="Update an existing indexed Confluence page",
        factory=lambda deps: create_update_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    ToolDefinition(
        name="delete_confluence_page",
        description="Delete an existing indexed Confluence page",
        factory=lambda deps: create_delete_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # CRYPTO REAL-TIME TOOLS - Hybrid approach (RAG + Real-time)
    # =========================================================================
    # These tools fetch LIVE data directly from DexScreener API.
    # Use alongside search_knowledge_base for comprehensive crypto analysis:
    # - search_knowledge_base: Historical context, trends (from indexed data)
    # - get_live_token_price: Current price (real-time API call)
    # - get_live_token_data: Full market data (real-time API call)
    ToolDefinition(
        name="get_live_token_price",
        description="Get LIVE/CURRENT cryptocurrency price from DexScreener API. Use for real-time price queries.",
        factory=lambda deps: create_get_live_token_price_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_live_token_data",
        description="Get comprehensive LIVE market data (price, volume, liquidity, transactions) from DexScreener API.",
        factory=lambda deps: create_get_live_token_data_tool(),
        requires=[],
    ),
    # =========================================================================
    # DEFILLAMA TOOLS — DeFi protocol data (TVL, yields, stablecoins, bridges)
    # Stateless / no auth required (NFR-CS4)
    # =========================================================================
    ToolDefinition(
        name="get_defillama_protocol",
        description="Get TVL, chain breakdown, market cap, and audit links for a DeFi protocol from DeFiLlama",
        factory=lambda deps: create_defillama_protocol_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_tvl_overview",
        description="Get top DeFi protocols ranked by Total Value Locked (TVL) from DeFiLlama",
        factory=lambda deps: create_defillama_tvl_overview_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_yields",
        description="Get DeFi yield pools sorted by APY from DeFiLlama Yields",
        factory=lambda deps: create_defillama_yields_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_stablecoins",
        description="Get top stablecoins ranked by market cap from DeFiLlama",
        factory=lambda deps: create_defillama_stablecoins_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_bridges",
        description="Get top cross-chain bridges ranked by 24h volume from DeFiLlama",
        factory=lambda deps: create_defillama_bridges_tool(),
        requires=[],
    ),
    # =========================================================================
    # CRYPTO SENTIMENT TOOLS — Fear & Greed + Reddit sentiment
    # Stateless / no auth required (NFR-CS4)
    # =========================================================================
    ToolDefinition(
        name="get_cmc_sentiment",
        description="Get the Crypto Fear & Greed Index for overall market sentiment from alternative.me",
        factory=lambda deps: create_cmc_sentiment_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_reddit_crypto_sentiment",
        description="Get Reddit community sentiment and post activity for a crypto symbol",
        factory=lambda deps: create_reddit_crypto_sentiment_tool(),
        requires=[],
    ),
    # =========================================================================
    # CRYPTO NEWS TOOLS — CryptoPanic news + CoinGecko token info
    # Stateless / no auth required for free tier (NFR-CS4)
    # =========================================================================
    ToolDefinition(
        name="get_crypto_news",
        description="Get latest cryptocurrency news and articles from CryptoPanic with sentiment signals",
        factory=lambda deps: create_crypto_news_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_coingecko_token_info",
        description="Get detailed token info, market data, supply, and social links from CoinGecko free tier",
        factory=lambda deps: create_coingecko_token_info_tool(),
        requires=[],
    ),
    # =========================================================================
    # CONTRACT ANALYSIS TOOLS — Block explorer + GoPlus security
    # Stateless; ETHERSCAN_API_KEY/BSCSCAN_API_KEY/POLYGONSCAN_API_KEY required (NFR-CS4)
    # =========================================================================
    ToolDefinition(
        name="get_contract_info",
        description="Get smart contract source code, ABI, and metadata from block explorers (Etherscan/BscScan/Polygonscan)",
        factory=lambda deps: create_contract_info_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="check_token_security",
        description="Run a security audit on a token contract using GoPlus Labs — detects honeypots, high taxes, and rug risks",
        factory=lambda deps: create_check_token_security_tool(),
        requires=[],
    ),
    # =========================================================================
    # NANSEN TOOLS — Smart-money wallet flows (Story 9-UX-4 AC1)
    # Requires NANSEN_API_KEY (paid tier). Gracefully returns 401 error if missing.
    # =========================================================================
    ToolDefinition(
        name="get_nansen_smart_money",
        description="Get Nansen smart-money wallet flows and accumulation signals for a token — top wallets, 24h net flow, accumulating/distributing signal",
        factory=lambda deps: create_nansen_smart_money_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_nansen_wallet_label",
        description="Get the Nansen label for a wallet address — identifies exchanges, funds, VCs, protocols (~200K known wallets)",
        factory=lambda deps: create_nansen_wallet_label_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_nansen_token_god_mode",
        description="Get holder distribution by cohort (smart money %, exchanges %, retail %, VCs %) and top-10 concentration for a token",
        factory=lambda deps: create_nansen_token_god_mode_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_smart_money_flow",
        description="Get smart money flow visualized as a Sankey diagram (nodes and links) representing 24h USD value flows. Use this for flow visualization instead of raw nansen tools.",
        factory=lambda deps: create_smart_money_flow_tool(),
        requires=[],
    ),
    # =========================================================================
    # CERTIK SKYNET TOOLS — Formal security audits (Story 9-UX-4 AC2)
    # Free public API tier (60 req/min). CERTIK_API_KEY optional for paid.
    # =========================================================================
    ToolDefinition(
        name="get_certik_audit_score",
        description="Get CertiK Skynet security score (0-100) and category breakdown for a token contract — cross-reference with GoPlus",
        factory=lambda deps: create_certik_audit_score_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_certik_incident_history",
        description="Get CertiK incident and hack history for a crypto project — exploits, rug pulls, flash loan attacks with financial impact",
        factory=lambda deps: create_certik_incident_history_tool(),
        requires=[],
    ),
    # =========================================================================
    # DUNE ANALYTICS TOOL — Custom on-chain queries (Story 9-UX-4 AC3)
    # Requires DUNE_API_KEY (Basic plan $99/mo). Gracefully returns 401 if missing.
    # =========================================================================
    ToolDefinition(
        name="run_dune_query",
        description="Execute a pre-registered Dune Analytics query for on-chain data — DEX volume, staking flows, whale concentration, NFT floors",
        factory=lambda deps: create_run_dune_query_tool(),
        requires=[],
    ),
    # =========================================================================
    # TOKENINSIGHT TOOLS — Third-party ratings (Story 9-UX-4 AC4)
    # Free tier for ratings; TOKENINSIGHT_API_KEY required for research snippets.
    # =========================================================================
    ToolDefinition(
        name="get_tokeninsight_rating",
        description="Get TokenInsight letter grade rating (A+/A/B/C/D/F) and score breakdown for a cryptocurrency — technology, team, ecosystem, tokenomics",
        factory=lambda deps: create_tokeninsight_rating_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_tokeninsight_research_snippet",
        description="Get the latest TokenInsight analyst research note excerpt for a token — investment thesis and analyst opinion",
        factory=lambda deps: create_tokeninsight_research_snippet_tool(),
        requires=[],
    ),
]


# =============================================================================
# Registry Functions
# =============================================================================


def get_tool_by_name(name: str) -> ToolDefinition | None:
    """Get a tool definition by its name."""
    for tool_def in BUILTIN_TOOLS:
        if tool_def.name == name:
            return tool_def
    return None


def get_all_tool_names() -> list[str]:
    """Get names of all registered tools."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS]


def get_default_enabled_tools() -> list[str]:
    """Get names of tools that are enabled by default (excludes hidden tools)."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS if tool_def.enabled_by_default]


def build_tools(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
) -> list[BaseTool]:
    """Build the list of tools for the agent.

    Args:
        dependencies: Dict containing all possible dependencies:
            - search_space_id: The search space ID
            - db_session: Database session
            - connector_service: Connector service instance
            - firecrawl_api_key: Optional Firecrawl API key
        enabled_tools: Explicit list of tool names to enable. If None, uses defaults.
        disabled_tools: List of tool names to disable (applied after enabled_tools).
        additional_tools: Extra tools to add (e.g., custom tools not in registry).

    Returns:
        List of configured tool instances ready for the agent.

    Example:
        # Use all default tools
        tools = build_tools(deps)

        # Use only specific tools
        tools = build_tools(deps, enabled_tools=["generate_report"])

        # Use defaults but disable podcast
        tools = build_tools(deps, disabled_tools=["generate_podcast"])

        # Add custom tools
        tools = build_tools(deps, additional_tools=[my_custom_tool])

    """
    # Determine which tools to enable
    if enabled_tools is not None:
        tool_names_to_use = set(enabled_tools)
    else:
        tool_names_to_use = set(get_default_enabled_tools())

    # Apply disabled list
    if disabled_tools:
        tool_names_to_use -= set(disabled_tools)

    # Build the tools (skip hidden/WIP tools unconditionally)
    tools: list[BaseTool] = []
    for tool_def in BUILTIN_TOOLS:
        if tool_def.hidden or tool_def.name not in tool_names_to_use:
            continue

        # Check that all required dependencies are provided
        missing_deps = [dep for dep in tool_def.requires if dep not in dependencies]
        if missing_deps:
            msg = f"Tool '{tool_def.name}' requires dependencies: {missing_deps}"
            raise ValueError(
                msg,
            )

        # Create the tool
        tool = tool_def.factory(dependencies)
        tools.append(tool)

    # Add any additional custom tools
    if additional_tools:
        tools.extend(additional_tools)

    return tools


async def build_tools_async(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
    include_mcp_tools: bool = True,
) -> list[BaseTool]:
    """Async version of build_tools that also loads MCP tools from database.

    Design Note:
    This function exists because MCP tools require database queries to load user configs,
    while built-in tools are created synchronously from static code.

    Alternative: We could make build_tools() itself async and always query the database,
    but that would force async everywhere even when only using built-in tools. The current
    design keeps the simple case (static tools only) synchronous while supporting dynamic
    database-loaded tools through this async wrapper.

    Args:
        dependencies: Dict containing all possible dependencies
        enabled_tools: Explicit list of tool names to enable. If None, uses defaults.
        disabled_tools: List of tool names to disable (applied after enabled_tools).
        additional_tools: Extra tools to add (e.g., custom tools not in registry).
        include_mcp_tools: Whether to load user's MCP tools from database.

    Returns:
        List of configured tool instances ready for the agent, including MCP tools.

    """
    import time

    _perf_log = logging.getLogger("nowing.perf")
    _perf_log.setLevel(logging.DEBUG)

    _t0 = time.perf_counter()
    tools = build_tools(dependencies, enabled_tools, disabled_tools, additional_tools)
    _perf_log.info(
        "[build_tools_async] Built-in tools in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    # Load MCP tools if requested and dependencies are available
    if (
        include_mcp_tools
        and "db_session" in dependencies
        and "search_space_id" in dependencies
    ):
        try:
            _t0 = time.perf_counter()
            mcp_tools = await load_mcp_tools(
                dependencies["db_session"],
                dependencies["search_space_id"],
            )
            _perf_log.info(
                "[build_tools_async] MCP tools loaded in %.3fs (%d tools)",
                time.perf_counter() - _t0,
                len(mcp_tools),
            )
            tools.extend(mcp_tools)
            logging.info(
                f"Registered {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}",
            )
        except Exception as e:
            # Log error but don't fail - just continue without MCP tools
            logging.exception(f"Failed to load MCP tools: {e!s}")

    # Log all tools being returned to agent
    logging.info(
        f"Total tools for agent: {len(tools)} - {[t.name for t in tools]}",
    )

    return tools
