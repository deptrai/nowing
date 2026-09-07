# Epic 29 Context: SaaS Operations, Advanced Admin Governance & Analyst Workspace

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 29 nâng cấp Nowing từ vận hành single-tenant lên SaaS operations console: superadmin quản lý workspace/tenant, subscription tier/quota, bulk operations, audit; owner/admin/analyst có dashboard health/adoption và memory browser/research timeline.

## Stories

- Story 29.1: Custom Workspace Roles & Permissions Builder
- Story 29.2: Workspace Health & Adoption Analytics Dashboard
- Story 29.3: Tenant Subscription Tier & Quota Management
- Story 29.4: Admin Bulk Operations Console
- Story 29.5: Memory Browser & Research Timeline for Analyst
- Story 29.6: Data Governance & Retention Policy Console

## Requirements & Constraints

- FR-100: Custom workspace roles with Owner ceiling guard; no `Admin` system role.
- FR-101: Health dashboard with pre-aggregated metrics and quota CTA.
- FR-102: Plan tier/quota directory, reversible upgrades/downgrades, trial handling, idempotency for bulk ops.
- FR-103: Bulk operations console with dry-run, structured filters, job polling, audit trail.
- FR-104: Memory browser with workspace-scoped queries and review queue.
- AR-17 / AR-18: SaaS admin operations console and auditability traceability for all admin actions.
- NFR-1 / NFR-2 / NFR-5: Performance, correctness, and security gates apply.

## Technical Decisions

- `WorkspaceLimit` plan definitions use `plan_tier` with `workspace_id IS NULL`; per-workspace overrides use `workspace_id` with `plan_tier IS NULL` (XOR constraint).
- `subscription_change` table records `from_plan`, `to_plan`, `effective_at`, `status`, `initiated_by`, `payment_method_id`, `immediate`, `reversible_until`.
- Default `effective_at` is now + 7 days; immediate only with explicit `immediate=true` and no quota conflicts.
- Downgrade with usage exceeding new limits returns `409 Conflict` with a remediation checklist.
- `WorkspaceLimit` expands columns `max_monthly_credits`, `max_sources`, `support_level`, `price_micros`, `currency` (default `USD`).
- Quota enforcement hooks into memory creation, member invite, source enable; proration credits daily against `credit_micros_balance`.
- Trial end cron converts workspace to `Free`, suspends new writes if over quota, and notifies owner with 72h grace period.
- Existing active workspaces keep grandfathered limits when a plan definition changes.

## UX & Interaction Patterns

- Superadmin plan catalog at `/admin/saas/plans` with system-default badge and editable limits/pricing.
- Workspace billing settings at `/dashboard/[workspace_id]/settings/billing` (or `/saas/billing`) showing current plan, plan comparison, and change plan flow.
- Plan comparison table highlights current plan and upgrade/downgrade options.
- Downgrade conflict dialog lists memory count, member count, source count, credit usage exceeding new limits.
- Change confirmation dialog shows `effective_at` default 7 days, `immediate` checkbox, and `reversible_until`.
- Subscription history lists `from_plan`, `to_plan`, `status`, `effective_at`.

## Cross-Story Dependencies

- Story 29.1 (custom roles) must ship before Story 29.4 bulk `assign_role`.
- Story 29.3 (tier/quota) must ship before Story 29.4 bulk `apply_tier`.
- Epic 1 (auth/RBAC), Epic 3 (memory schema), Epic 8 (billing/cost/wallet), Epic 25 (admin baseline), Epic 28 (retention/right-to-delete) are cross-epic dependencies.
