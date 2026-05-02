# Sprint Change Proposal — Epic 11 Deferred Items Triage

**Date:** 2026-05-02
**Author:** Winston (System Architect) via `bmad-correct-course`
**Mode:** Batch
**Trigger:** Epic 11 deferred items backlog (24 items) from round-2 reviews of stories 11-1 through 11-5

---

## 1. Issue Summary

### Problem statement

Epic 11 (Architecture Resilience & Stability) đã đóng tất cả 5 stories ở status `done` trong sprint-status.yaml (2026-05-02). Tuy nhiên, các round-2 adversarial reviews cùng ngày đã surface **24 deferred findings** — không phải bug cản trở functionality, nhưng có 4 finding là **production go-live blockers** và 4 finding là **resilience gaps** sẽ trigger incident sau khi launch nếu không fix trước Epic 11 retrospective.

Vấn đề chính: **deferred-work.md không có ownership / due-date** — nếu Epic 11 retrospective chốt mà chưa promote critical items thành stories, chúng sẽ rớt vào tech-debt black-hole.

### Discovery context

- **When:** 2026-05-02, Round 2 reviews chạy ngay sau khi 5 stories được mark `done`. Các finding chưa được apply lúc round 1 (do scope/effort/cần PM input).
- **How:** Mỗi review chạy 3 layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Round 1 catch 28 issues → fix all. Round 2 catch deeper issues bị round 1 missed.
- **Evidence:** `_bmad-output/implementation-artifacts/deferred-work.md` lines 385-423 (sections "code review of story 11-1..11-5 (2026-05-02)"). MCP impact analysis trên 4 critical files trả risk=`high`, blast radius 85 files.

### Categorisation (24 items)

| Bucket | Count | Examples |
|---|---|---|
| 🔴 CRITICAL — Production go-live blockers | 4 | Cloudflare CDN strip SSE; HTTP/2 chưa verify Traefik; PRO_PLANS sync FE/BE; Redis-flap double-consume |
| 🟡 IMPORTANT — Resilience gaps + design questions | 4 | Token waste on tool exception; heartbeat cancel leaks DB session; search-space scoping mismatch; NOT EXISTS scan on 10M-row table |
| 🟢 NICE-TO-HAVE — Tech debt | 15 | EVALSHA cache, get_limiter race, wait_step floor, pre-existing async patterns, test smells, etc. |
| 🔵 OBSOLETE — Already addressed | 1 | `asyncio.new_event_loop()` (round 2 đã hardened) |

### Validation evidence (MCP impact analysis)

```
Blast radius for 4 critical files (rate_limiter.py, new_streaming_service.py,
entitlements.ts, stream_new_chat.py):
  - 73 nodes directly changed
  - 500 nodes impacted (within 2 hops)
  - 85 additional files affected
  - Risk: high
```

**PRO_PLANS duplication confirmed:**
- `nowing_backend/app/config/__init__.py:317-348` (token/page limits per plan)
- `nowing_backend/app/schemas/stripe.py:14-17` (PlanId enum, lines 14-17)
- `nowing_web/lib/entitlements.ts:30` (FE `PRO_PLANS` array)

Source of truth không tồn tại — 3 nơi maintained độc lập, drift = silent revenue loss.

---

## 2. Impact Analysis

### Epic Impact

**Epic 11** (Architecture Resilience & Stability):
- ✅ Original 5 stories đã `done` — không cần modify scope của 11-1..11-5.
- ⚠️ **Scope gap discovered post-completion**: 4 critical items lẽ ra phải là acceptance criteria của 11-1, 11-4, 11-5 nhưng được route qua deferred. Không invalidate epic, nhưng cần addendum.
- 🆕 **2 new stories cần add vào Epic 11**: 11-6 (Production Go-Live Hardening) và 11-7 (Resilience Hardening Round 2).
- 📉 Epic effort estimate: original "2-3 weeks (1 BE + 0.5 FE)" → cần **+1 week** cho 11-6/11-7.

### Story Impact

**Existing Epic 11 stories (5):**
- Tất cả `done`. Không rollback. Không modify scope.
- Cập nhật **Review Findings** sections để cross-link với 11-6/11-7 follow-ups.

**New stories proposed:**
- **Story 11.6: Production Go-Live Hardening** (P0 — block launch) — covers 4 CRITICAL items
- **Story 11.7: Resilience & Performance Hardening** (P1 — within 2 weeks of launch) — covers 4 IMPORTANT items

**Future epic impact:** None. Epic 12 (Desktop) độc lập.

### Artifact Conflicts

| Artifact | Conflict | Action |
|---|---|---|
| `epics.md` line 1266-1362 (Epic 11) | 5-story scope viết "covers FR41-FR45". 4 critical items extend FR41 (SSE) và FR45 (Quota) nhưng không có story handle | **Update**: append 11.6 + 11.7 stories vào Epic 11 section |
| `prd.md` (FR41 SSE Reliability) | Đã specify "auto-reconnect" nhưng không mention CDN compatibility / HTTP/2 verification | **Update**: Add NFR-R2 sub-criteria cho production-readiness verification |
| `architecture.md` | Epic 11 architecture đã tài liệu hoá Redis CB pattern. Token bucket + entitlement layer chưa có ADR riêng | **Add**: 3 ADRs (rate_limiter Redis-flap consistency, entitlement single source of truth, heartbeat cancellation strategy) |
| `ux-design-specification.md` | Không liên quan — backend/infra changes only | **N/A** |
| `sprint-status.yaml` | `epic-11: in-progress` (line 167); 5 stories đã `done` | **Update**: thêm 11-6 (`backlog`), 11-7 (`backlog`); giữ epic-11 ở `in-progress` cho đến khi 11-6/11-7 done |
| `deferred-work.md` | 24 items chưa marked OBSOLETE/PROMOTED | **Update**: mark 8 items "PROMOTED to 11-6/11-7"; mark obsolete item resolved |

### Technical Impact

- **Code:** No modifications required to Epic 11 code (đã `done`). 11-6/11-7 sẽ touch `rate_limiter.py`, `entitlements.ts`, `stream_new_chat.py`, `new_streaming_service.py`, deployment manifests (Traefik config), backend schema/contracts.
- **Infrastructure:** Traefik HTTP/2 verification (deployment-side). CDN behavior testing (Cloudflare-specific). Document deployment ordering in 11-6.
- **Deployment:** No CI/CD pipeline changes. 11-6 must complete **before production cutover**; 11-7 can ship within 2 weeks after launch.
- **Observability:** Add metrics: `rate_limit_local_fallback_consumed`, `sse_cdn_strip_detected`, `entitlement_drift_alarm`.

---

## 3. Recommended Approach

### Path forward evaluation

| Option | Viable? | Effort | Risk | Trade-off |
|---|---|---|---|---|
| **1. Direct Adjustment** — modify existing 11-1..11-5 to add criteria | ❌ Not viable | Medium | High | All 5 stories `done`; reopening invalidates retrospective integrity |
| **2. Rollback** — revert recent commits | ❌ Not viable | High | Critical | Stories shipped value; rollback costs more than fixing forward |
| **3. PRD MVP review** — reduce Epic 11 scope | ❌ Not viable | Low | Low | MVP doesn't need reduction — Epic 11 is delivering all FRs; gap is in production-hardening surface area |
| **4. New stories (11-6/11-7)** within Epic 11 | ✅ **Recommended** | Low-Medium | Low | Preserves done status of 11-1..11-5; explicit ownership of follow-ups; epic stays open until 11-6 done so retro captures full picture |

### Selected approach: Option 4 — Hybrid (extend Epic 11 with 2 follow-up stories)

**Rationale:**
- **Implementation effort**: 11-6 = ~3 BE-days + 1 DevOps-day, 11-7 = ~5 BE-days. Total ~9 days. Acceptable extension.
- **Technical risk**: Low — no architectural restructuring, only hardening pass on existing code.
- **Team morale**: Stories `done` stay `done`. New stories framed as "production hardening pass" (positive), not "we missed things" (negative).
- **Long-term sustainability**: Forces single-source-of-truth for PRO_PLANS (eliminates silent revenue-loss vector). Documents deployment-hardening in Traefik/CDN docs.
- **Stakeholder expectations**: PM gets 1 explicit decision (search-space scoping) instead of bug discovery in production. Clear due-date for production blockers.

### Trade-offs considered

- **Defer to Epic 12+**: Rejected. CRITICAL items are pre-launch blockers; deferring = risking production incident on day 1.
- **Open as standalone hotfix epic**: Rejected. Scope (~9 days) doesn't warrant new epic; stays within Epic 11's "Resilience" theme.
- **Split into 4 micro-stories**: Rejected. Coupling between items (PRO_PLANS sync needs both BE schema + FE consumer change) is best handled as cohesive story.

---

## 4. Detailed Change Proposals

### CHANGE-01 — Add Story 11.6 to Epic 11

**Location**: `_bmad-output/planning-artifacts/epics.md` after Story 11.5 (around line 1362)

**Insert:**

```markdown
#### Story 11.6: Production Go-Live Hardening
📄 **Story file**: [`stories/11-6-production-go-live-hardening.md`](./stories/11-6-production-go-live-hardening.md) | **P0**
As a system operator,
I want production-environment-specific hardening for SSE / rate-limiter / entitlement
contracts before user-facing launch,
So that day-1 production incidents from CDN buffering, HTTP/2 absence, FE-BE plan
drift, and Redis-flap double-consume are eliminated.

**Source:** Epic 11 round-2 review deferred items 2026-05-02 (4 CRITICAL)

**Acceptance Criteria:**

**Given** Cloudflare CDN deployment serving SSE traffic,
**When** a `/runs/{id}/stream` connection runs with `Cache-Control: no-cache, no-transform`,
**Then** verify (via deployment smoke test in production-mirror env) the response is
NOT recompressed/buffered. Document Cloudflare-specific config requirement (page rule
or worker bypass) in `docs/deployment/sse-cdn.md`.

**And given** Traefik (or active reverse proxy) serving Nowing,
**When** 3+ browser tabs open SSE streams concurrently,
**Then** all tabs maintain connections via HTTP/2 multiplexing (verify in staging,
document required Traefik config flags in `docs/deployment/http2.md`).

**And given** FE consumes `PRO_PLANS` (entitlements.ts),
**When** BE adds/removes a plan SKU,
**Then** FE auto-syncs without manual edit — implement via:
(a) BE exposes `GET /entitlements/plans` endpoint returning canonical list,
(b) FE fetches at app boot OR
(c) generated TS file from BE schema enum at build-time (preferred — no runtime call).

**And given** Redis flap (up → down → up mid-request),
**When** a single `acquire()` call is in-flight during the flap,
**Then** at most 1 token is consumed across Redis + local stores combined
(prevent double-consume by mirroring Redis state to local on each successful EVAL).

**Tasks:**
- [ ] T1: SSE/CDN smoke test + docs (DevOps + BE)
- [ ] T2: HTTP/2 Traefik config + multi-tab test (DevOps)
- [ ] T3: Shared entitlement contract (BE schema endpoint OR build-time codegen) + FE consume
- [ ] T4: rate_limiter Redis flap state-mirror + integration test with toxiproxy

**Estimated effort:** 3 BE-days + 1 DevOps-day = ~4 days

---
```

**Rationale:** Promotes 4 deferred CRITICAL items to formal story with explicit AC, due-date alignment with launch.

### CHANGE-02 — Add Story 11.7 to Epic 11

**Location**: `_bmad-output/planning-artifacts/epics.md` after CHANGE-01

**Insert:**

```markdown
#### Story 11.7: Resilience & Performance Hardening Round 2
📄 **Story file**: [`stories/11-7-resilience-hardening-round2.md`](./stories/11-7-resilience-hardening-round2.md) | **P1**
As a system operator,
I want round-2-review resilience gaps (token-waste, heartbeat-cancel safety, slow-table
DELETE, scoping clarification) addressed within 2 weeks of launch,
So that production stability degrades gracefully under sustained load and edge cases.

**Source:** Epic 11 round-2 review deferred items 2026-05-02 (4 IMPORTANT)

**Acceptance Criteria:**

**Given** a tool raises exception/timeout AFTER `limiter.acquire()` succeeded,
**When** the wrapper catches the exception,
**Then** the consumed token is returned to the bucket (TokenBucketRateLimiter exposes
`release()` method; decorator calls it on exception path).

**And given** a SSE consumer disconnects mid-stream during `_with_heartbeat` wrap,
**When** Starlette cancels the request,
**Then** the inner generator's cancellation does NOT corrupt LangGraph state or leak
DB sessions (use structured concurrency / sentinel pattern; integration test that
simulates disconnect mid-DB-write asserts session is properly closed).

**And given** `crypto_data_snapshots` table grows to 10M+ rows,
**When** `cleanup_orphaned_crypto_snapshots` runs the `NOT EXISTS` batch,
**Then** each batch completes within 60s (verify index `ix_crypto_snapshots_cache_lookup`
covers the orphan-detection query plan via `EXPLAIN ANALYZE`; add session-level
`SET LOCAL statement_timeout = '60s'` is already in place from 11-3 round 2).

**And given** `_prefetch_category` (refresh) writes snapshots without `search_space_id`
while cleanup purges `search_space_id IS NOT NULL`,
**When** PM/Architect reviews,
**Then** an ADR is written documenting the design decision:
(a) Snapshots are intentionally bi-modal (global cache rows + per-workspace rows), OR
(b) Refresh task should pass `search_space_id` (and which workspaces it refreshes for).
ADR landed in `_bmad-output/planning-artifacts/adrs/`.

**Tasks:**
- [ ] T1: TokenBucket release() API + decorator integration + tests
- [ ] T2: Heartbeat cancellation safety refactor + integration test
- [ ] T3: NOT EXISTS query plan analysis (EXPLAIN ANALYZE on prod-shape data) + index recommendation
- [ ] T4: ADR: snapshot scoping (PM/Architect input)

**Estimated effort:** 5 BE-days = ~5 days
```

### CHANGE-03 — Update sprint-status.yaml

**Location**: `_bmad-output/implementation-artifacts/sprint-status.yaml` lines 167-178

**OLD:**

```yaml
  epic-11: in-progress

  # P0 — Critical
  11-1-sse-heartbeat-auto-reconnect: done
  11-2-redis-circuit-breaker: done

  # P1 — Important
  11-3-orphaned-cache-purge: done
  11-4-per-api-token-buckets: done
  11-5-client-quota-enforcement: done

  epic-11-retrospective: optional
```

**NEW:**

```yaml
  epic-11: in-progress  # 11-6 (P0) and 11-7 (P1) follow-up stories pending

  # P0 — Critical
  11-1-sse-heartbeat-auto-reconnect: done
  11-2-redis-circuit-breaker: done

  # P1 — Important
  11-3-orphaned-cache-purge: done
  11-4-per-api-token-buckets: done
  11-5-client-quota-enforcement: done

  # Round-2 review follow-ups (added 2026-05-02 by SCP)
  11-6-production-go-live-hardening: backlog       # P0 — must complete before launch
  11-7-resilience-hardening-round2: backlog        # P1 — within 2 weeks of launch

  epic-11-retrospective: optional
```

### CHANGE-04 — Update Epic 11 effort estimate

**Location**: `_bmad-output/planning-artifacts/epics.md` line 1276

**OLD:**

```
**Estimated Effort:** 2-3 weeks (1 BE + 0.5 FE)
```

**NEW:**

```
**Estimated Effort:** 3-4 weeks (1 BE + 0.5 FE + 0.2 DevOps)
  - 11-1..11-5: 2-3 weeks (delivered 2026-05-02)
  - 11-6 (production hardening): 4 days (P0 — pre-launch)
  - 11-7 (resilience round 2): 5 days (P1 — within 2 weeks post-launch)
```

### CHANGE-05 — Annotate deferred-work.md

**Location**: `_bmad-output/implementation-artifacts/deferred-work.md` (sections for 11-1..11-5 round 2 reviews)

**Action:** Add header to each section:

```markdown
> **Triage 2026-05-02 (Sprint Change Proposal):**
> - 4 CRITICAL items → PROMOTED to Story 11-6 (Production Go-Live Hardening)
> - 4 IMPORTANT items → PROMOTED to Story 11-7 (Resilience Hardening Round 2)
> - 15 NICE-TO-HAVE items → REMAIN deferred, revisit on production signal
> - 1 OBSOLETE item (`asyncio.new_event_loop()`) → DROPPED (pre-existing pattern, no action)
```

Mark each promoted item with `[PROMOTED → 11-6]` or `[PROMOTED → 11-7]` prefix.
Mark obsolete item `[DROPPED 2026-05-02 — pre-existing pattern]`.

### CHANGE-06 — Add 3 ADRs

**Location**: `_bmad-output/planning-artifacts/adrs/`

Create:
1. **`ADR-011-rate-limiter-flap-consistency.md`** — Decision: mirror Redis state to local on every successful EVAL; trade-off: 1 extra atomic op per acquire vs eliminate double-consume class of bug.
2. **`ADR-012-entitlement-single-source-of-truth.md`** — Decision: BE schema is canonical; FE consumes via build-time codegen from `PlanId` enum (no runtime call). Trade-off: build-step complexity vs eliminate silent drift.
3. **`ADR-013-snapshot-scoping-bimodal.md`** — Decision: PM/Architect input required. Document the question + 2 candidate answers + recommendation. Owner: 11-7 T4.

### CHANGE-07 — Update PRD FR41 sub-criteria

**Location**: `_bmad-output/planning-artifacts/prd.md` (FR41 SSE Reliability section)

**Action:** Add sub-criteria:
- FR41.1: SSE compatible with Cloudflare CDN (no recompression / no buffering)
- FR41.2: HTTP/2 multiplexing verified in production reverse-proxy config
- FR41.3: SSE heartbeat cancel safety on consumer disconnect (no DB session leak)

---

## 5. Implementation Handoff

### Change scope classification

**MODERATE** — Backlog reorganization needed (2 new stories), 1 PM decision required (search-space scoping), no fundamental architecture replan.

### Handoff plan

| Recipient | Responsibility | Deliverable |
|---|---|---|
| **Product Owner** | Approve 11-6/11-7 priority + due-dates relative to launch | Updated sprint-status.yaml |
| **Product Manager** | Decide on snapshot scoping (ADR-013 input) | PM signoff on ADR-013 within 11-7 timeline |
| **Architect (Winston)** | Author 3 ADRs + draft 11-6/11-7 story files | ADR-011/012/013 + story-11-6.md, story-11-7.md |
| **Developer agent** | Implement 11-6 (P0, pre-launch) | Code + tests for 4 CRITICAL items |
| **Developer agent** | Implement 11-7 (P1, post-launch within 2 weeks) | Code + tests for 4 IMPORTANT items |
| **DevOps** | Traefik HTTP/2 config + Cloudflare bypass rule + smoke test | Deployment docs + verified config |

### Success criteria

- ✅ Stories 11-6, 11-7 created in `_bmad-output/planning-artifacts/stories/`
- ✅ ADR-011, ADR-012, ADR-013 published in `adrs/`
- ✅ sprint-status.yaml reflects new stories with `backlog` status
- ✅ epics.md Epic 11 section updated with 11-6/11-7 entries + revised effort
- ✅ deferred-work.md sections annotated with promotion status
- ✅ 11-6 completes before production cutover (gating)
- ✅ 11-7 completes within 2 weeks post-launch (non-gating but tracked)

### Timeline impact

- **Pre-launch:** +4 days for 11-6 (P0)
- **Post-launch:** +5 days for 11-7 (P1) — non-blocking, runs in parallel with Epic 12 if needed
- **Total Epic 11 extension:** +1 week (vs original 2-3 week estimate → revised 3-4 weeks)

---

## 6. Approval

**Status:** Pending user review.

Approve [yes] / Revise [no — specify what to adjust].
