/**
 * Pro entitlement checks shared across UI components.
 *
 * Single source of truth for "is this user entitled to Pro features right now".
 * Mirrored loosely on `nowing_backend/app/db.py:SubscriptionStatus` enum
 * (FREE | ACTIVE | CANCELED | PAST_DUE) — keep this list in sync if backend
 * adds new states.
 *
 * Round-1 review fixes (2026-05-02):
 * - Honour `subscription_current_period_end`: a user who clicks "cancel" keeps
 *   their paid features through the end of the current billing period even
 *   though Stripe flips status to "canceled" immediately.
 * - `is_superuser` bypass moved into this helper so consumers don't have to
 *   re-implement the check.
 * - Removed `"trialing"` (backend enum doesn't emit it).
 * - Tightened types to accept `null` (matches contracts/types/user.types.ts).
 *
 * Story 11.6 fix (2026-05-02 / ADR-012):
 * - PRO_PLANS list is now generated from BE `PlanId` enum at build time
 *   (`scripts/generate_plan_ids.py`). Edit BE schema, not this file.
 *   CI fails if generated file drifts from BE source.
 */

import { PRO_PLANS, type ProPlan } from "./generated/plan-ids";

export { PRO_PLANS };
export type { ProPlan };

export interface EntitlementUser {
	plan_id?: string | null;
	subscription_status?: string | null;
	subscription_current_period_end?: string | null;
	is_superuser?: boolean | null;
}

export function isProPlan(planId: string | null | undefined): boolean {
	if (!planId) return false;
	return (PRO_PLANS as readonly string[]).includes(planId);
}

/**
 * "Active" means the subscription is currently good to use.
 *
 * `canceled` is intentionally allowed *if* the current paid period hasn't
 * elapsed yet — Stripe sets status=canceled the moment the user clicks cancel,
 * but they retain access through `subscription_current_period_end`.
 */
export function isSubscriptionActive(
	status: string | null | undefined,
	periodEnd?: string | null,
): boolean {
	if (status === "active") return true;
	if (status === "canceled" && periodEnd) {
		const end = Date.parse(periodEnd);
		if (!Number.isNaN(end) && end > Date.now()) return true;
	}
	return false;
}

/**
 * Unified Pro-entitlement check. Returns true for:
 *   - superusers (bypass for staff/admin)
 *   - users on a Pro plan with an active subscription
 *   - users who cancelled but haven't hit period_end yet
 */
export function hasProEntitlement(user: EntitlementUser | null | undefined): boolean {
	if (!user) return false;
	if (user.is_superuser) return true;
	return (
		isProPlan(user.plan_id) &&
		isSubscriptionActive(user.subscription_status, user.subscription_current_period_end)
	);
}
