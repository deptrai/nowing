# BRIEFING — 2026-08-15T06:34:00Z

## Mission
Investigate Nowing backend and frontend architecture for Epic 21 (Lead Gen Intelligence) covering Outbound Prospecting Sequencer & Multi-Channel Delivery (21.4, 21.6), CRM Integration & Write-Back (21.5), Outcome-Based Pricing & ROI Tracking (21.7), and API Routes & Testing Patterns.

## 🔒 My Identity
- Archetype: explorer
- Roles: Teamwork explorer
- Working directory: /Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_explorer_survey_3
- Original parent: 50a7ac8d-3de4-4fdf-bf6c-27623b1509b7
- Milestone: Epic 21 Lead Gen Intelligence Architecture Survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Multi-channel delivery: Celery tasks, scheduling, sequence steps, rate limiting, channel adapters (Telegram, Email, Webhook, SMS)
- CRM sync: Bi-directional sync, HubSpot/Salesforce/Webhook adapter patterns, field mapping, conflict resolution, sync logs
- ROI / Billing: Workspace limits, token tracking, conversion attribution, ROI calculation, cost-per-lead / cost-per-conversion metering
- API routes structure and testing patterns (unit & integration)
- Tenancy AD-31 (`workspace_id` + optional `client_id`), Provenance AD-44/AD-47 (`source_uuid` + `source_entity_type`)

## Current Parent
- Conversation ID: 50a7ac8d-3de4-4fdf-bf6c-27623b1509b7
- Updated: 2026-08-15T06:34:00Z

## Investigation State
- **Explored paths**:
  - `nowing_backend/app/celery_app.py`, `app/automations/runtime/`, `app/automations/triggers/builtin/schedule/`, `app/automations/actions/builtin/`
  - `nowing_backend/app/gateway/` (`base/`, `telegram/`, `slack/`, `discord/`, `whatsapp/`, `ratelimit.py`)
  - `nowing_backend/app/services/` (`workspace_limits.py`, `token_tracking_service.py`, `billing_event_service.py`, `composio_service.py`, `connector_service.py`)
  - `nowing_backend/app/lead_intelligence/` (`signals/`, `scoring/`)
  - `nowing_backend/alembic/versions/` (198, 199 migrations)
  - `nowing_backend/app/routes/` (`lead_scoring_routes.py`, `signals_routes.py`, `__init__.py`, `app.py`)
  - `nowing_backend/tests/` (`unit/lead_intelligence/`, `integration/lead_intelligence/`, `unit/capabilities/test_billing.py`)
- **Key findings**:
  - Celery Beat + Automation Execution engine (`execute_run`, `execute_step`) provides a complete foundation for Outbound Sequencer.
  - Redis token-bucket rate limiter (`app/gateway/ratelimit.py`) with memory fallback is in place.
  - MCP write-back architecture (`write_back/shared.py`) handles connector resolution, tool discovery, parameter translation, and response normalization.
  - Dual ledger architecture: `TokenUsage` for LLM operations and `BillingEvent` for non-LLM business events with partial unique indexes (`ix_billing_events_signal_unique`, `ix_billing_events_outcome_unique`).
  - WorkspaceLimitService enforces limits with Postgres advisory transaction locks.
- **Unexplored areas**: None for survey scope.

## Key Decisions Made
- Mapped all 4 focus areas to concrete codebase patterns.
- Completed comprehensive `analysis.md` and `handoff.md`.

## Artifact Index
- `/Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_explorer_survey_3/analysis.md` — Detailed survey analysis
- `/Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_explorer_survey_3/handoff.md` — Handoff report
