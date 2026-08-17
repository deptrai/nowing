# UX Contract — Service-to-Service Auth + Cost Ledger Sync

**Date:** 2026-08-09  
**Scope:** Cross-project trust boundary between Nowing and `chainlens-research`: service token rotation, cost ledger sync, and workspace-level chainlens usage visibility.  
**Binds to:** FR-61 · AD-8 · AD-15 · AD-34 · AD-35 · Story 20.4  
**Document type:** *contract* — behavior the UI/API must support, not layout/color.

---

## 1. Problem

Nowing and `chainlens-research` must authenticate each other, attribute costs to the right workspace, and let workspace admins see chainlens usage in real dollars. Token rotation must be automatic; token failures must be visible but must not send user data with an invalid token.

## 2. Contract — Required UI/API States

### 2A. Service Auth Admin

| # | State | Required |
|---|-------|----------|
| A1 | **Admin panel** (`/admin/chainlens-service-auth`) shows current service token status (active, expiring, rotation failed) | ✅ |
| A2 | **Token metadata visible:** token kind, expiry/rotation date, last rotation, status, correlation-id prefix | ✅ |
| A3 | **Rotation log** with timestamp, reason (pre-expiry / 401 from engine), success/failure, and error message | ✅ |
| A4 | **Manual rotate button** (superuser) with confirmation; logs a warning | ✅ |
| A5 | **Alert banner** when `chainlens_auth_failed` counter fires or token rotation fails | ✅ |

### 2B. Outbound Request Headers

| # | State | Required |
|---|-------|----------|
| B1 | Every Nowing → `chainlens-research` request carries `Authorization: Bearer <service-token>`, `X-Correlation-Id`, `X-Workspace-Id` | ✅ |
| B2 | `X-Correlation-Id` is traceable in the workspace usage dashboard | ✅ |
| B3 | `X-Workspace-Id` scopes the request to one workspace; engine validates it | ✅ |

### 2C. Inbound Request Auth

| # | State | Required |
|---|-------|----------|
| C1 | `chainlens-research` → Nowing calls (`POST /v1/private-data/search`, `POST /v1/scraper/{scraper_id}/run`) require `Authorization: Bearer <service-token>` | ✅ |
| C2 | Missing or invalid token → `401` with no workspace data returned | ✅ |
| C3 | Valid token is mapped to the target `workspace_id` and token usage is recorded | ✅ |

### 2D. Cost Ledger Sync UI

| # | State | Required |
|---|-------|----------|
| D1 | **Workspace usage dashboard** shows `chainlens_search`, `chainlens_gap_fill`, `chainlens_ingest`, `chainlens_private_search` cost in real dollars (from `costDollars`) | ✅ |
| D2 | Each row shows `usage_type`, `resolved_mode` (for research), `workspace_id`, `run_id`/`correlation_id`, and `cost_micros` | ✅ |
| D3 | **Deep-research cost** is not a flat rate; dashboard falls back to a warning + env fallback rate only when `costDollars` is missing | ✅ |
| D4 | **Cost breakdown by operation** is filterable by day/week/month and by `usage_type` | ✅ |
| D5 | **Cost per correlation id** is queryable for support / debugging | ✅ |

### 2E. Token Rotation & Failure

| # | State | Required |
|---|-------|----------|
| E1 | Token rotates automatically within 30 days of expiry or on a `401` from `chainlens-research` | ✅ |
| E2 | In-flight requests are not dropped during rotation (lock + re-fetch) | ✅ |
| E3 | If rotation fails, outbound calls fail open with `service_auth_unavailable`; UI shows an amber alert and `chainlens_auth_failed` counter | ✅ |
| E4 | No user data is sent with an invalid or rotated-out token | ✅ |

## 3. Technical UX Constraints

- **Cost source of truth:** `costDollars` from the SSE terminal `done` frame, converted to `cost_micros` with `Decimal(cost_dollars) * 1_000_000` half-up (`AD-8`, Story 20.4).
- **Fallback rate:** `CHAINLENS_QUERY_MICROS_PER_CALL` is a fallback only and must log a warning when used (`AD-8`, `app/config/__init__.py:806`).
- **Token lifecycle:** Service token is a single Nowing ↔ ChainLens credential, not per-user; stored in Postgres (encrypted) or secret store (`Story 20.4` Dev Notes).
- **Correlation:** `X-Correlation-Id` is the public trace key; `run_id` links `TokenUsage` to `Run`.
- **No public corpus in Nowing:** `chainlens-research` owns the canonical index; Nowing only pushes `Chunk[]` and answers private-data queries (`AD-34`, `AD-35`).

## 4. Source Citations

- `prd.md:495-505` — FR-61 cross-project service auth & cost allocation
- `epics.md:2327-2358` — Story 20.4 service-to-service auth + cost ledger sync
- `ARCHITECTURE-SPINE.md:218-226` — AD-8 unified credit wallet; cost from service, not flat rate
- `ARCHITECTURE-SPINE.md:294-297` — AD-15 ChainLens is external deep-research dependency
- `ARCHITECTURE-SPINE.md:706-715` — AD-34 scraper feed contract
- `ARCHITECTURE-SPINE.md:717-724` — AD-35 Nowing does not build public/vertical search corpus
- `20-4-service-to-service-auth-cost-ledger-sync.md` — implementation story for service auth and cost ledger
- `ux-contract-usage-dashboard.md` — workspace usage dashboard baseline

## 5. Traceability

- Blocks: Story 20.4, Story 9.2, Story 18.7
- Related: `ux-contract-private-data-provider.md` (inbound private search), `ux-contract-async-deep-research.md` (async deep research cost and mode)
