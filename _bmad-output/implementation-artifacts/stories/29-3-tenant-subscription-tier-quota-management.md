---
story_key: 29-3-tenant-subscription-tier-quota-management
status: in-progress
baseline_commit: f3490b642
epic: 29
story: 3
---

# Story 29.3: Tenant Subscription Tier & Quota Management

**Status:** `in-progress`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-102, AR-17, UX-DR-PRFAQ-5, AD-8, AD-51, `spec-29-3-tenant-subscription-tier-quota-management.md`, `ux-contract-epic-29-saas-admin-analytics.md` §3 (PM-1..PM-6).  
**Dependencies:** Existing `Workspace`, `WorkspaceLimit`, `AuditEvent`, `SearchSourceConnector`, `Permission.SETTINGS_UPDATE`.

---

## Story

As a **superadmin or workspace Owner**,  
I want **multi-tenant subscription tier catalog management and self-serve upgrade/downgrade with quota conflict checks and 7-day reversible windows**,  
so that **workspaces can smoothly scale their resource limits with full safety, rollback capability, and audit traceability**.

---

## Acceptance Criteria

### AC-1 — Plan Catalog & Workspace Limit Expansion (PM-1, AD-8, AD-51)
**Given** the need for a multi-tier SaaS catalog,  
**When** plan definitions are stored and managed,  
**Then**:
1. `WorkspaceLimit` model expands with columns:
   - `max_monthly_credits`: BigInteger, nullable
   - `max_sources`: Integer, nullable
   - `support_level`: String(50), nullable
   - `price_micros`: BigInteger, nullable (currency amount in micros, AD-8)
   - `currency`: String(3), nullable, default 'USD'
2. `WorkspaceLimit` maintains XOR constraint: `plan_tier IS NOT NULL AND workspace_id IS NULL` for plan defaults; `workspace_id IS NOT NULL AND plan_tier IS NULL` for per-workspace overrides.
3. System default tiers seeded / updated: `free`, `team`, `growth`, `enterprise`.
4. Superadmin API `GET/POST/PUT/DELETE /admin/saas/plans` protected by `require_superuser`.
5. Grandfathering invariant: updating a plan default preserves existing limits for active workspaces on that tier via per-workspace snapshot overrides.

### AC-2 — Subscription Change State Machine & Safety Rails (PM-4, PM-5, PM-6, FR-102)
**Given** an authenticated workspace owner or user with `Permission.SETTINGS_UPDATE`,  
**When** `POST /workspaces/{id}/subscription-changes` is invoked with `to_plan`,  
**Then**:
1. `SubscriptionChange` model records: `id` (UUID), `workspace_id`, `from_plan`, `to_plan`, `effective_at`, `reversible_until`, `status` (`pending`, `active`, `cancelled`, `reverted`, `expired`), `initiated_by`, `payment_method_id`, `immediate`, `diff_payload`, `created_at`, `updated_at`.
2. **Quota Conflict Check:** before initiating a plan change, current usage (documents, members, runs, storage_bytes, memory_count, memory_bytes, sources) is validated against target plan limits. If any metric exceeds the new plan limit, HTTP `409 Conflict` is returned with a structured `conflicts` checklist.
3. **Grace Period & Reversibility:**
   - Default: `effective_at = now + 7 days`, `reversible_until = effective_at`, `status = "pending"`.
   - Immediate upgrade (`immediate=true`): `effective_at = now`, `reversible_until = now + 7 days`, `status = "active"`, and `Workspace.plan_tier` is updated immediately.
4. **Revert & Cancel Endpoints:**
   - `POST /workspaces/{id}/subscription-changes/{change_id}/revert`: within 7-day reversible window (`now <= reversible_until`), reverts `Workspace.plan_tier = from_plan`, marks status `reverted`, and audits the event.
   - `POST /workspaces/{id}/subscription-changes/{change_id}/cancel`: cancels a `pending` change, setting status `cancelled`.
5. **Audit Trail:** every subscription change creation, reversion, and cancellation creates an immutable `AuditEvent` with `diff_payload`.
6. **History Listing:** `GET /workspaces/{id}/subscription-changes` returns full chronological change history.

### AC-3 — UI Workflows (PM-1..PM-6)
**Given** the frontend web application,  
**Then**:
1. `/admin/saas/plans` renders the SaaS Plan Catalog table with system default badges, price/mo, limits, support level, and create/edit modal.
2. `/admin/admin-shell.tsx` includes navigation link to `SaaS Plans`.
3. `/dashboard/[workspace_id]/workspace-settings/limits` includes:
   - Current plan tier and "Change plan" button.
   - Plan comparison drawer/modal highlighting current plan.
   - Confirmation dialog showing 7-day default effective date, immediate toggle, and reversible period.
   - 409 Downgrade Conflict checklist modal highlighting metrics that exceed new limits.
   - Chronological subscription history with cancel and undo buttons where applicable.
