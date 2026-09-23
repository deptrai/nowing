---
story_key: 37-7-hybrid-pricing-packaging-ui-and-auto-refund-guarantee-sla
status: done
baseline_commit: b61846a657bf99fcb2f88a5508a775c05247c51d
epic: 37
priority: P0
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-121, AD-110]
---

# Story 37.7: Hybrid Pricing Packaging UI & Auto-Refund Guarantee SLA

**Status:** `done`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P0  
**Target Codebase:** `nowing_backend`, `nowing_web`  
**Architectural Alignment:** Extends `/dashboard/[workspace_id]/buy-tokens`, `app/services/wallet_credit.py`, and Phone Waterfall engine.

## Story

As a Platform Administrator and Customer,  
I want the web dashboard to display transparent hybrid pricing tiers (Starter, Professional, Business) with instant VietQR checkout and an automated refund guarantee for invalid contacts,  
So that pricing matches local willingness-to-pay and eliminates buyer hesitation.

## Acceptance Criteria

- **AC-1 (Hybrid Tier Packaging UI):** Renders Starter (990.000đ/tháng, 1.000 credits), Professional (2.490.000đ/tháng, 3.500 credits, 3 seats, highlighted), and Business (5.990.000đ/tháng, 10.000 credits, unlimited seats) with an interactive credit calculator slider on `/dashboard/[workspace_id]/buy-tokens`.
- **AC-2 (VietQR Dynamic Checkout):** Generates VietQR dynamic transfer modal with a 10-minute countdown, automatically crediting the wallet within 5 seconds of Napas bank transfer webhook receipt.
- **AC-3 (Objective Technical Refund SLA - AD-121):** If an unlocked phone number programmatically returns `ZALO_USER_NOT_FOUND` or `TELCO_NUMBER_UNALLOCATED`, the full credits deducted for that resolution are refunded immediately with an audited ledger entry `credit_refund_invalid_contact`. *(Resolved: spec said "10 credits"; the actual charge is `PHONE_RESOLUTION_COST_MICROS` = 150 credits — implementation refunds the real deducted amount.)*
- **AC-4 (Refund Circuit Breaker - AD-110):** Enforces a monthly auto-refund volume cap of 15% of total unlocked leads per workspace; excess requests route to the manual Admin Desk.

## Review Triage Log

3-layer parallel review (blind / edge-case / verification-gap) on the
implementation diff → ~55 raw findings, ~20 unique after dedup.

### Patched (17 groups)

- **Webhook secret gate**: publicly-known `test_webhook_secret_key_123`
  default + `VIETQR_TOPUP_ENABLED` default TRUE let anyone forge signed
  webhooks and credit arbitrary wallets → webhook refuses fulfilment when
  secret unset/placeholder (503 `webhook_unconfigured`); feature flag now
  defaults FALSE like sibling payment flags.
- **Amount verification**: `_extract_amount_vnd=None` previously skipped the
  underpayment check and credited the full grant → `amount_unknown` keeps
  the intent PENDING for corrected delivery; zero/empty candidate keys no
  longer shadow later keys.
- **Late-transfer race**: lazy poll flip PENDING→FAILED made real money
  uncreditable → new `CreditPurchaseStatus.EXPIRED` (migration 241),
  conditional `UPDATE ... WHERE status='pending'`, webhook credits
  PENDING+EXPIRED (funds arrived = we owe the balance).
- **Self-service refund abuse**: `phone-verification-result` was gated by
  workspace `LEADS_WRITE` — any member could claim `ZALO_USER_NOT_FOUND`
  and refund while keeping the phone → now `require_superuser`.
- **Exact-log refunds**: `resolve_admin_desk_refund` re-selected the latest
  log for the lead — approving entry X could refund a newer charge while X
  stayed queued forever → `waterfall_log_id` param; admin desk + waterfall
  both pin the exact row.
- **Wrong-wallet credits**: payer lookup could match desk-marker events and
  fell back to `user_id` (the admin on the desk path) → constrained to
  `event_type="contact_enrichment"` + `created_at asc`; desk passes
  `user_id=None`; unresolved payer → `refund_review`, never a credit-less
  `refunded` row; approve persists `approved_by:{admin}` + note.
- **Cap race**: concurrent refunds on different leads both passed the 15%
  count check → per-workspace `pg_advisory_xact_lock` (sha256-keyed) before
  re-reading counts.
- **Free micros**: `commit_reserved_credit` failure was swallowed but
  auto-refund still credited → `charge_committed` flag gates the hook.
- **Dead-number caching**: `refund_review`/`refund_error` still wrote the
  30-day Redis cache → cache write now gated on `refund_status is None`.
- **Error-code false positives**: `str(payload).upper()` substring scan
  fired on `ZALO_USER_NOT_FOUND_RESOLVED` etc. → word-boundary regex.
- **Status contract**: undocumented `"refunded"` top-level status reverted
  to `"success"`; `refund_status` carries the outcome.
- **Intent validation**: `tier_id`+`amount_vnd` both → 400; non-positive
  `VIETQR_VND_PER_USD` → ValueError; memo-collision `IntegrityError` →
  retry×3; missing user row → FAILED not stuck-PENDING.
- **workspace_id honored**: `RequirePermissionFromBody(BILLING_READ)`
  verifies membership on the claimed workspace.
- **Modal**: polling keyed on live polled status (was frozen prop → polled
  forever); `onCompleted` fires once per intent (was re-toasting every
  tick); clipboard `.catch` toast; unparseable `expires_at` → expired,
  never `NaN:NaN`; bank name from API (was hardcoded Vietcombank vs env BIN).
- **Pricing UI**: duplicated hardcoded `VND_PER_USD` → `vnd_per_usd` in the
  pricing-tiers response; error/empty tier-grid state; `/buy-more` Stripe
  link restored (card-payment entry point had been removed).
- **Admin Desk list**: SQL `count()`+`LIMIT/OFFSET`; nullable-tolerant
  `provider_used`/`tier_reached`.
- **Missing tests added**: waterfall-level refund e2e (code in raw_response
  → refunded + cache skipped), refund_review cache-skip, charge-commit
  failure skips refund, desk approve refunds exact log + original payer,
  expired-intent webhook credit, secret refusal, param validation.

### Rejected

- Cap numerator counting `lead_refund`/`contact_unlock_refund` alongside
  `credit_refund_invalid_contact` — kept: manual-path refunds consuming the
  auto budget is conservative (bounded), never over-permissive. Commented.

### Deferred

- `auto_refund_lead` (24h manual-report path) is uncapped while feeding the
  cap counter — global-cap semantics across refund paths is a product call.
- Spec says "10 credits"; actual charge is `PHONE_RESOLUTION_COST_MICROS`
  = 150 credits — code refunds the real deducted amount; reconcile wording.
- Real Napas aggregator webhook E2E needs sandbox credentials.
- Browser verification of `/buy-tokens` tiers + VietQR modal pending.
