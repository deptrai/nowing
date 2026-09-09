---
story_key: 21-8e-per-account-proxy-cookie-binding
status: done
epic: 21
story: 8e
---

# Story 21.8e: Per-Account Proxy and Cookie Binding

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-3, AD-SOC-11  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a sales development representative,  
I want each target to use its own XActions account and proxy,  
so that scraping is resilient to blocks and follows platform policies.

---

## Acceptance Criteria

1. **Target-Level Account/Proxy** — **Given** a target with `account_id` and `proxy_url`, **When** scheduler runs, **Then** XActions is called with those values.
2. **Fallback Account** — **Given** no target-level account, **When** scheduler runs, **Then** it falls back to `XACTIONS_FACEBOOK_ACCOUNT_ID` or `x_facebook_list_accounts`.
3. **Per-Workspace Binding** — **Given** per-workspace account/proxy binding, **When** persisted, **Then** it is stored in `xactions_proxy_bindings` with `UNIQUE (workspace_id, account_id, platform)`.

---

## Tasks / Subtasks

- [x] Task 1: Schema changes
  - [x] 1.1 Add `account_id` column to `social_monitored_targets`.
  - [x] 1.2 Add `xactions_proxy_bindings` table via `XActionsProxyBinding` model.
  - [x] 1.3 Create Alembic migration(s).
- [x] Task 2: Scheduler wiring
  - [x] 2.1 In `ingest_social_target_task`, inject `accountId`/`proxyUrl` from target.
  - [x] 2.2 Implement fallback to `XACTIONS_FACEBOOK_ACCOUNT_ID` or `x_facebook_list_accounts` (only if `XACTIONS_MODE=local`).
- [x] Task 3: Schemas and routes
  - [x] 3.1 Update `SocialTargetCreate`/`SocialTargetRead` schemas to include `account_id`/`proxy_url`.
  - [x] 3.2 Update validation in `social_routes.py`.
- [x] Task 4: Tests
  - [x] 4.1 Unit tests for fallback logic.
  - [x] 4.2 Integration tests for proxy binding persistence.

---

## Dev Notes

- Remote mode requires explicit `account_id`; do not call `x_facebook_list_accounts` in remote mode.
- Proxy binding must be workspace-scoped for multi-tenancy.
- AD-SOC-3 requires sticky 1-to-1 residential proxy IP binding per account.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py]
- [Code: nowing_backend/app/models/leads/social.py]
