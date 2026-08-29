---
title: 'Re-enable BĐS phone resolution with unlock UI'
type: 'feature'
created: '2026-08-28'
status: 'completed'
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-21-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Real-estate broker E2E shows all BĐS leads with phone = `—` and Zalo/ZNS disabled because BĐS adapters run with `resolve_phones=False`. Without a working phone, outbound (Zalo, ZNS, sequences) is unusable.

**Approach:** Re-enable phone resolution for BĐS adapters with a 90s per-adapter timeout and a circuit breaker that degrades gracefully. Add a UI affordance to unlock a missing phone for 1.5 credits.

## Boundaries & Constraints

**Always:**
- Phone numbers must be encrypted via AES-256 in `VerifiedContact` and masked in standard API responses (`0908***456`).
- Phone resolution must respect DNC and PII vault rules.
- Unlock action debits 1.5 credits (`usage_type="contact_enrichment"`) only on success; auto-refund SLA applies if reported dead within 24h.
- `resolve_phones` must not cause the whole `multi_source_lead_gen` call to fail; one adapter timing out must degrade to `needs_enrichment`.

**Ask First:**
- If adding a new API endpoint for per-contact unlock instead of reusing the existing PhoneWaterfallEngine flow.
- If changing the unlock credit price from 1.5 credits.

**Never:**
- Store raw phone in `Lead` table; always use `VerifiedContact`.
- Return full phone in API responses to non-privileged viewers.
- Scrape phone in a way that violates Decree 13/2023/NĐ-CP or platform ToS.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | BĐS adapter `resolve_phones=True`, phone resolves in <90s | `VerifiedContact` created with phone, Zalo/ZNS enabled, masked phone shown | N/A |
| TIMEOUT | BĐS adapter phone resolution exceeds 90s | Row persisted with `needs_enrichment=True`; UI shows "Mở khóa SĐT" | Log warning; circuit breaker trips after N retries |
| UNLOCK_CLICK | User clicks "Mở khóa SĐT" on a lead with no phone | Backend retries resolution; on success update row in-place; on fail show error + refund credit | No-op if resolution unavailable |
| NO_CONTACT_SOURCE | Listing has no phone channel (e.g., removed by platform) | Row shows "Không có SĐT" instead of disabled buttons | N/A |

</frozen-after-approval>

## Code Map

- `app/lead_intelligence/services/lead_gen_orchestrator.py` -- dispatches adapters and sets `resolve_phones`
- `app/lead_intelligence/lead_source_adapter.py` or `app/lead_intelligence/adapters/` -- `BatdongsanLeadAdapter`, `ChototLeadAdapter`, `MuabanBdsLeadAdapter`
- `app/proprietary/platforms/batdongsan/scrape/executor.py` -- actual BĐS scraper with `resolve_phones` flag
- `app/proprietary/platforms/chotot/` -- Chotot scraper
- `app/proprietary/platforms/muaban_bds/` -- Muaban BĐS scraper
- `app/services/lead_batch_service.py` -- ingests leads, creates `VerifiedContact` rows
- `app/services/lead_intelligence/confidence/gate.py` -- `ConfidenceGate` already fixed for area parsing
- `components/leads/NowingLeadMatrix.tsx` -- adds unlock action column
- `components/leads/PhoneCopyPill.tsx` -- phone display + copy
- `components/leads/zalo-outreach-button.tsx` -- enabled only when phone exists
- `app/services/phone_waterfall_service.py` -- existing 3-tier phone resolution engine
- `tests/leads/broker-smoke.spec.ts` -- E2E to update

## Tasks & Acceptance

**Execution:**
- [x] `app/lead_intelligence/services/lead_gen_orchestrator.py` -- set `resolve_phones=True` for BĐS adapters (batdongsan, chotot, muaban_bds) and cap max_pages/max_items to keep total call under 90s budget.
- [x] `app/proprietary/platforms/batdongsan/scrape/executor.py` -- wire `resolve_phones` through to phone resolution; add per-adapter 90s timeout and circuit breaker.
- [x] `app/proprietary/platforms/chotot/` and `app/proprietary/platforms/muaban_bds/` -- apply same `resolve_phones` + timeout/circuit breaker pattern.
- [x] `app/services/lead_batch_service.py` -- ensure resolved phones create `VerifiedContact` with PII encryption and masked display; truncate long encrypted tokens before insert (regression guard).
- [x] `components/leads/NowingLeadMatrix.tsx` / `components/leads/ContactChannels.tsx` -- add primary "Mở khóa SĐT" action for rows without phone (matrix + flyout); disabled Zalo/ZNS become secondary.
- [x] `components/leads/PhoneCopyPill.tsx` / `components/leads/zalo-outreach-button.tsx` -- enable Zalo/ZNS when phone resolves; update after Zero sync.
- [x] `app/routes/leads_routes.py` or existing API -- add endpoint to retry phone resolution for a single `lead_id` and debit 1.5 credits on success.
- [x] `tests/leads/broker-smoke.spec.ts` -- update assertion to check at least one phone is non-empty or unlockable.

**Acceptance Criteria:**
- Given a BĐS query, when `multi_source_lead_gen` runs, then at least one adapter attempts phone resolution and creates a `VerifiedContact` on success.
- Given phone resolution fails, when the lead row renders, then it shows "Mở khóa SĐT" instead of only disabled buttons.
- Given the user clicks "Mở khóa SĐT", when resolution succeeds, then the row updates to show the masked phone and enables Zalo/ZNS.
- Given `ruff check` and `pytest` run, then all relevant tests pass and no `StringDataRightTruncationError` occurs.

## Design Notes

The existing `PhoneWaterfallEngine` (Story 21.3) already supports 3-tier resolution. Reuse it by calling from the adapter layer after `normalize_lead`. The unlock action should be a lightweight retry of the same engine for a single `lead_id`, not a full re-scrape.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/lead_intelligence app/proprietary/platforms/batdongsan app/proprietary/platforms/chotot app/proprietary/platforms/muaban_bds app/services/lead_batch_service.py`
- `uv run pytest tests/unit/lead_intelligence -q`
- `uv run pytest tests/leads/broker-smoke.spec.ts` (from `nowing_web` via Playwright)

**Manual checks:**
- Run `multi_source_lead_gen` with BĐS prompt; inspect Right Dock for phone column and Zalo button state.
- Click "Mở khóa SĐT" and verify credit deduction + phone appears.
