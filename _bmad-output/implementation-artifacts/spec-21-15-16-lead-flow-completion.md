---
title: 'Complete lead flow amends — seller intent routing + E2E verification'
type: 'feature'
created: '2026-08-28'
status: 'in-progress'
review_loop_iteration: 0
baseline_commit: 'c1d8dae5783b3b43f081c7a3b5a16437018dd59b'
context:
  - _bmad-output/implementation-artifacts/epic-21-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** SCP 2026-08-28 identified five gaps in the real-estate broker E2E flow. P0 phone unlock, P1 intent/chat framing, and P2 composer reactivity are implemented but the full success criteria are not yet verified, and seller-intent still routes to BĐS seller listings instead of buyer-demand signals.

**Approach:** Wire seller-intent into `LeadSourceAdapterRegistry.resolve_adapters_for_intent`, align E2E fakes and `broker-smoke.spec.ts` with the 10-lead / unlock / seller-framing success criteria, and confirm no `StringDataRightTruncationError` on lead persistence.

</frozen-after-approval>

## Boundaries & Constraints

**Always:**
- Buy/sell/neutral detection uses existing `_detect_lead_intent` in `LeadGenOrchestrator`.
- `resolve_adapters_for_intent` must remain backward-compatible for callers that omit `intent`.
- Seller-intent must still return useful BĐS listings if no buyer-demand source is available, with `source_kind="listing"` semantics.
- Phone unlock debit 1.5 credits and PII handling must reuse existing `ContactUnlockService`.
- E2E fakes must not require real scraper platform accounts.

**Ask First:**
- If changing unlock credit cost from 1.5 credits.
- If adding a new real buyer-demand adapter instead of social-adapter stub.
- If the final 10-lead count should come from more BĐS adapters or larger fake records per adapter.

**Never:**
- Store raw phone in `Lead` table; always use `VerifiedContact`.
- Return full phone in API responses to non-privileged viewers.
- Skip the existing per-adapter 90s timeout / circuit breaker.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_SELL | Prompt "Tôi cần bán 10 lô đất ký gửi quận 7" | `LeadGenOrchestrator` returns `intent="sell"`, adapter list includes `social` (buyer-demand first) and falls back to BĐS listings | Degrade to BĐS if social unavailable |
| HAPPY_BUY | Prompt "Tìm 10 nhà bán quận 7" | `intent="buy"`, adapters = batdongsan + chotot + muaban_bds | N/A |
| HAPPY_NEUTRAL | Prompt "Thị trường nhà đất quận 7" | `intent="neutral"`, BĐS adapters selected | N/A |
| E2E_10_LEADS | Fake BĐS adapters return 4 records each, 1 filtered by price/city | Right Dock shows ≥10 `lead-row` elements | Test fails if count < 10 |
| E2E_UNLOCK | `broker-smoke.spec.ts` clicks "Mở khóa SĐT" on a row | Masked phone appears, Zalo button enabled | N/A |
| PERSIST_TRUNCATION | Long encrypted phone / title > column limit | `_truncate_bytes` prevents `StringDataRightTruncationError` | Log warning |

## Code Map

- `nowing_backend/app/lead_intelligence/adapters/registry.py` -- `resolve_adapters_for_intent` needs `intent` parameter
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` -- `decompose_query` / `execute_multi_source_lead_gen` pass intent to registry
- `nowing_backend/app/lead_intelligence/adapters/base.py` -- `LeadSourceAdapter` / `LeadSourceCategory` / `RawLeadRecord`
- `nowing_backend/app/lead_intelligence/adapters/social.py` -- buyer-demand stub, currently returns `[]`
- `nowing_backend/tests/e2e/fakes/lead_scrapers.py` -- synthetic records for E2E
- `nowing_backend/tests/e2e/fakes/chat_llm.py` -- trigger keywords for `multi_source_lead_gen`
- `nowing_web/tests/leads/broker-smoke.spec.ts` -- E2E assertions
- `nowing_backend/app/services/lead_batch_service.py` -- `_truncate_bytes` regression guard

## Tasks & Acceptance

**Execution:**
- [ ] `nowing_backend/app/lead_intelligence/adapters/registry.py` -- add `intent: LeadIntent | None = None` to `resolve_adapters_for_intent`; for `sell` intent prefer `SOCIAL` then `REAL_ESTATE`; for `buy`/`neutral` keep existing category logic
- [ ] `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` -- pass `intent` from `decompose_query` to `resolve_adapters_for_intent`; ensure `SubTaskPlan` carries `intent`
- [ ] `nowing_backend/app/lead_intelligence/adapters/social.py` -- stub `search_leads` returns synthetic buyer-demand records in E2E mode (when `SOCIAL_BUYER_DEMAND_STUB` is set or no real feed)
- [ ] `nowing_backend/tests/e2e/fakes/lead_scrapers.py` -- increase BĐS fake records to 4 per source (one above 8 tỷ, one Hà Nội, two Quận 7 under 8 tỷ) so total visible leads ≥ 10
- [ ] `nowing_backend/tests/e2e/fakes/chat_llm.py` -- ensure seller-intent prompts trigger `multi_source_lead_gen`
- [ ] `nowing_web/tests/leads/broker-smoke.spec.ts` -- assert `lead-row` count ≥ 10, add seller-intent test case, add unlock-click test verifying masked phone + enabled Zalo
- [ ] `nowing_backend/app/services/lead_batch_service.py` -- verify `_truncate_bytes` applied to encrypted `VerifiedContact` value and title fields before insert; add regression unit test
- [ ] `nowing_backend/tests/unit/lead_intelligence/test_lead_source_adapters.py` -- add test for `resolve_adapters_for_intent` with `LeadIntent.SELL` / `BUY` / `NEUTRAL`
- [ ] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- tag 21-15 and 21-16 with `amended-2026-08-28`, keep 21-3 `done`

**Acceptance Criteria:**
- Given a seller-intent prompt, when `LeadGenOrchestrator.decompose_query` runs, then it returns `intent="sell"` and `resolve_adapters_for_intent` prioritizes `social` adapter.
- Given `social` adapter has no live buyer-demand data, when `sell` intent is routed, then it falls back to BĐS listings with honest framing.
- Given `broker-smoke.spec.ts` runs, when the BĐS test completes, then the Right Dock shows at least 10 lead rows and no `DEGRADED` / `PARTIAL` banner.
- Given a lead row with no phone, when the user clicks "Mở khóa SĐT", then the row updates to a masked phone and the Zalo button is enabled.
- Given `ruff check` and `pytest` run, then all relevant tests pass and no `StringDataRightTruncationError` occurs.

## Spec Change Log

## Design Notes

`resolve_adapters_for_intent` currently picks adapters by keyword category. Adding an explicit `intent` parameter lets the orchestrator express "I have inventory to sell, find me buyer demand" without relying on prompt keywords. The social adapter is a stub for buyer-demand signals; in E2E it can be faked to return posts from Facebook groups like "cần mua nhà quận 7". If social is empty, the orchestrator still runs BĐS adapters so the broker sees comparable listings and can choose to extract seller phones as a fallback.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/lead_intelligence app/services/lead_batch_service.py tests/e2e/fakes`
- `cd nowing_backend && uv run pytest tests/unit/lead_intelligence -q`
- `cd nowing_backend && uv run pytest tests/unit/services/test_lead_batch_service.py -q`
- `cd nowing_web && pnpm tsc --noEmit`
- `cd nowing_web && PLAYWRIGHT_NO_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://localhost:3567 NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000 NOWING_BACKEND_INTERNAL_URL=http://localhost:8000 pnpm test:e2e tests/leads/broker-smoke.spec.ts`

**Manual checks:**
- Run `multi_source_lead_gen` with seller prompt; inspect chat framing says "tin đăng bán tương tự" not "khách hàng tiềm năng".
- Run buyer prompt; inspect chat framing says "leads".
