# Sprint Change Proposal: Defer Tech Debt Resolution

**Date:** 2026-08-08
**Source:** Code review defer items across 15 stories (73 items total, 21 patched, 15 remaining)
**Priority:** P2 — no user-facing impact, defense-in-depth + cost optimization

## Context

Code reviews across 15 stories identified 73 defer items. 21 patches + 122 tests đã được apply. Còn 15 items deferred — không gây data loss, security vulnerability, hay user-facing bug, nhưng cần plan để track và resolve theo priority.

## Proposed: Tech Debt Epic (Epic 19)

Tạo epic mới cho tech debt từ code review, chia thành 3 stories theo priority:

### Story 19-1: Defense-in-depth hardening (P2)

**Scope:** DB-level constraints + locking strategy cho concurrent access

| Item | File | Effort | Trigger |
|------|------|--------|---------|
| DB CHECK constraint on confidence [0.1, 1.0] | `app/db.py:2232` + migration | S | Khi có direct DB access từ services khác |
| Race condition: concurrent revalidation (9-6b) | `revalidation_service.py:234` | M | Khi có automated revalidation |
| Race condition: concurrent retention update (3-7) | `workspaces_routes.py:304` | M | Khi có automated workspace config |
| Race condition: mode budget counter (4-8h) | `mode_budget.py:209` | M | Khi có concurrent tool calls trong 1 turn |
| Provider validation enum (8-11) | `admin_global_model_connections_routes.py` | M | Khi provider catalog正式化 |

**AC:** DB CHECK constraint added + SELECT FOR UPDATE cho concurrent paths + provider enum validated

### Story 19-2: Cost optimization (P2)

**Scope:** ChainLens conditional gating + capability output limits

| Item | File | Effort | Trigger |
|------|------|--------|---------|
| ChainLens conditional gating (4-8h) | `mode_budget.py` + orchestrator | L | Khi cost optimization là priority |
| Large output handling (9-6b) | `revalidation_service.py:53` | S | Khi có capability return binary data |
| HMAC workspace hash (4-8c) | `chat_query_sampler.py:97` | S | Khi hash dùng cho auth purpose |
| DB error handling in sampler (4-8c) | `chat_query_sampler.py:158` | S | Khi sampler trở thành automated job |
| Pagination on admin list (8-11) | `admin_global_model_connections_routes.py:320` | S | Khi connections > 1000 |

**AC:** ChainLens chỉ trigger khi no mentioned_docs AND first search empty + output truncation + pagination

### Story 19-3: Test robustness (P3)

**Scope:** Test quality improvements cho CI gate

| Item | File | Effort |
|------|------|--------|
| Negative assertion (archived search) | `test_data_retention.py:482` | S |
| Zero sync skip condition | `test-archived-sync.spec.ts` | S |
| gate.yaml missing file handling | `test_quality.py` | S |
| try/finally workspace cleanup | `data-retention.spec.ts` | S |
| Session context manager cleanup | `test_chat_query_sampler.py:41` | S |
| Mock call count assertion | `test_memory_revalidation.py:249` | S |

**AC:** All tests have negative assertions + skip conditions + cleanup in finally blocks

## Effort Summary

| Story | Items | Effort | Priority |
|-------|-------|--------|----------|
| 19-1 | 5 | 2-3 days | P2 |
| 19-2 | 5 | 3-5 days | P2 |
| 19-3 | 6 | 1 day | P3 |
| **Total** | 16 | **6-9 days** | |

## Recommendation

- **19-3 (test robustness)** làm trước — 1 ngày, rủi ro thấp nhất, cải thiện CI gate ngay
- **19-1 (defense-in-depth)** làm khi có signal về concurrent access hoặc direct DB access
- **19-2 (cost optimization)** làm khi ChainLens cost trở thành pain point

## Risk if deferred indefinitely

| Risk | Probability | Impact |
|------|-------------|--------|
| Confidence set to invalid value via direct DB | Low | Medium — app clamps anyway |
| Concurrent revalidation corrupts confidence | Low | Low — user-initiated, low concurrency |
| ChainLens called unnecessarily in quality mode | High | Low — cost, not correctness |
| Test passes for wrong reason | Medium | Low — test quality, not production |
| Admin list slow with 1000+ connections | Low | Low — admin-only |

**Bottom line:** Không có item nào gây data loss hay security vulnerability. Tất cả đều là defense-in-depth hoặc cost optimization. An toàn để defer đến khi có trigger.
