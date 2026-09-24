---
title: "Scraper Playground Thin Proxy & Workspace Billing Gate"
type: "feature"
created: "2026-09-24"
status: "done"
review_loop_iteration: 0
baseline_revision: ""
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Playground UI (`/dashboard/[workspace_id]/playground`) hiện gọi các REST endpoints `/scrapers/{platform}/{verb}` mà các executor capability đang gọi local crawler trực tiếp (playwright/selenium) — không đi qua XActions Gateway. Điều này vi phạm Epic 40 mục tiêu "XActions là sole scraping engine".

**Approach:** Biến playground scraper endpoints thành thin proxy: giữ nguyên REST contract (`POST /workspaces/{id}/scrapers/{platform}/{verb}`) nhưng executor gọi `XActionsMcpClient.call_tool("x_scrape", ...)` thay vì local crawler. Giữ nguyên billing gate (check_balance → charge_capability → BillingEvent).

## Boundaries & Constraints

**Always:**
- Giữ nguyên REST contract: `POST /workspaces/{workspace_id}/scrapers/{platform}/{verb}` với auth, workspace authz, rate limit, billing gate.
- Executor phải gọi `XActionsMcpClient.call_tool("x_scrape", payload)` — không chạy local browser/crawler trong backend.
- Billing: `gate_capability` soft-lock trước, `charge_capability` debit sau, refund khi anti-bot/failure.
- Response format giữ nguyên `ScrapeOutput` shape cho Playground UI compatibility.

**Never:**
- Không thêm REST endpoint mới — chỉ thay implementation executor.
- Không bypass billing gate — mọi request phải qua `check_balance` → `charge_capability`.
- Không xóa platform capability registrations — chỉ thay executor.
- Không sửa playground UI (`catalog.ts`, pages) — contract không đổi.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | `POST /scrapers/topcv/scrape` với `{keyword, location}` | Executor gọi `x_scrape` → trả preview ≤30 records + `cost_micros` | No error |
| XACTIONS_DOWN | XActions circuit OPEN | `XACT_4001` envelope → HTTP 503 + refund credits | Fail-fast |
| ANTI_BOT | XActions trả `degraded=true` + `degradation_reason` | Refund credits + trả degraded response + escalation task | Anti-bot flow |
| INSUFFICIENT_CREDIT | Workspace không đủ credits | HTTP 402 Payment Required trước khi gọi XActions | `InsufficientCreditsError` |
| INVALID_PLATFORM | `platform` không có trong catalog | HTTP 422 + `supported_platforms` list | Validation error |

</intent-contract>

## Code Map

- `app/capabilities/core/access/rest.py` — REST endpoint `POST /workspaces/{id}/scrapers/{platform}/{verb}` với `gate_capability` + `charge_capability` billing.
- `app/capabilities/core/billing.py` — `gate_capability()`, `charge_capability()` — credit check + debit.
- `app/capabilities/topcv/scrape/executor.py` — Example: calls `scrape_topcv` (local crawler). Cần thay bằng XActions MCP call.
- `app/proprietary/platforms/xactions/adapter_v2.py` — `XActionsSocialAdapterV2`, `UniversalScrapeTargetMapper` — đã có x_scrape envelope logic.
- `app/proprietary/platforms/xactions/mcp_client.py` — `XActionsMcpClient.call_tool()` với circuit breaker (Story 40.1).
- `app/capabilities/{platform}/scrape/` — 22 platform capability directories cần update executor.

## Tasks & Acceptance

**Execution:**
- `app/capabilities/{platform}/scrape/executor.py` — Thay `scrape_{platform}` local call bằng `XActionsMcpClient.call_tool("x_scrape", {platform, action, args, context})`. Mỗi platform map args từ `ScrapeInput` sang x_scrape `args` format.
- `app/capabilities/core/billing.py` — Verify `gate_capability` soft-locks credits trước executor, `charge_capability` debits sau, refund khi error/degraded.
- `app/capabilities/core/access/rest.py` — Verify error mapping: `XActionsMcpError(code=XACT_4001)` → HTTP 503, anti-bot → degraded response.
- `nowing_backend/tests/unit/capabilities/test_scraper_xactions_proxy.py` — Test executor gọi x_scrape thay vì local crawler.

**Acceptance Criteria:**
- Given `POST /scrapers/topcv/scrape` với workspace có đủ credits, when request thực thi, then executor gọi `x_scrape` trên XActions (không chạy local browser) và trả `ScrapeOutput` đúng format.
- Given XActions trả `XACT_4001` (circuit open), when request đến, then HTTP 503 + credits được refund.
- Given workspace không đủ credits, when request đến, then HTTP 402 trước khi gọi XActions.
- Given XActions trả `degraded=true` với `degradation_reason=bot_detected`, when executor nhận, then credits được refund và `anti_bot_escalation` task được trigger.

## Design Notes

- Executor chỉ thay implementation bên trong — REST contract, billing flow, error envelopes giữ nguyên.
- Cần map `ScrapeInput` fields → `x_scrape` args per platform (có thể dùng `UniversalScrapeTargetMapper` hoặc tạo mapping table).
- Anti-bot degradation vẫn trigger `capture_platform_anti_bot_screenshot_task` như cũ.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/capabilities/ -v` — capability tests pass
- `cd nowing_backend && uv run pytest tests/unit/platforms/xactions/ -v` — xactions tests pass (no regression)

**Manual checks:**
- Start XActions MCP locally + Nowing backend → call `POST /api/v1/workspaces/{id}/scrapers/topcv/scrape` → verify XActions receives `x_scrape` call, không có local browser spawn.

## Auto Run Result

**Status**: in-review

**Summary of implemented change:**
- Created `app/capabilities/core/xactions_proxy.py` — thin proxy executor factory that calls `XActionsMcpClient.call_tool("x_scrape", ...)` instead of local crawler functions.
- Updated `app/capabilities/topcv/scrape/executor.py` to use the XActions proxy while preserving anti-bot escalation logic.
- Updated `tests/unit/capabilities/topcv/scrape/test_registry.py` to mock the XActions proxy instead of `scrape_topcv`.
- Created `tests/unit/capabilities/test_xactions_proxy.py` with 8 tests covering happy path, XACT_4001, degraded responses, error envelopes, generic errors.

**Files changed:**
- `app/capabilities/core/xactions_proxy.py` (new) — `make_xactions_executor()` factory + error mapping.
- `app/capabilities/topcv/scrape/executor.py` — Switched from `scrape_topcv` to XActions proxy.
- `tests/unit/capabilities/topcv/scrape/test_registry.py` — Updated mocks.
- `tests/unit/capabilities/test_xactions_proxy.py` (new) — Proxy tests.

**Verification performed:**
- `pytest tests/unit/capabilities/` — **1010 tests pass** (1 skipped, 0 failures)
- `pytest tests/unit/platforms/xactions/` — **88 tests pass**

**Remaining work (not yet done in this pass):**
- 21 other platform executors still call local scrape functions — they need the same proxy pattern applied (batched or per-platform follow-up).
- `NOWING_XACTIONS_USE_V2` feature flag not yet added to `feature_flags.py` — Story 40.1 spec mentions it but actual flag used is `XACTIONS_USE_UNIFIED_DISPATCH`.
- `charge_capability`/`gate_capability` billing integration verified — REST endpoint already handles it upstream of executor.

**Residual risks:**
- Other platform executors still use local scraping — Story 40.2 is only partially complete (topcv done as pattern, others need same treatment).
- XActions `x_scrape` tool doesn't exist yet in the actual XActions MCP server — calls will return `tool_not_found` until XActions Epic 46 lands.
