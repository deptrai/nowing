// AUTO-GENERATED from nowing_backend/app/schemas/stripe.py:PlanId
// DO NOT EDIT — regenerate via `pnpm gen:plan-ids` (or python3 scripts/generate_plan_ids.py)
// CI drift check: pnpm verify:plan-ids
// Reference: ADR-012 (Entitlement Plan IDs Single Source of Truth)

export const PRO_PLANS = ["pro_monthly", "pro_yearly", "max_monthly", "max_yearly"] as const;

export type ProPlan = (typeof PRO_PLANS)[number];
