---
title: Crypto Orchestra — UX Handoff Delta
epic: Epic 9 — Advanced Crypto Sub-Agents
journey: PRD Journey #8 (Crypto Power User "Khoa")
purpose: Architect/Dev handoff — không cần load full ux-design-specification.md (200KB)
source: _bmad-output/planning-artifacts/ux-design-specification.md → Section "Crypto Orchestra UX"
created: 2026-04-23
author: Luisphan
status: ready-for-architecture
---

# Crypto Orchestra — UX Handoff Delta

Ngắn gọn những gì Architect và Dev cần biết để implement UX Crypto Orchestra mà không phải đọc toàn bộ ux-design-specification.md. Full design rationale ở file gốc section **"Crypto Orchestra UX"**.

---

## 1. What We're Building (TL;DR)

**Journey 8 UX:** Khoa gõ "phân tích toàn diện $UNI" → Main agent spawn 6-11 sub-agents parallel → UI hiển thị per-agent progress + multi-source citations + graceful degradation trong P95 < 90s.

**Core UX decisions đã chốt:**
- **Progress display:** Inline horizontal "Orchestra Conductor Strip" (KHÔNG blocking spinner).
- **Failure handling:** Muted gray + amber notice (KHÔNG red panic).
- **Citations:** Stacked `[1·3·5]`, cluster `[5+◆]`, conflict `[2≠4]`.
- **Long-wait:** 4-stage perceived progress + 30s "soft attention break" milestone.
- **Persistence:** Zustand + Rocicorp Zero → PGLite (survives refresh, background mode).

---

## 2. New Components (7 total)

| # | Component | Base | File path đề xuất | Variants |
|---|-----------|------|-------------------|----------|
| 1 | `<OrchestraStrip />` | Custom | `components/chat/orchestra-strip.tsx` | `default`, `collapsed`, `single-agent`, `pinned` (background mode) |
| 2 | `<AgentRow />` | Custom + shadcn `Tooltip` | `components/chat/agent-row.tsx` | Status: `idle`, `queued`, `running`, `done`, `failed` |
| 3 | `<DegradationNotice />` | shadcn `Alert` (amber variant) | `components/chat/degradation-notice.tsx` | `inline`, `expanded` |
| 4 | `<MultiCitationBadge />` | Extends existing `<CitationBadge />` | `components/chat/citation-badge.tsx` | `single`, `stacked`, `cluster`, `conflict` |
| 5 | `<SourceTabsPanel />` | shadcn `Tabs` (vertical) | `components/document-panel/source-tabs.tsx` | Inside Split-Pane right side |
| 6 | `<ConflictCompare />` | Custom 2-col grid | `components/document-panel/conflict-compare.tsx` | For `≠` citations |
| 7 | `<ProgressMilestone />` | Custom inline text | `components/chat/progress-milestone.tsx` | "Soft attention break" at T+30s |

**Animation tokens (all < 150ms per Design System Foundation):**
- Strip expand/collapse: `duration-150 ease-out`
- Status transition (running→done): emerald glow 600ms one-shot
- Spinner: `animate-spin` (1s linear) — 1 per row max
- **Forbidden:** Lottie, framer-motion spring, parallax (perf with 8+ concurrent rows)

**State layer:**
- Zustand store: `useOrchestraStore`
- Persistence: Rocicorp Zero mutator → PGLite snapshot mỗi 2s
- Cache: `(query_hash, agent_name)` 5-min TTL cho re-ask optimization

---

## 3. SSE Event Contract (TBD — Architect Input Required)

Frontend expects backend emit qua existing SSE pipe (Epic 7 `/api/v1/chat`). Event schemas cần finalize trong architecture.md:

```typescript
// Event names (đề xuất — architect confirm)
type OrchestraEvent =
  | { event: 'orchestra.spawn'; data: { query_hash: string; agents: AgentManifest[] } }
  | { event: 'orchestra.update'; data: { agent_name: string; status: 'running'; elapsed_ms: number } }
  | { event: 'orchestra.done';   data: { agent_name: string; duration_ms: number; summary: AgentSummary } }
  | { event: 'orchestra.fail';   data: { agent_name: string; reason: FailReason } }
  | { event: 'orchestra.cancel'; data: { at_ms: number; partial_results: boolean } }
  | { event: 'orchestra.complete'; data: { total_ms: number; success: number; failed: number } };

type FailReason = 'rate_limit' | 'timeout' | 'unavailable' | 'cancelled_by_user';

interface AgentManifest {
  name: string;         // e.g. "tokenomics_analyst"
  display_name: string; // e.g. "tokenomics"
  estimated_p50_ms: number; // for ETA heuristic
}

interface AgentSummary {
  fact_count: number;
  sources: string[];    // e.g. ["Messari", "CryptoRank"]
}
```

**Open questions cho Architect:**
- [ ] Event naming convention consistent với existing Epic 7 streaming events?
- [ ] Backpressure: rate-limit `orchestra.update` mỗi 500ms server-side hay client-side debounce?
- [ ] Multi-session: nếu user có 2 tabs mở cùng query, orchestra shared hay duplicated?
- [ ] Conflict detection: backend emit `orchestra.conflict` event khi 2 agents return khác data, hay FE tự detect từ citation metadata?

---

## 4. Telemetry Events (for NFR-Q1..Q4 Quality Gates)

**Reference:** `stories/0-5-parallel-execution-validation.md` — `ParallelismTelemetryMiddleware`.

Frontend emit 8 events qua existing analytics pipe:

| # | Event | Payload | Purpose | Quality Gate |
|---|-------|---------|---------|--------------|
| 1 | `orchestra.spawn` | `{query_hash, agents: string[], spawn_count}` | Smart selection accuracy | FR-34 |
| 2 | `orchestra.agent_done` | `{agent_name, duration_ms, source_count}` | Parallelism check | NFR-CS2 |
| 3 | `orchestra.agent_fail` | `{agent_name, reason}` | Degradation rate | NFR-Q3 |
| 4 | `orchestra.completed` | `{total_duration_ms, success_count, fail_count, p95_bucket}` | P95 tracking | NFR-Q4 |
| 5 | `orchestra.cancelled` | `{at_ms, partial_results: bool}` | UX abandon signal | Product health |
| 6 | `citation.click` | `{badge_type, source_count, conflict: bool}` | Multi-source engagement | Trust signal |
| 7 | `degradation.notice_expanded` | `{}` | User actively reads failure notice | Trust signal |
| 8 | `degradation.retry_clicked` | `{agent_name}` | Recovery flow effectiveness | NFR-Q3 UX |

**Dashboard tiles (đề xuất Khoa-persona):**
- P95 full-suite latency (target < 90s)
- % requests với ≥ 1 degradation
- % users click retry vs abandon
- % conflict citations được explore

---

## 5. Implementation Phasing → Sprint Mapping

| Phase | Scope | Map vào Sprint | Duration đề xuất |
|-------|-------|----------------|------------------|
| **9.0 MVP UX** | `OrchestraStrip` + `AgentRow` + `DegradationNotice` + extends `CitationBadge` to `stacked` variant | Phase 1 sprint (song song với Stories 9-1, 9-4 backend done) | ~5 days |
| **9.1 Trust polish** | `ConflictCompare` + `SourceTabsPanel` + 8 telemetry events wiring | Phase 2 sprint (sau 9-2, 9-5 backend done) | ~4 days |
| **9.2 Advanced** | Background mode pinning (status bar) + 5-min cache layer + `ProgressMilestone` soft-attention copy A/B test | Phase 3 sprint (sau 9-3, 9-6 backend done + spike validated) | ~5 days |

**Gating:**
- 9.0 → 9.1: NFR-Q3 graceful degradation gate đạt > 95% (reviewed qua logged events 2 tuần).
- 9.1 → 9.2: NFR-Q4 P95 < 90s gate đạt trên sample 100 full-suite queries.

**New story đề xuất:** `9-FE-1: Orchestra Conductor Strip + Citation Stacking (Phase 2 MVP)` — owner: Frontend. Required inputs: SSE event spec finalized (Sec 3) + 7 components scaffolded. AC mapping 1:1 với telemetry events Sec 4.

---

## 6. Non-Goals (Explicit)

Để tránh scope creep ở Architect window:

- ❌ **KHÔNG** redesign Split-Pane layout — reuse hiện có từ Epic 2.4.
- ❌ **KHÔNG** thay đổi baseline streaming UI từ Epic 7 (`/api/v1/chat` SSE contract). Chỉ **thêm** event names mới.
- ❌ **KHÔNG** tạo new design direction — visual language (Zinc/Slate + Indigo accent + shadcn/ui) đã established, chỉ extend.
- ❌ **KHÔNG** chat input UX thay đổi — trigger detection (FR-34) hoàn toàn backend-side.
- ❌ **KHÔNG** mobile redesign — tablet/mobile dùng pattern "bottom sheet orchestra strip" đã cover ở Platform Strategy (Sec 1), không cần separate story.

---

## 7. Design Questions — RESOLVED by Architect (2026-04-23)

> **Status**: ✅ All 5 resolved. See `architecture.md` §9 Crypto Orchestra Architecture / §7 Decision Table for rationale.

| # | Question | Resolution (v1 MVP) | Source |
|---|----------|---------------------|--------|
| 1 | Agent display names i18n | **EN-only v1**; technical names human-readable; VN i18n deferred to v2 | arch §9.Q1 |
| 2 | Retry agent-level vs query-level | **Query-level only v1** — no single-agent re-spawn (backend complexity); v2 may add per-agent retry | arch §9.Q2 |
| 3 | Cancel cost semantics | **Best-effort terminate** — backend stops spawning new agents; in-flight LLM tokens still billed (user sees "partial, cancelled" with cost footnote) | arch §9.Q3 |
| 4 | Conflict threshold `[2≠4]` | **>5% delta** for numeric fields; FE detects (not backend); categorical mismatch = exact | arch §9.Q4 |
| 5 | Background mode cross-tab | **Single-tab MVP** — no BroadcastChannel sync v1; user must return to origin tab | arch §9.Q5 |

**Implementation impact**: No UX spec changes required — original recommendations (EN-only, 5% delta, single-tab) were adopted as-is. Retry + cancel semantics need FE implementation notes in Story 9-FE-1.

---

## 8. Files Touched / Create (summary)

**Create:**
- `components/chat/orchestra-strip.tsx`
- `components/chat/agent-row.tsx`
- `components/chat/degradation-notice.tsx`
- `components/chat/progress-milestone.tsx`
- `components/document-panel/source-tabs.tsx`
- `components/document-panel/conflict-compare.tsx`
- `stores/use-orchestra-store.ts` (Zustand)
- `lib/telemetry/orchestra-events.ts` (8 events)

**Modify:**
- `components/chat/citation-badge.tsx` (add `stacked`/`cluster`/`conflict` variants)
- `components/chat/chat-bubble.tsx` (slot cho `<OrchestraStrip />` above response)
- `components/chat/split-pane.tsx` (right-side accept `<SourceTabsPanel />`)
- Rocicorp Zero schema: add `orchestra_sessions` table (query_hash, agents[], timestamps) cho cache + background mode recovery.

**Architect needs to specify:**
- `app/schemas/sse_events.py` (or equivalent) — 6 Orchestra event types (Sec 3)
- `app/agents/new_chat/orchestra_telemetry.py` — emit events matching FE expectations
- Migration for `orchestra_sessions` table (if Rocicorp Zero-backed)

---

## 9. Why Skip UX Design Directions (Step 9)

**Decision:** NOT running full `bmad-create-ux-design` Step 9 (Design Directions / mood exploration).

**Rationale:**
- Epic 9 là **extension** cho hệ thống chat UI đã production từ Epic 1-7, không phải greenfield.
- Visual language đã established trong Section "Visual Design Foundation":
  - Color: Zinc/Slate dark base + Indigo/Teal accent
  - Typography: Inter + JetBrains Mono
  - Component: shadcn/ui + Tailwind
  - Animation: < 150ms rule
- Step 9 purpose là "chọn visual direction từ 6-8 variants" — đã không còn relevant.
- Continuing Step 9 sẽ tạo false exploration và risk design divergence khỏi existing product.

**What replaces it:** Direct extension via Sections 2-9 của "Crypto Orchestra UX" addendum, apply existing design tokens vào new components.

---

> **Handoff complete.** Architect window cần:
> 1. Finalize SSE event contract (Sec 3) trong `architecture.md`.
> 2. Define `orchestra_sessions` Rocicorp Zero schema.
> 3. Coordinate với Backend Lead về `ParallelismTelemetryMiddleware` (Story 0.5) để frontend consume events Sec 4.
> 4. Open 5 design questions Sec 7 với PM.
>
> Full UX rationale: `_bmad-output/planning-artifacts/ux-design-specification.md` → Section "Crypto Orchestra UX".
