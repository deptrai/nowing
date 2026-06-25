# Story 10.1.6a — Nansen TGM Tier Detection (Dev-Only)

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10.1.3 (TGM endpoint migration)
**Status:** backlog
**Created:** 2026-05-06
**Why:** Story 10.1.3 migrate Nansen sang `/api/v1/tgm/who-bought-sold` endpoint (TGM tier ~$150-300/mo). Pro tier customers ($49/mo) nhận 403 cho mọi smart money query mà không có warning. Cần dev-side tier detection + graceful FE notice.

> **🔄 Split 2026-05-06:** Story originally bundled dev work (tier detection code, FE notice) + non-dev cross-functional work (marketing/sales/support coordination). Per IR § QV-4, split into:
> - **10-1-6a (this story):** Dev-only tier detection + FE notice + graceful fallback
> - **[10-1-6b](./10-1-6b-nansen-tgm-customer-comms.md):** Cross-functional comms (marketing email, sales upgrade path, support runbook, finance forecast)
>
> 10-1-6a can ship independently. 10-1-6b is non-blocking on dev cycle.

---

## Problem Statement

**Old endpoint** (`/v1/token/smart-money`): available trên Pro tier ($49/mo).
**New endpoint** (`/api/v1/tgm/who-bought-sold`): yêu cầu **TGM tier** (giá ~$150-300/mo per Nansen pricing 2026).

**Behavior hiện tại:**
- Pro tier customer set `NANSEN_API_KEY` cũ
- Tool gọi TGM endpoint → 403 response
- Code path: `_unavailable_error(403)` → returns `{"error": "...", "status": 403, "source_domain": "nansen.ai"}`
- User chỉ thấy "Smart money flow data unavailable" trong fallback message
- Không biết nguyên nhân thật là tier mismatch

**Customer impact:**
- Existing Pro customers thấy regression — feature từng work, giờ không
- Không có guidance để upgrade/downgrade
- Operations team không có visibility về số customer affected

---

## Acceptance Criteria

**AC1 — Tier-mismatch error specifically labelled:**
GIVEN response status 403 từ Nansen TGM endpoint
WHEN response body contains marker (e.g. `"error": "Insufficient tier"` hoặc similar)
THEN tool returns `{"error": "...", "status": 403, "tier_mismatch": true, "required_tier": "TGM", "current_tier": "Pro"}`
AND log structured event `nansen.tier_mismatch` với customer hash (PII-safe)

**AC2 — User-facing message:**
GIVEN tool returns `tier_mismatch: true`
THEN FE renders specific message:
```
⚠️ Smart money data requires Nansen TGM tier upgrade.
Your current API key has Pro tier access. To enable real-time
smart money flow analysis, upgrade at https://nansen.ai/plans
or contact support.
```
AND fallback chain (Arkham → Dune) STILL runs — user vẫn được thấy data từ free providers

**AC3 — Startup health check:**
GIVEN backend boots với `NANSEN_API_KEY` set
THEN background task gọi TGM probe endpoint một lần để verify tier access
AND result được cache trong Redis với key `nansen:tier_check:<key_hash>` TTL 1h
AND log `nansen.tier_verified` (success) hoặc `nansen.tier_insufficient` (failure)

**AC4 — Operator dashboard event:**
GIVEN structured log `nansen.tier_mismatch`
THEN event được forward sang ops dashboard (Sentry tag `nansen_tier_mismatch=true`)
AND counter `nansen_tier_mismatch_total{customer_hash="..."}` increment

**AC5 — Documentation update:**
- `nowing_backend/.env.example` comment cập nhật:
  ```bash
  # NANSEN_API_KEY=     # TGM tier required (~$150-300/mo). Pro tier ($49/mo) returns 403.
  #                     # Get key at https://nansen.ai/plans → "TGM" subscription
  ```
- README hoặc operations runbook bổ sung section "Nansen tier requirements"

**AC6 — Graceful degradation:**
GIVEN customer chưa upgrade (Pro tier)
THEN feature `get_smart_money_flow` vẫn work qua Arkham + Dune fallbacks
AND user thấy real Sankey data (không bị block hoàn toàn)

---

## Files to Modify / Create

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Detect tier-mismatch in 403 response body + return structured error |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Surface `tier_mismatch` flag through wrapper response |
| `nowing_backend/app/tasks/health/nansen_tier_check.py` | CREATE | Background task for startup tier probe |
| `nowing_backend/app/tasks/celery_app.py` | UPDATE | Schedule tier check on boot + every 1h |
| `nowing_web/components/new-chat/report/crypto-report-layout.tsx` | UPDATE | Render `<NansenTierUpgradeNotice />` when `tier_mismatch` |
| `nowing_web/components/crypto/NansenTierUpgradeNotice.tsx` | CREATE | New notice component with upgrade CTA |
| `nowing_backend/.env.example` | UPDATE | Comment about TGM requirement |
| `docs/operations/nansen-tiers.md` | CREATE | Runbook for tier troubleshooting |
| `nowing_backend/tests/unit/tasks/test_nansen_tier_check.py` | CREATE | Unit tests for tier check task |

---

## Tasks/Subtasks

- [ ] Research Nansen 403 response body shape — verify "tier insufficient" marker
- [ ] Implement tier-mismatch detection in `nansen_smart_money.py`
- [ ] Surface `tier_mismatch` field through tool wrapper
- [ ] Background tier check task (Celery beat schedule 1h)
- [ ] FE notice component
- [ ] Update `.env.example` + create runbook
- [ ] Sentry tagging
- [ ] Unit tests (3-5 cases)
- [ ] Integration test: simulate Pro-tier 403 → verify graceful fallback to Arkham/Dune
- [ ] Cross-functional handoff to story 10-1-6b: trigger condition, customer-hash list, tier-detection metrics dashboard

---

## Test Plan

```python
@pytest.mark.asyncio
async def test_nansen_403_tier_mismatch_returns_structured_error():
    payload = {"error": "Insufficient tier — TGM required"}
    patcher, _ = _patch_httpx_post(_mock_response(payload, 403))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "pro-tier-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 403
    assert result.get("tier_mismatch") is True
    assert "required_tier" in result


@pytest.mark.asyncio
async def test_pro_tier_falls_back_to_arkham_dune_gracefully():
    # Mock Nansen 403, Arkham 200 with data
    # Assert final Sankey came from Arkham (source_domain=arkm.com)
    # Assert FE notice still shown alongside data
```

---

## Risks

| Risk | Mitigation |
|---|---|
| Nansen 403 body shape differs từ documented marker → tier detection unreliable | Multiple heuristics (status code + body marker + tier check task confirmation) |
| Customer upgrades but cache vẫn returns "tier mismatch" | Tier cache TTL 1h + manual `POST /admin/nansen/recheck` endpoint |
| Notice component spam — appears every smart money query | Throttle notice display to once per 24h per user (localStorage flag) |
| GDPR concern: logging customer hash | SHA-256 hash của API key, không log raw key |

---

## Hand-off to Story 10-1-6b (Customer Comms)

When 10-1-6a ships, trigger 10-1-6b với deliverables:
- Customer hash list (SHA-256 from `nansen.tier_mismatch` Sentry events)
- Tier-detection metrics dashboard (Grafana board) cho marketing/sales tracking
- Implementation runbook handoff to Support team

10-1-6b owners (Marketing + Sales + Support + Finance) execute non-dev workstream independently. See [story 10-1-6b](./10-1-6b-nansen-tgm-customer-comms.md).
