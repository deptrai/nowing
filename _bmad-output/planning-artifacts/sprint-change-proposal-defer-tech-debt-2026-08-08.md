# Sprint Change Proposal: Defer Tech Debt Resolution

**Date:** 2026-08-08
**Source:** Code review defer items across 15 stories (73 items total, 21 patched, 15 remaining)
**Priority:** P2/P3 — no user-facing impact, defense-in-depth + cost optimization
**Scope:** Minor — extend 5 epic cũ với follow-up stories, không tạo epic mới

## Section 1: Issue Summary

**Problem statement:** Code reviews across 15 stories (3-7, 4-8c, 4-8d, 4-8h, 8-11, 9-6b, 10-4, others) identified 73 defer items. 21 patches + 122 tests đã được apply trong sprint hiện tại. Còn 15 items deferred — defense-in-depth gaps, cost optimization opportunities, test robustness improvements.

**Discovery context:** Phát hiện trong quá trình code review adversarial (Blind Hunter + Edge Case Hunter) cho từng story. Mỗi item có exact file:line, current code, fix complexity đã được investigate.

**Evidence:**
- 7 architectural/medium items: DB CHECK constraint, race conditions (3 paths), provider validation, HMAC hash, DB error handling, large output, pagination
- 6 test robustness items: negative assertion, skip condition, gate.yaml handling, try/finally cleanup, session cleanup, mock call count
- 2 feature implementations: ChainLens conditional gating, JSON regex upgrade (latter đã addressed trong test gaps spec)

**Impact:** Không có item nào gây data loss, security vulnerability, hay user-facing bug. Tất cả có app-layer guards hiện có — chỉ thiếu DB-level constraints, locking, hoặc observability.

## Section 2: Impact Analysis

### Epic Impact

| Epic | Status | Impact | Action |
|------|--------|--------|--------|
| Epic 3: Knowledge Base + Long-Term Memory | done | 4 defer items (3-7) | Add 3.7-followup story |
| Epic 4: Chat & Agents | in-progress | 7 defer items (4-8c, 4-8d, 4-8h) | Add 3 followup stories |
| Epic 8: Platform Operations | done | 2 defer items (8-11) | Add 8.11-followup story |
| Epic 9: Deep Research | done | 4 defer items (9-6b) | Add 9.6-followup story |
| Epic 10: Connector & Scraper Expansion | in-progress | 0 (already addressed) | No change |

**No epics obsolete. No new epics needed. No priority changes.**

### Artifact Conflicts

- **PRD:** No conflict — defer items là tech debt, không thay đổi requirements
- **Architecture:** No conflict — chỉ thêm DB constraints + locking (cùng pattern hiện có)
- **UX:** No impact
- **CI/CD:** Test robustness items cải thiện CI gate nhưng không thay đổi pipeline

### Technical Impact

| Category | Impact |
|----------|--------|
| Code | 15 files affected (7 production, 8 test) |
| Infrastructure | 1 Alembic migration (DB CHECK constraint) |
| Deployment | No change — all patches backward compatible |
| Testing | 6 test robustness improvements |

## Section 3: Recommended Approach

**Selected: Option 1 — Direct Adjustment**

Extend 5 epic cũ (3, 4, 8, 9) với 6 follow-up stories. Không tạo epic mới.

**Rationale:**
- Defer items thuộc về epic gốc — cùng domain, cùng codebase area
- Tạo epic mới (Epic 19) sẽ fragment tech debt khỏi context gốc, khó track
- Follow-up stories giữ liên kết với story gốc, dễ trace khi review
- Effort thấp: 6-9 ngày tổng, có thể làm incremental
- Risk thấp: tất cả backward compatible, có app-layer guards hiện có

**Effort estimate:** 6-9 days
**Risk level:** Low
**Timeline impact:** Minimal — P2/P3, làm khi có trigger

## Section 4: Detailed Change Proposals

### Epic 3: Knowledge Base + Long-Term Memory

**Add Story 3.7-followup: Retention Hardening** `(tech debt, P2)`

**AC:**
1. Concurrent retention update: SELECT FOR UPDATE tránh last-write-wins
2. Test: negative assertion verify cả 2 chunks tồn tại trước khi assert search filter
3. Test: test-archived-sync.spec.ts skip khi backend không chạy
4. Test: data-retention.spec.ts workspace cleanup trong finally block

**Items covered:** race condition (3-7), negative assertion, zero sync skip, try/finally cleanup
**Effort:** 1-2 days

### Epic 4: Chat & Agents

**Add Story 4.8c-followup: Sampler Hardening** `(tech debt, P3)`

**AC:**
1. HMAC workspace hash thay vì plain SHA256
2. DB error handling: log error rõ ràng thay vì crash silently
3. Test: session context manager __aexit__ rollback trên exception

**Items covered:** HMAC hash, DB error handling, session cleanup
**Effort:** 1 day

**Add Story 4.8d-followup: Quality Benchmark Test Robustness** `(tech debt, P3)`

**AC:**
1. Test: skip với clear message khi gate.yaml missing

**Items covered:** gate.yaml handling
**Effort:** 0.5 day

**Add Story 4.8h-followup: Mode-Aware Chat Policy Hardening** `(tech debt, P2)`

**AC:**
1. Concurrent tool calls: atomic budget counter update tránh race
2. ChainLens conditional gating: chỉ trigger khi no mentioned_docs AND first KB search empty

**Items covered:** race condition (4-8h), ChainLens conditional gating
**Effort:** 2-3 days

### Epic 8: Platform Operations

**Add Story 8.11-followup: Admin Model Config Hardening** `(tech debt, P3)`

**AC:**
1. Provider validation against known provider list (enum)
2. Pagination trên list endpoint (limit/offset)

**Items covered:** provider validation, pagination
**Effort:** 1 day

### Epic 9: Deep Research

**Add Story 9.6-followup: Re-Validation Hardening** `(tech debt, P2)`

**AC:**
1. DB CHECK constraint trên Memory.confidence [0.1, 1.0] (Alembic migration)
2. Concurrent revalidation: SELECT FOR UPDATE tránh race
3. Large output: truncate text > 100KB trước khi compare
4. Test: assert mock executor call_count > 0 trong failure path

**Items covered:** DB CHECK constraint, race condition (9-6b), large output, mock call count
**Effort:** 2-3 days

## Section 5: Implementation Handoff

**Change scope: Minor** — direct implementation by Developer agent

| Story | Priority | Effort | Trigger |
|-------|----------|--------|---------|
| 3.7-followup | P2 | 1-2 days | Khi có concurrent retention updates |
| 4.8c-followup | P3 | 1 day | Khi sampler trở thành automated job |
| 4.8d-followup | P3 | 0.5 day | Làm trước — rủi ro thấp nhất |
| 4.8h-followup | P2 | 2-3 days | Khi ChainLens cost là pain point |
| 8.11-followup | P3 | 1 day | Khi connections > 1000 |
| 9.6-followup | P2 | 2-3 days | Khi có automated revalidation |

**Recommended order:**
1. 4.8d-followup (0.5 day, lowest risk)
2. 4.8c-followup (1 day, test robustness)
3. 3.7-followup (1-2 days, test + race)
4. 9.6-followup (2-3 days, DB constraint + race)
5. 4.8h-followup (2-3 days, ChainLens gating)
6. 8.11-followup (1 day, admin hardening)

**Handoff:** Developer agent — implement theo recommended order khi trigger conditions met.

**Success criteria:**
- All follow-up stories have tests passing
- No regression trong existing tests
- DB migration backward compatible
- ChainLens conditional gating verified qua chat/regression benchmark

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Confidence set to invalid value via direct DB | Low | Medium | App clamps anyway; DB constraint là defense-in-depth |
| Concurrent revalidation corrupts confidence | Low | Low | User-initiated, low concurrency |
| ChainLens called unnecessarily in quality mode | High | Low | Cost, not correctness; conditional gating giảm cost |
| Test passes for wrong reason | Medium | Low | Test quality, not production |
| Admin list slow with 1000+ connections | Low | Low | Admin-only endpoint |

**Bottom line:** Không có item nào gây data loss hay security vulnerability. Tất cả là defense-in-depth hoặc cost optimization. An toàn defer đến khi trigger conditions met.
