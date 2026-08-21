---
workflowStatus: done
totalSteps: 5
stepsCompleted:
  - step-01-detect-mode
  - step-02-load-context
  - step-03-risk-and-testability
  - step-04-coverage-plan
  - step-05-generate-output
lastStep: step-05-generate-output
lastSaved: "2026-08-21T23:50:00+07:00"
inputDocuments:
  - _bmad-output/implementation-artifacts/stories/25-3-affiliate-partner-payout-desk-anti-fraud-engine.md
  - nowing_backend/app/routes/admin_affiliates_routes.py
  - nowing_backend/app/services/affiliate_anti_fraud_service.py
  - nowing_backend/app/services/partner_payout_service.py
  - nowing_backend/tests/unit/services/test_affiliate_anti_fraud.py
  - nowing_backend/tests/integration/routes/test_admin_affiliates.py
  - nowing_backend/tests/unit/services/test_partner_payout_service.py
  - nowing_backend/tests/integration/services/test_partner_payout_reconciliation.py
  - nowing_web/app/admin/affiliates/payouts/page.tsx
  - nowing_web/components/admin/AffiliatePayoutDetailModal.tsx
  - nowing_web/lib/apis/admin-affiliates-api.service.ts
outputDocuments:
  - _bmad-output/implementation-artifacts/test-design-25-3.md
---

# Test Design Progress

## Step 1: Detect Mode & Prerequisites

**Mode:** Epic-Level (detected from `sprint-status.yaml`). Target: Story 25.3.

## Step 2: Load Context

Loaded story, architecture context, implementation code, and existing test files. Stack: fullstack (FastAPI + Next.js). Identified Playwright E2E and service-level integration gaps.

## Step 3: Risk & Testability

Identified 9 risks (R1–R9), with 6 high-risk items (score ≥ 6). Risks cover high-risk payout dispatch, duplicate payout, VND conversion, fraud detection, audit completeness, and webhook settlement.

## Step 4: Coverage Plan

Mapped P0–P2 tests to AC-1 through AC-4 plus NFR/quality gates. Included unit, integration, concurrency, E2E, and mutation-gate coverage.

## Step 5: Output Generated

Final test plan saved to `_bmad-output/implementation-artifacts/test-design-25-3.md`.
