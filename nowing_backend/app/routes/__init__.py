from fastapi import APIRouter, Depends

# Import verb namespaces for their registration side effects before the door builds.
import app.capabilities.amazon
import app.capabilities.batdongsan
import app.capabilities.cafef
import app.capabilities.chainlens
import app.capabilities.chotot
import app.capabilities.executive_move
import app.capabilities.funding
import app.capabilities.google_maps
import app.capabilities.google_search
import app.capabilities.hiring
import app.capabilities.indeed
import app.capabilities.instagram
import app.capabilities.itviec
import app.capabilities.masothue
import app.capabilities.muaban_bds
import app.capabilities.news
import app.capabilities.reddit
import app.capabilities.social
import app.capabilities.tech_stack
import app.capabilities.tiktok
import app.capabilities.topcv
import app.capabilities.vietnamworks
import app.capabilities.vn_bds
import app.capabilities.vn_jobs
import app.capabilities.walmart
import app.capabilities.web
import app.capabilities.youtube
import app.lead_intelligence.enrichment.capability
import app.lead_intelligence.scoring.capability  # noqa: F401
from app.automations.api import router as automations_router
from app.capabilities.core.access.rest import build_capabilities_router
from app.file_storage.api import router as file_storage_router
from app.gateway import require_gateway_enabled
from app.notifications.api import router as notifications_router
from app.podcasts.api import router as podcasts_router

from .admin_affiliates_routes import router as admin_affiliates_router
from .admin_agent_registry_routes import (
    router as admin_agent_registry_router,
)
from .admin_anti_bot_escalation_routes import (
    router as admin_anti_bot_escalation_router,
)
from .admin_audit_logs_routes import router as admin_audit_logs_router
from .admin_broadcasts_routes import router as admin_broadcasts_router
from .admin_credits_routes import router as admin_credits_router
from .admin_dnc_routes import router as admin_dnc_router
from .admin_global_model_connections_routes import (
    router as admin_global_model_connections_router,
)
from .admin_latency_routes import router as admin_latency_router
from .admin_scraper_platform_accounts_routes import (
    router as admin_scraper_platform_accounts_router,
    scraper_accounts_alias_router,
)
from .admin_scraper_rules_routes import router as admin_scraper_rules_router
from .admin_telemetry_routes import router as admin_telemetry_router
from .admin_users_routes import router as admin_users_router
from .agent_action_log_route import router as agent_action_log_router
from .agent_chat_routes import router as agent_chat_router
from .agent_flags_route import router as agent_flags_router
from .agent_permissions_route import router as agent_permissions_router
from .agent_revert_route import router as agent_revert_router
from .airtable_add_connector_route import (
    router as airtable_add_connector_router,
)
from .broadcasts_routes import router as broadcasts_router
from .chat_comments_routes import router as chat_comments_router
from .circleback_webhook_route import router as circleback_webhook_router
from .clickup_add_connector_route import router as clickup_add_connector_router
from .composio_routes import router as composio_router
from .confluence_add_connector_route import router as confluence_add_connector_router
from .crm_oauth_routes import router as crm_oauth_router
from .crm_routes import router as crm_router
from .discord_add_connector_route import router as discord_add_connector_router
from .dnc_routes import router as dnc_router
from .documents_routes import router as documents_router
from .dropbox_add_connector_route import router as dropbox_add_connector_router
from .editor_routes import router as editor_router
from .enrichment_routes import router as enrichment_router
from .export_routes import router as export_router
from .extract_entities_routes import router as extract_entities_router
from .folders_routes import router as folders_router
from .gateway_webhook_routes import (
    config_router as gateway_config_router,
    router as gateway_router,
)
from .gateway_whatsapp_baileys_routes import router as gateway_whatsapp_baileys_router
from .gateway_whatsapp_webhook_routes import router as gateway_whatsapp_webhook_router
from .google_calendar_add_connector_route import (
    router as google_calendar_add_connector_router,
)
from .google_drive_add_connector_route import (
    router as google_drive_add_connector_router,
)
from .google_gmail_add_connector_route import (
    router as google_gmail_add_connector_router,
)
from .image_generation_routes import router as image_generation_router
from .incentive_tasks_routes import router as incentive_tasks_router
from .jira_add_connector_route import router as jira_add_connector_router
from .lead_clipper_routes import router as lead_clipper_router
from .lead_pipeline_routes import router as lead_pipeline_router
from .lead_scoring_routes import router as lead_scoring_router
from .leads_routes import router as leads_router
from .linear_add_connector_route import router as linear_add_connector_router
from .logs_routes import router as logs_router
from .luma_add_connector_route import router as luma_add_connector_router
from .mcp_oauth_route import router as mcp_oauth_router
from .meeting_minutes_routes import router as meeting_minutes_router
from .memories_routes import router as memories_router
from .memory_routes import router as memory_router
from .model_connections_routes import router as model_connections_router
from .model_list_routes import router as model_list_router
from .new_chat_routes import router as new_chat_router
from .notes_routes import router as notes_router
from .notion_add_connector_route import router as notion_add_connector_router
from .obsidian_plugin_routes import router as obsidian_plugin_router
from .onedrive_add_connector_route import router as onedrive_add_connector_router
from .outbound_routes import router as outbound_router
from .outcome_pricing_routes import router as outcome_pricing_router
from .partner_routes import router as partner_router
from .personal_access_tokens_routes import router as personal_access_tokens_router
from .presentation_routes import router as presentation_router
from .promo_code_routes import router as promo_code_router
from .prompts_routes import router as prompts_router
from .public_chat_routes import router as public_chat_router
from .rbac_routes import router as rbac_router
from .reports_routes import router as reports_router
from .research_threads_routes import router as research_threads_router
from .sandbox_routes import router as sandbox_router
from .search_source_connectors_routes import router as search_source_connectors_router
from .sequence_routes import router as sequence_router
from .signals_routes import router as signals_router
from .slack_add_connector_route import router as slack_add_connector_router
from .social_copilot_routes import router as social_copilot_router
from .social_routes import router as social_routes
from .stripe_routes import router as stripe_router
from .team_memory_routes import router as team_memory_router
from .teams_add_connector_route import router as teams_add_connector_router
from .usage_routes import router as usage_router
from .video_presentations_routes import router as video_presentations_router
from .web_builder_routes import router as web_builder_router
from .workspace_tables_routes import router as workspace_tables_router
from .workspaces_routes import router as workspaces_router
from .youtube_routes import router as youtube_router
from .zns_routes import router as zns_router

router = APIRouter()

router.include_router(workspaces_router)
router.include_router(workspace_tables_router)
router.include_router(sequence_router)
router.include_router(outcome_pricing_router)
router.include_router(promo_code_router)
router.include_router(partner_router)
router.include_router(lead_scoring_router)
router.include_router(leads_router)
router.include_router(lead_clipper_router)
router.include_router(lead_pipeline_router)
router.include_router(dnc_router)
router.include_router(outbound_router)
router.include_router(zns_router)
router.include_router(enrichment_router)
router.include_router(crm_router, prefix="/workspaces")
router.include_router(crm_oauth_router)
router.include_router(rbac_router)  # RBAC routes for roles, members, invites
router.include_router(editor_router)
router.include_router(export_router)
router.include_router(documents_router)
router.include_router(folders_router)
_gateway_enabled_dep = [Depends(require_gateway_enabled)]
router.include_router(gateway_config_router)
router.include_router(gateway_router, dependencies=_gateway_enabled_dep)
router.include_router(
    gateway_whatsapp_webhook_router, dependencies=_gateway_enabled_dep
)
router.include_router(
    gateway_whatsapp_baileys_router, dependencies=_gateway_enabled_dep
)
router.include_router(notes_router)
router.include_router(new_chat_router)  # Chat with assistant-ui persistence
router.include_router(agent_revert_router)  # POST /threads/{id}/revert/{action_id}
router.include_router(agent_action_log_router)  # GET /threads/{id}/actions
router.include_router(
    agent_permissions_router
)  # CRUD for /workspaces/{id}/agent/permissions/rules
router.include_router(agent_flags_router)  # GET /agent/flags
router.include_router(agent_chat_router)  # Public agent-chat endpoints
router.include_router(sandbox_router)  # Sandbox file downloads (Daytona)
router.include_router(chat_comments_router)
router.include_router(podcasts_router)  # Podcast task status and audio
router.include_router(
    video_presentations_router
)  # Video presentation status and streaming
router.include_router(reports_router)  # Report CRUD and multi-format export
router.include_router(image_generation_router)  # Image generation via litellm
router.include_router(search_source_connectors_router)
router.include_router(signals_router, prefix="/workspaces")
router.include_router(social_routes)
router.include_router(social_copilot_router)
router.include_router(google_calendar_add_connector_router)
router.include_router(google_gmail_add_connector_router)
router.include_router(google_drive_add_connector_router)
router.include_router(airtable_add_connector_router)
router.include_router(linear_add_connector_router)
router.include_router(luma_add_connector_router)
router.include_router(notion_add_connector_router)
router.include_router(slack_add_connector_router)
router.include_router(teams_add_connector_router)
router.include_router(onedrive_add_connector_router)
router.include_router(obsidian_plugin_router)  # Obsidian plugin push API
router.include_router(personal_access_tokens_router)  # Personal access token manager
router.include_router(discord_add_connector_router)
router.include_router(jira_add_connector_router)
router.include_router(confluence_add_connector_router)
router.include_router(clickup_add_connector_router)
router.include_router(dropbox_add_connector_router)
router.include_router(
    admin_global_model_connections_router
)  # Platform admin global models
router.include_router(admin_agent_registry_router)  # Platform admin agent registry
router.include_router(
    admin_latency_router
)  # Platform admin ChainLens latency percentiles
router.include_router(admin_telemetry_router)  # Platform admin real-time telemetry
router.include_router(
    admin_scraper_platform_accounts_router
)  # Admin scraper platform credentials
router.include_router(admin_scraper_rules_router)  # Admin dynamic scraper rules
router.include_router(
    scraper_accounts_alias_router
)  # Admin scraper platform credentials alias (/admin/scraper-accounts)
router.include_router(
    admin_anti_bot_escalation_router
)  # Admin anti-bot / CAPTCHA escalations
router.include_router(admin_users_router)  # Admin users and impersonation
router.include_router(admin_affiliates_router)  # Admin affiliate partner payout desk
router.include_router(admin_credits_router)  # Manual credit adjustments
router.include_router(
    admin_audit_logs_router
)  # Platform admin audit trail logs (Story 25.6)
router.include_router(
    admin_dnc_router
)  # Platform admin global DNC blacklist (Story 25.6)
router.include_router(
    admin_broadcasts_router
)  # Platform admin broadcast management (Story 25.6)
router.include_router(
    broadcasts_router
)  # In-app active broadcast announcements (Story 25.6)
router.include_router(model_connections_router)  # Connection-centric model catalog
router.include_router(model_list_router)  # Dynamic model catalogue from OpenRouter
router.include_router(logs_router)
router.include_router(circleback_webhook_router)  # Circleback meeting webhooks
router.include_router(notifications_router)  # Notifications with Zero sync
router.include_router(
    mcp_oauth_router
)  # MCP OAuth 2.1 for Linear, Jira, ClickUp, Slack, Airtable
router.include_router(composio_router)  # Composio OAuth and toolkit management
router.include_router(public_chat_router)  # Public chat sharing and cloning
router.include_router(incentive_tasks_router)  # Incentive tasks for earning free pages
router.include_router(stripe_router)  # Stripe checkout for additional page packs
router.include_router(usage_router)  # Usage and credit dashboard
router.include_router(youtube_router)  # YouTube playlist resolution
router.include_router(prompts_router)
router.include_router(memories_router)  # Structured memory CRUD/search
router.include_router(
    research_threads_router
)  # Research-thread continuity context (4.6)
router.include_router(memory_router)  # User personal memory (memory.md style)
router.include_router(team_memory_router)  # Workspace team memory
router.include_router(automations_router)  # Automations CRUD + run history
router.include_router(file_storage_router)  # Original file metadata + download
router.include_router(extract_entities_router)  # Test entity extraction (AC-1 / AD-107)
router.include_router(
    web_builder_router
)  # Full-stack Web App Builder (Story 27.1 / AD-113)
router.include_router(presentation_router)  # Presentation Studio (Story 27.2a)
router.include_router(meeting_minutes_router)  # Meeting Minutes (Story 27.2b)

router.include_router(build_capabilities_router())  # Scraper-API capability doors (05)
