# Epic 25 Context: Platform Administration & Multi-Tenant Operations

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Provide platform superadmins and operations staff with a secure, centralized control plane to oversee multi-tenant workspaces, conduct short-lived support impersonation with strict privilege stripping, execute atomic manual credit adjustments, audit and dispatch affiliate payouts, monitor real-time AI token costs and operational margins, update scraper extraction rules dynamically without redeployment, maintain Decree 13 audit and DNC compliance trails, and monitor third-party service health across all integrations.

## Stories

- Story 25.1: Multi-Tenant User & Workspace Hub + Scoped Impersonation
- Story 25.2: Manual Credit Adjustment & Refund Desk with Dual-Audit Ledger
- Story 25.3: Affiliate Partner Payout Desk & Anti-Fraud Engine
- Story 25.4: Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry
- Story 25.5: Dynamic Scraper Rule Engine & ReDoS Sandbox
- Story 25.6: Security Audit Trail Logs & In-App Broadcast Announcements
- Story 25.7: Third-Party Health & Operations Dashboard

## Requirements & Constraints

- All `/admin/*` and `/api/v1/admin/*` endpoints strictly require superadmin validation (`User.is_superuser == True`). Personal Access Tokens (PAT) must be rejected fail-closed.
- Impersonation sessions must generate a separate short-lived JWT (TTL <= 15 minutes) with stripped superadmin privileges. Forbidden actions during impersonation return HTTP 403: password reset, email modification, account deletion, API key access, nested impersonation, and admin route access.
- Every admin action and impersonated request must write append-only audit records to `audit_events` capturing both the acting admin (`actor_id`) and the impersonated user or target entity (`subject_id`), along with IP, user agent, endpoint, and diff payload for Decree 13 compliance.
- Manual credit adjustments require a mandatory `Idempotency-Key` header, a reason (minimum 10 characters), and an external ticket reference. Concurrency is controlled via a two-tier lock (Redis Redlock + Postgres `SELECT FOR UPDATE` on `workspace_wallets`).
- Support staff credit adjustments must enforce daily spending thresholds ($10 / 1,000 credits/day), escalating higher amounts to manager approval.
- Affiliate payout requests must pass fraud evaluation (self-referral ring detection, bank account name matching against Napas gateway) and compute mandatory 10% PIT tax deductions for requests >= 2,000,000 VND. Approved payouts execute idempotently over VietQR Napas 24/7.
- Scraper rule updates (CSS selectors, delays, retries) must validate selector syntax via `cssselect.parse` and pass a ReDoS benchmark sandbox enforced by `google-re2` with a hard timeout of 50ms (HTTP 422 if exceeded).
- Active scraper rule changes must publish via Redis Pub/Sub (`scraper_config_updated`) so Celery workers refresh in-memory configurations in under 1 second without pod restarts, with automated fallback if worker error rates exceed 20%.
- Global Do-Not-Call (DNC) blacklist additions must propagate immediately to runtime caches, suppressing outbound scraping and outreach system-wide.
- Real-time gross margin calculation `(revenue - cogs) / revenue` must correlate billed credit purchases against actual provider LLM token expenses (OpenAI, Anthropic, Google, DeepSeek) with visual alerts for negative margins.
- Third-party health probes must remain read-only (never auto-disabling integrations) with category-specific probe intervals (30s infrastructure, 2m LLM, 5m scrapers/messaging/payments/storage, 15m connectors) and bounded concurrency (`asyncio.Semaphore(20)`).

## Technical Decisions

- **Admin Auth & Middleware:** Gated by `require_superuser`. Impersonation sessions run through `ImpersonationGuardMiddleware`, which detects `is_impersonation: true` in token claims, overrides context user to the target, strips superuser status, and blocks sensitive mutations.
- **Audit Logging:** Unified `audit_events` table with dual-principal columns (`actor_id`, `subject_id`, `impersonation_session_id`, `action`, `endpoint`, `origin_ip`, `user_agent`, `diff_payload`).
- **Credit Concurrency:** `ManualCreditAdjustmentService` acquires `lock:workspace_wallet:{workspace_id}` (10s TTL) in Redis, then executes transactional Postgres `SELECT ... FOR UPDATE` on `workspace_wallets`, inserting into `credit_transactions` and updating balances atomically.
- **Affiliate Fraud & Payout:** `AffiliateAntiFraudService` uses recursive CTEs over referral and purchase timelines to flag self-referral rings (`risk_score >= 70`). `PartnerPayoutService.execute_payout_with_lock` acquires `lock:payout:{payout_id}` and dispatches to `VietQRPayoutClient` with deterministic idempotency keys. Final settlement transitions via webhook to update hold and total paid balances.
- **Dynamic Scraper Rules:** Versioned platform rules stored in Postgres `JSONB` keyed by `(platform, version)`. Worker cache invalidation orchestrated via Redis Pub/Sub channel `scraper_config_updated`. Emergency circuit breaker toggles stored in Redis and database.
- **Health Architecture:** Encapsulated in `app/services/health/` (`ThirdPartyHealthService`, `HealthProbeScheduler`, `HealthProbeRegistry`, `HealthResultStore`, `AdminHealthAlertEngine`). Uses a two-tier data model: Redis for latest status cache and pub/sub events (`nowing:health:updates`), Postgres tables `admin_health_status`, `admin_health_history`, `admin_health_alert_rules`, and `admin_health_alerts`. Reuses the Generic Alert Engine (`app/alerts/`) for alert scheduling, diffing, and dispatch (email, Slack, Telegram, in-app).

## UX & Interaction Patterns

- **Admin Surface:** Root-level `/admin/*` routes separate from workspace dashboards, styled with high-density components (36px row height, monospace identifiers, compact status pills).
- **Impersonation State:** Persistent 40px amber warning hazard banner fixed at `z-[9999]` with remaining countdown timer, keyboard shortcut `Esc` for immediate exit, and an enclosing 4px amber viewport outline around the entire screen.
- **Telemetry & Health Center:** `/admin/telemetry` provides category tab navigation (Overview, Infrastructure, LLM/AI, Scrapers, Connectors, Messaging, Payments, Storage), a top Active Alerts banner with 1-click acknowledge, Recharts latency/error-rate trends, and log inspection drawers.
- **Payout & Credit Desks:** Risk indicator pills (`🟢 Low 0-29`, `🟡 Mid 30-69`, `🔴 High 70-100`), bank name validation tags (`100% Match` vs `Name Mismatch`), and confirmation dialogs with mandatory justification fields.
- **Audit & Blacklist Controls:** Filterable timeline tables supporting CSV/JSON exports, payload inspection drawers, and bulk CSV upload dialogs for DNC exclusions.
- **Global Broadcasts:** Superadmin broadcast banner editor supporting emergency maintenance or promotional notices rendered directly atop `/dashboard/*` via zero-cache real-time push.

## Cross-Story Dependencies

- **Story 25.1** establishes the baseline `require_superuser` guard, admin session context, and `ImpersonationGuardMiddleware` relied upon by all subsequent admin features.
- **Story 25.2** sets the 2-tier locking, idempotency pattern, and audit logging standards applied in Story 25.3 (Affiliate Payouts).
- **Story 25.4** establishes basic LLM token and queue telemetry metrics that **Story 25.7** integrates and expands into comprehensive third-party health monitoring.
- **Story 25.5** dynamic rule and circuit-breaker states are surfaced in the Story 25.7 health probes and dashboard.
- **Story 25.6** audit event schema and global DNC blacklist records provide data for Story 25.1 impersonation logs, Story 25.2 adjustments, and downstream outbound systems (Epic 24 & Epic 26).
- **Story 25.7** reuses `CapabilityRegistry` for target discovery, `model_connection_service` (Story 8.11) for model verification, `admin_telemetry_service` for proxy/worker status, `hybrid_llm_router` (Story 26.3) for local vLLM probes, and Generic Alert Engine (Story 6.8) for notification delivery.
