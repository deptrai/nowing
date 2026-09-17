---
story_key: 37-7-hybrid-pricing-packaging-ui-and-auto-refund-guarantee-sla
status: ready-for-dev
epic: 37
priority: P0
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-121, AD-110]
---

# Story 37.7: Hybrid Pricing Packaging UI & Auto-Refund Guarantee SLA

**Status:** `ready-for-dev`  
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
- **AC-3 (Objective Technical Refund SLA - AD-121):** If an unlocked phone number programmatically returns `ZALO_USER_NOT_FOUND` or `TELCO_NUMBER_UNALLOCATED`, the 10 credits deducted are refunded immediately with an audited ledger entry `credit_refund_invalid_contact`.
- **AC-4 (Refund Circuit Breaker - AD-110):** Enforces a monthly auto-refund volume cap of 15% of total unlocked leads per workspace; excess requests route to the manual Admin Desk.
