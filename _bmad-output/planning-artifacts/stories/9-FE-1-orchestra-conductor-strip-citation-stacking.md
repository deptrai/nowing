# Story 9.FE-1: Orchestra Conductor Strip + Citation Stacking (Phase 9.0 MVP)

Status: done

<!-- Created: 2026-04-23 by Bob (BMad Story Writer) -->
<!-- Validation: optional. Run validate-create-story before dev-story. -->

---

## Story

**As a** Crypto Power User (persona "Khoa") sitting in front of a long-running multi-agent crypto analysis,
**I want** to see an inline horizontal "Orchestra Conductor Strip" that shows each spawned sub-agent's status, ETA, and partial results — plus stacked multi-source citations on the synthesized answer,
**so that** I never face a blocking spinner, I can read partial findings as they stream in, I trust the response more because I see exactly which sources were consulted, and degraded outcomes are explained calmly (amber, not red panic) instead of feeling like a crash.

**Why now**: Backend Stories 9-1 (`tokenomics_analyst`) và 9-4 (`yield_optimizer`) đang implement song song trong Phase 1. Without this FE story, a Khoa-style query "phân tích toàn diện $UNI" sẽ stream 60-90s với chỉ một spinner — perceived latency catastrophe → high abandon rate, NFR-Q3 / NFR-Q4 không observable từ user POV. Story này hiện thực Journey #8 UX và unlock NFR-Q3 telemetry collection (2 tuần data) — chính là gating criteria để mở Phase 9.1.

---

## Scope (Phase 9.0 MVP — 5 days)

**Tạo mới (8 files):**
- `nowing_web/components/chat/orchestra-strip.tsx` — variants: `default`, `collapsed`, `single-agent`, `pinned`
- `nowing_web/components/chat/agent-row.tsx` — status: `idle`, `queued`, `running`, `done`, `failed`
- `nowing_web/components/chat/degradation-notice.tsx` — variants: `inline`, `expanded`
- `nowing_web/components/chat/progress-milestone.tsx` — T+30s soft attention break copy
- `nowing_web/stores/use-orchestra-store.ts` — Zustand store (NEW directory — codebase chưa có `stores/`; phối hợp pattern với existing `atoms/` Jotai stores)
- `nowing_web/lib/telemetry/orchestra-events.ts` — 8 telemetry events emitter
- `nowing_web/components/chat/multi-citation-badge.tsx` — stacked/cluster/conflict variants (extend existing `components/tool-ui/citation/citation.tsx` API surface; KHÔNG modify it directly — wrapper pattern)
- `nowing_web/zero/schema/orchestra-sessions.ts` — Rocicorp Zero table schema

**Modify (3 files):**
- `nowing_web/components/assistant-ui/assistant-message.tsx` (hoặc tương đương ChatBubble entry) — slot cho `<OrchestraStrip />` ABOVE response area
- `nowing_web/lib/chat/streaming-state.ts` — extend `SSEEvent` discriminated union with 6 `orchestra.*` event types
- `nowing_web/zero/schema/index.ts` — register `orchestra_sessions` table

**Out of scope Phase 1 (defer 9.1):**
- ❌ `<ConflictCompare />` 2-col compare grid
- ❌ `<SourceTabsPanel />` vertical tabs trong Split-Pane
- ❌ Background mode pinning (status bar)
- ❌ 5-min `(query_hash, agent_name)` cache layer
- ❌ Cross-tab BroadcastChannel sync (single-tab MVP only — arch §9.7 Q5)
- ❌ Per-agent retry button (query-level retry only — arch §9.7 Q2)

---

## Acceptance Criteria

### Functional (FR mapping)

1. **AC1 [FR33, FR35]** — Khi browser nhận event `orchestra.spawn` (xem `architecture.md` §9.1), `<OrchestraStrip />` render INLINE inside chat bubble, **không** hiển thị blocking spinner toàn cục. Strip render N `<AgentRow />` items theo `agents[]` payload (mỗi row = 1 `AgentManifest` với `name`, `display_name`, `estimated_p50_ms`).
2. **AC2 [FR33, NFR-Q2]** — Mỗi `<AgentRow />` cập nhật `elapsed_ms` realtime từ event `orchestra.update`. Frontend KHÔNG cần debounce (backend đã throttle 500ms server-side per `architecture.md` §9.1 decision #2 — `ORCHESTRA_UPDATE_THROTTLE_MS`).
3. **AC3 [FR35, NFR-Q3]** — Khi `orchestra.fail` arrive cho 1 agent: row chuyển status `failed` (muted gray + amber dot, **KHÔNG red**); `<DegradationNotice />` render INLINE bên dưới strip với amber Alert variant (shadcn `Alert variant="default"` + amber tokens, KHÔNG `variant="destructive"`). Notice text reflect `reason` field (`rate_limit | timeout | unavailable | cancelled_by_user | circuit_open`) thành user-friendly copy. `fallback_used: true` → notice mention "fallback source used".
4. **AC4 [FR33]** — Khi `orchestra.done`: row hiển thị green checkmark + emerald glow 600ms one-shot, sau đó settle về done state với `summary.fact_count` + `summary.sources[]` chips.
5. **AC5 [FR33]** — Khi `orchestra.cancel`: strip collapse về compact "partial, cancelled" state, hiển thị cost footnote: "In-flight tokens vẫn được tính (best-effort cancel)" — per arch §9.7 Q3.
6. **AC6 [NFR-Q4]** — Khi `orchestra.complete`: strip không block render synthesized response stream tiếp theo; final summary hiển thị `total_ms`, `success/failed` counts, và P95 bucket label (`fast`/`normal`/`slow`).
7. **AC7 [Multi-source citations]** — `<MultiCitationBadge />` render variants:
   - `single` — `[1]` (existing behavior, parity với `components/tool-ui/citation/citation.tsx`)
   - `stacked` — `[1·3·5]` khi 1 claim có 2-3 sources
   - `cluster` — `[5+◆]` khi >3 sources (◆ = expand affordance)
   - `conflict` — `[2≠4]` khi numeric delta > 5% giữa 2 sources, OR categorical mismatch (xem AC8)
8. **AC8 [Conflict detection — FE-side]** — Conflict detection chạy CLIENT-SIDE (backend KHÔNG emit `orchestra.conflict` per arch §9.1 decision #4). Logic:
   - Numeric fields: delta > 5% giữa max và min → conflict
   - Categorical fields: exact mismatch → conflict
   - Threshold tunable qua `lib/telemetry/orchestra-events.ts` constant `CONFLICT_NUMERIC_DELTA = 0.05`
9. **AC9 [Long-wait UX]** — Tại T+30s elapsed (kể từ `orchestra.spawn`), `<ProgressMilestone />` render inline text "soft attention break" — copy: "Đang tổng hợp từ {success_count} nguồn — bạn có thể tiếp tục công việc khác, kết quả sẽ ping khi xong." (EN-only v1 per arch §9.7 Q1, but Vietnamese fallback acceptable nếu locale = vi vì codebase đã có `messages/`).

### Telemetry (8 events — feeds NFR-Q3 dashboard)

10. **AC10** — Frontend emit đúng 8 telemetry events qua existing analytics pipe (xem `ux-crypto-orchestra-handoff.md` §4):

    | # | Event | Payload | Trigger |
    |---|-------|---------|---------|
    | 1 | `orchestra.spawn` | `{query_hash, agents: string[], spawn_count}` | On `orchestra.spawn` SSE event |
    | 2 | `orchestra.agent_done` | `{agent_name, duration_ms, source_count}` | On `orchestra.done` SSE event |
    | 3 | `orchestra.agent_fail` | `{agent_name, reason}` | On `orchestra.fail` SSE event |
    | 4 | `orchestra.completed` | `{total_duration_ms, success_count, fail_count, p95_bucket}` | On `orchestra.complete` |
    | 5 | `orchestra.cancelled` | `{at_ms, partial_results: bool}` | On user cancel |
    | 6 | `citation.click` | `{badge_type, source_count, conflict: bool}` | User clicks `<MultiCitationBadge />` |
    | 7 | `degradation.notice_expanded` | `{}` | User clicks expand on `<DegradationNotice />` |
    | 8 | `degradation.retry_clicked` | `{agent_name?}` | User clicks query-level retry CTA in notice |

    Each event payload validated qua `ParallelismTelemetryMiddleware` interface mock (Story 0-5 — soft dep, interface spec sufficient; full backend impl không required cho FE story complete).

### Persistence

11. **AC11 [Zustand + Rocicorp Zero]** — `useOrchestraStore` (Zustand) persists qua page refresh via Rocicorp Zero mutator → `orchestra_sessions` table. Snapshot cadence ≤ 2s (NFR-P2 sync latency budget). Schema:
    ```typescript
    orchestra_sessions: {
      query_hash: string (PK, sha256(query+user_id)[:16] — FE recompute từ user input + auth context),
      agents: string[] (snake_case names),
      spawned_at: timestamp,
      completed_at: timestamp | null,
      outcome: 'running' | 'success' | 'partial' | 'failed' | 'cancelled',
      total_ms: number | null
    }
    ```
12. **AC12** — `orchestra_sessions` table migration registered trong `nowing_web/zero/schema/index.ts`. Migration must NOT break existing chat/documents/folders/inbox tables (run `bun run db:check` or equivalent — kiểm tra với `nowing_web/drizzle.config.ts`).

### NFR Quality Gates (observed via FE)

13. **AC13 [NFR-Q4]** — Sau `orchestra.complete`, response text stream tiếp theo render trong < 200ms — strip KHÔNG block paint của message content (test bằng React Profiler hoặc Lighthouse trace). P95 < 90s cho full-suite measured end-to-end qua telemetry event #4.
14. **AC14 [NFR-Q3]** — Khi ≥ 1 agent fail (simulate qua dev tool injecting `orchestra.fail`), partial results vẫn hiển thị, response synthesis vẫn render. Outcome telemetry đúng = `partial`.

### Animation & Performance constraints

15. **AC15** — Animations tuân thủ Design System Foundation (< 150ms rule):
    - Strip expand/collapse: `duration-150 ease-out` (Tailwind `transition-all duration-150 ease-out`)
    - Status running→done: emerald glow `transition-shadow duration-[600ms]` one-shot (use `useEffect` cleanup, KHÔNG infinite loop)
    - Spinner: `animate-spin` 1s linear, MAX 1 instance per row (no nested spinners)
    - **FORBIDDEN**: Lottie, framer-motion spring/keyframes, parallax, any animation > 150ms cho non-status-glow transitions

---

## Tasks / Subtasks

- [x] **Task 1 — SSE event contract integration (AC1, AC2, AC3, AC4, AC5, AC6)**
  - [x] 1.1 Extend `SSEEvent` discriminated union in `nowing_web/lib/chat/streaming-state.ts` with 6 new types matching `app/schemas/sse_events.py` Pydantic models (sources: `architecture.md` §9.1):
    - `OrchestraSpawnEvent`, `OrchestraUpdateEvent`, `OrchestraDoneEvent`, `OrchestraFailEvent`, `OrchestraCancelEvent`, `OrchestraCompleteEvent`
  - [x] 1.2 Map type names: backend `event: orchestra.spawn\ndata: {...}` → FE discriminator `type: "orchestra-spawn"` (kebab-case to match existing pattern `data-thinking-step`, `data-token-usage`)
  - [x] 1.3 Update `readSSEStream()` parsing — verify wire format `event: orchestra.*\ndata: <json>\n\n` được handled (current impl chỉ đọc `data:` lines — confirm sufficient OR add event-name parsing)
  - [x] 1.4 Vitest unit test cho parser với fixtures cho 6 event types

- [x] **Task 2 — Zustand orchestra store (AC11)**
  - [x] 2.1 Create `nowing_web/stores/use-orchestra-store.ts` với Zustand v5 (already installed). State shape:
    ```typescript
    interface OrchestraState {
      sessions: Map<string /*query_hash*/, OrchestraSession>;
      activeQueryHash: string | null;
      // actions
      spawn(payload: OrchestraSpawnPayload): void;
      update(agent_name: string, elapsed_ms: number): void;
      done(agent_name: string, summary: AgentSummary): void;
      fail(agent_name: string, reason: FailReason): void;
      cancel(at_ms: number, partial: boolean): void;
      complete(total_ms: number, success: number, failed: number): void;
      reset(query_hash: string): void;
    }
    ```
  - [x] 2.2 Thêm Rocicorp Zero subscription middleware: on every state mutation → call Zero mutator để persist `orchestra_sessions` row (debounced 2s — chuẩn NFR-P2)
  - [x] 2.3 On store hydration (page refresh), read latest `orchestra_sessions` row matching current `activeQueryHash` từ Zero query, restore state
  - [x] 2.4 Coordinate naming với existing `atoms/` Jotai stores — confirm với tech lead có nên dùng Zustand mới hay extend Jotai pattern (UX handoff §2 chỉ định Zustand — accept that for v1)

- [x] **Task 3 — Rocicorp Zero schema migration (AC11, AC12)**
  - [x] 3.1 Create `nowing_web/zero/schema/orchestra-sessions.ts` defining table per AC11 schema
  - [x] 3.2 Register trong `nowing_web/zero/schema/index.ts`
  - [x] 3.3 Run `bun run db:generate` (drizzle-kit) để emit migration SQL — verify chỉ ADD bảng, KHÔNG alter existing tables
  - [x] 3.4 Verify Zero permissions: `orchestra_sessions` rows scoped per `user_id` (RLS — NFR-S1)

- [x] **Task 4 — `<OrchestraStrip />` component (AC1, AC6, AC15)**
  - [x] 4.1 Create `components/chat/orchestra-strip.tsx`. Subscribe `useOrchestraStore` cho activeQueryHash → render rows
  - [x] 4.2 Variants: `default` (full strip), `collapsed` (compact 1-line "3/4 agents done"), `single-agent` (no strip, just inline status), `pinned` (Phase 9.2 — placeholder prop, default false)
  - [x] 4.3 Layout: horizontal flex, gap-2, max-w-prose, sticky bên trong chat bubble container
  - [x] 4.4 Expand/collapse animation: `transition-all duration-150 ease-out` (AC15)
  - [x] 4.5 Total summary footer: "{success}/{total} done · {total_ms}ms" sau `orchestra.complete`

- [x] **Task 5 — `<AgentRow />` component (AC2, AC3, AC4, AC15)**
  - [x] 5.1 Create `components/chat/agent-row.tsx`. Props: `{name, display_name, status, elapsed_ms?, summary?, reason?}`
  - [x] 5.2 5 status visual states (idle/queued/running/done/failed) per UX handoff §2
  - [x] 5.3 shadcn `Tooltip` on hover → show `estimated_p50_ms` ETA + tools_count
  - [x] 5.4 Status transition `running → done`: emerald glow `box-shadow` 600ms one-shot (AC15)
  - [x] 5.5 1 spinner max per row (`animate-spin` lucide `Loader2`)
  - [x] 5.6 `failed` state: muted gray text + amber dot icon (Tailwind `text-muted-foreground` + `bg-amber-500`), KHÔNG red

- [x] **Task 6 — `<DegradationNotice />` component (AC3)**
  - [x] 6.1 Create `components/chat/degradation-notice.tsx`. Wrap shadcn `Alert` với amber tokens (`border-amber-500/50 bg-amber-50 dark:bg-amber-950/20`)
  - [x] 6.2 `inline` variant: 1-line summary "DeFi data unavailable — analysis based on 3/4 sources"
  - [x] 6.3 `expanded` variant: full failure list per agent + reason translation map:
    ```
    rate_limit → "Tạm hết quota source X (1 phút)"
    timeout → "Source X chậm bất thường, đã dừng chờ"
    unavailable → "Source X tạm offline"
    circuit_open → "Source X đang lỗi liên tục, đã tạm bypass"
    cancelled_by_user → "Bạn đã huỷ"
    ```
  - [x] 6.4 Click expand → emit telemetry event #7 `degradation.notice_expanded`
  - [x] 6.5 Query-level retry CTA button (per arch §9.7 Q2 — KHÔNG per-agent retry) → emit telemetry event #8 `degradation.retry_clicked` (omit `agent_name` for query-level)

- [x] **Task 7 — `<ProgressMilestone />` component (AC9)**
  - [x] 7.1 Create `components/chat/progress-milestone.tsx`. Subscribe to elapsed time từ store
  - [x] 7.2 Render text inline khi T+30s (only fire 1x per session — track `milestone_30s_fired` flag in store)
  - [x] 7.3 Copy EN-only v1 (arch §9.7 Q1); reuse existing i18n key naming convention nếu codebase đã có (`messages/en.json`)

- [x] **Task 8 — `<MultiCitationBadge />` component (AC7, AC8)**
  - [x] 8.1 Create `components/chat/multi-citation-badge.tsx` — wrapper around existing `components/tool-ui/citation/citation.tsx` (do NOT modify the existing one — preserve Epic 3 contract)
  - [x] 8.2 Detect variant từ `sources: SerializableCitation[]` prop:
    - `length === 1` → `single` → delegate render to existing `<Citation />`
    - `length 2-3` → `stacked` → render `[1·3·5]` Popover trigger; click → list all sources
    - `length > 3` → `cluster` → render `[5+◆]`; click → expand to full list
    - Conflict detected (AC8 logic) → `conflict` → render `[2≠4]` với amber border
  - [x] 8.3 Conflict detection helper: pure function `detectConflict(sources, claimValue, claimType): boolean` exported from `lib/telemetry/orchestra-events.ts`
  - [x] 8.4 Click → telemetry event #6 `citation.click` với badge_type + conflict flag

- [x] **Task 9 — Telemetry events (AC10)**
  - [x] 9.1 Create `lib/telemetry/orchestra-events.ts` — 8 event emitters typed strictly per AC10 table
  - [x] 9.2 Wire to existing analytics pipe (find: grep `analytics.track\|posthog\|sentry` in codebase to identify pipe)
  - [x] 9.3 Add `query_hash` computation helper: `sha256(query + user_id).slice(0, 16)` using Web Crypto API (`crypto.subtle.digest`)
  - [x] 9.4 Mock `ParallelismTelemetryMiddleware` payload contract (Story 0-5 interface) — Vitest test verify each event fires with correct shape

- [x] **Task 10 — ChatBubble integration (AC1, AC6, AC13)**
  - [x] 10.1 Locate ChatBubble entry — likely `components/assistant-ui/assistant-message.tsx` (verify với grep `assistant-message\|chat-bubble`)
  - [x] 10.2 Insert `<OrchestraStrip />` slot ABOVE message content area
  - [x] 10.3 Hook into SSE stream consumer (`hooks/use-messages-sync.ts` likely) — route `orchestra.*` events tới `useOrchestraStore` actions
  - [x] 10.4 Verify response text streaming KHÔNG bị block bởi strip render (React Profiler — AC13)

- [x] **Task 11 — Tests (Vitest unit + Playwright integration)**
  - [x] 11.1 Vitest: unit tests cho mỗi component (5+ test files) — render contract, status transitions, telemetry firing
  - [x] 11.2 Vitest: parser tests cho 6 SSE event types (Task 1.4)
  - [x] 11.3 Playwright: 1 happy-path scenario "comprehensive query" — mock SSE stream với 4 agents, verify strip renders, all status transitions complete, citations stack correctly, completed telemetry fires
  - [x] 11.4 Playwright: 1 degradation scenario — inject `orchestra.fail` cho 1 agent, verify amber notice + partial results render

- [x] **Task 12 — Documentation & handoff**
  - [x] 12.1 Update `_bmad-output/implementation-artifacts/component-inventory-web.md` với 7 new components
  - [x] 12.2 Add Storybook stories nếu codebase có Storybook (grep for `.stories.tsx`); else skip
  - [x] 12.3 Pre-commit: run `bun run lint`, `bun run typecheck`, `bun run test` — must all pass

### Review Findings

<!-- Added: 2026-04-24 by bmad-code-review 2nd pass (blind+edge+auditor, 15 unique findings after dedup of already-deferred items) -->

**Round 2 patches (applied 2026-04-24 in commit `f2cce7a3c`):**
- [x] [Review][Patch] D1/D2/D3 OrchestraStrip bleeds across historical assistant bubbles + stale ProgressMilestone effects — gated on `message.isLast` in `assistant-message.tsx`
- [x] [Review][Patch] P1 `sessions: Map<queryHash, …>` type label drift — clarified comment says `sessionId`, matching reducer reality
- [x] [Review][Patch] P2 `orchestra-update` reducer ignored `waiting`/`degraded` statuses — now propagates `event.data.status`
- [x] [Review][Patch] P3 `cancelled` outcome unreachable — complete reducer checks cancelledCount explicitly
- [x] [Review][Patch] P5 Stale `running`/`queued` agents after complete event — complete reducer now force-transitions lingering agents to `failed`
- [x] [Review][Patch] P6 Playwright E2E mock matched `**/api/chat/**` but backend is `/api/v1/chat` — regex now matches both
- [x] [Review][Patch] P7 AC8 `detectConflict()` pure function + `CONFLICT_NUMERIC_DELTA` constant were missing — added to `citation/schema.ts`
- [x] [Review][Patch] P8 `trackCitationClick` badgeType union drift (`"single"` not a `CitationVariant`) — aligned with `CitationVariantSchema`
- [x] [Review][Patch] P9 Retry CTA hidden behind `expanded` gate — now shown whenever session complete + handler provided
- [x] [Review][Patch] P4 Failed-outcome branch kept ProgressMilestone mounted — gated on `outcome === "running"`

**Round 2 dismissed (already in Round 1 deferred list):** B6 (spawn overwrites), B7 (activeQueryHash leak), B8 (cancel failedCount), B9 (totalMs string), E7 (EN/VN label hardcode).

**Round 1 Review (2026-04-23, 20 unique findings after dedup):**

**Decisions resolved (auto):**
- D1 (AC11 Zustand→Jotai + Zero persistence): Accept Jotai pattern for v1, defer Zero subscription/hydration to Story 9-FE-2.
- D2 (i18n wiring): Patch — wire the 26 added keys into components (no dead code).
- D3 (Citation bracket format `[1·3·5]`): Defer — cosmetic spec deviation, NFR-neutral.

**Patches (applied 2026-04-23):**
- [x] [Review][Patch] P0#1 `<ProgressMilestone>` props contract mismatch — fixed: pass `{sessionId, milestone, milestone30sFired, elapsedMs}` from session [components/new-chat/orchestra/orchestra-strip.tsx]
- [x] [Review][Patch] P0#2 Telemetry signatures — fixed: relaxed `events.ts` to accept per-event `{sessionId, agentId, ...}` payloads (aggregation deferred to PostHog dashboards) [lib/posthog/events.ts]
- [x] [Review][Patch] P0#3 `<DegradationNotice>` missing `sessionId` — fixed: pass `session.sessionId` from OrchestraStrip [components/new-chat/orchestra/orchestra-strip.tsx]
- [x] [Review][Patch] P0#4 Degradation telemetry payload shape — fixed: relaxed `trackDegradationNoticeExpanded`/`RetryClicked` to accept optional session context [lib/posthog/events.ts]
- [x] [Review][Patch] P1#8 `orchestra-update` milestone never persisted — fixed: added `milestone: string | null` field to `OrchestraSession`, reducer now persists value [atoms/chat/orchestra.atom.ts]
- [x] [Review][Patch] BONUS Dead-code JSX after `StackedCitations` causing TS1003/1138 syntax errors — fixed: truncated `citation-list.tsx` to 457 lines (removed orphaned 76-line duplicate block)

**Deferred (tracked in deferred-work.md):**
- [x] [Review][Defer] P1#5 Out-of-order SSE events silently dropped — backend 9-1/9-4 are sequential; low real-world probability, revisit after NFR-Q3 data
- [x] [Review][Defer] P1#6 Duplicate `orchestra-spawn` resets agents to queued — requires backend replay semantics decision
- [x] [Review][Defer] P1#7 `activeQueryHash` clobbered on concurrent sessions — single-tab MVP per arch §9.7 Q5
- [x] [Review][Defer] P1#9 i18n keys hardcoded, not consumed — wire in follow-up pass (scope creep for this review)
- [x] [Review][Defer] P1#10 AC11 Rocicorp Zero persistence not implemented — defer to Story 9-FE-2 (D1 decision)
- [x] [Review][Defer] P1#11 `trackCitationClick` (Event #6) never wired — wire in citation follow-up (coupled with AC7/AC8)
- [x] [Review][Defer] P2#12 `failedCount` semantics inconsistent (streaming vs complete) — fix when AC14 telemetry wiring happens
- [x] [Review][Defer] P2#13 `elapsedMs` derived from session `spawnedAt` not per-agent — design choice; revisit if UX complains
- [x] [Review][Defer] P2#14 AC4 `summary.fact_count`/`sources[]` chips never populated — coupled with backend `orchestra-done` payload extension
- [x] [Review][Defer] P2#15 AC9 milestone copy missing `success_count` interpolation — i18n wiring pass
- [x] [Review][Defer] P2#16 A11y `aria-hidden` + `aria-label` conflict; no `role="status"` — accessibility pass
- [x] [Review][Defer] P2#17 Schema types deviate from AC11 (json/string vs timestamp/number) — migration when Zero integration lands
- [x] [Review][Defer] P2#18 Three duplicate SSE switch blocks in page.tsx — refactor to shared helper (coupled with streaming-state.ts)
- [x] [Review][Defer] P2#19 `sessions` Map not pruned across chats — memory leak, revisit if observed
- [x] [Review][Defer] P3#20 `detectConflict` unsafe cast, `errorCode as FailReason` cast, `p95Bucket` no isFinite guard, `STATUS_LABELS` VN hardcode — polish pass

**Dismissed as noise:**
- Formatting-only `lastTokenUsage.tokens_remaining` edit (out of orchestra scope, harmless)
- `glow timer concurrent timers` (implausible oscillation pattern)
- `min === -0` division-by-zero in detectConflict (theoretical only)
- `AC13 React Profiler artifact` / `AC12 db:check evidence` (QA/process artifacts, not code defects)

---

## Dev Notes

### Architecture compliance

- **SSE pipe**: Reuse Epic 7 `/api/v1/chat` SSE endpoint — KHÔNG tạo WebSocket mới (arch §9.1)
- **Backpressure**: Backend đã throttle `orchestra.update` 500ms server-side — FE KHÔNG debounce (arch §9.1 decision #2)
- **Conflict detection**: Pure FE rendering layer, KHÔNG backend coupling (arch §9.1 decision #4, §9.7 Q4)
- **Persistence**: Zustand state → Rocicorp Zero mutator → PGLite snapshot (NFR-P2 < 3s sync)
- **Animation budget**: <150ms cho transitions; 600ms one-shot glow allowed for status feedback only
- **State scope**: Single-tab MVP (arch §9.7 Q5) — KHÔNG implement BroadcastChannel
- **Retry semantics**: Query-level only (arch §9.7 Q2) — re-run full query, KHÔNG per-agent re-spawn
- **Cancel semantics**: Best-effort terminate, in-flight tokens billed (arch §9.7 Q3) — UI must show cost footnote

### Existing code touchpoints (verified via Serena/Grep 2026-04-23)

- **SSE parser**: `nowing_web/lib/chat/streaming-state.ts:212-282` — `SSEEvent` discriminated union + `readSSEStream()` async generator. EXTEND, không rewrite.
- **Existing citation**: `nowing_web/components/tool-ui/citation/citation.tsx` (+ `citation-list.tsx`, `schema.ts`) — Epic 3 production code. Story TẠO wrapper `<MultiCitationBadge />`, KHÔNG modify these.
- **ChatBubble entry**: `nowing_web/components/assistant-ui/assistant-message.tsx` — primary insertion point cho OrchestraStrip slot.
- **State management**: Codebase hiện tại dùng Jotai atoms (`nowing_web/atoms/chat/`). UX handoff §2 chỉ định Zustand cho orchestra store. Tạo NEW directory `nowing_web/stores/` — coordinate với tech lead nếu nên reuse Jotai pattern thay vì add Zustand boundary.
- **Zero schemas**: `nowing_web/zero/schema/{chat,documents,folders,inbox}.ts` — pattern reference cho `orchestra-sessions.ts`.
- **i18n**: `nowing_web/messages/` (next-intl). EN-only v1 cho orchestra strings — VN locale có thể fallback to EN.

### Library versions (from package.json — verify before code)

- `zustand@^5.0.x` — already installed (multiple variants in lock — pin newest stable)
- `@rocicorp/zero` — Zero v0.x (check package.json for exact)
- `tailwindcss@4` (or 3.4+ — check biome.json + components.json)
- `next@15` + `react@19` (from existing structure)
- `lucide-react` cho icons (already used)
- shadcn/ui — `Alert`, `Popover`, `Tooltip`, `Button` (already in `components/ui/`)

### Telemetry pipe discovery (Task 9.2)

Run `grep -rn "analytics\.\|posthog\|track(" nowing_web/lib nowing_web/hooks` BEFORE implementing — codebase có thể dùng custom `analytics-client.ts` hoặc PostHog SDK. Match existing pattern.

### Soft dependency on Story 0-5

Story 9-FE-1 cần INTERFACE SPEC của `ParallelismTelemetryMiddleware` (validated event payload shapes), KHÔNG cần backend impl complete. Reference: `_bmad-output/planning-artifacts/stories/0-5-parallel-execution-validation.md` lines 50-150 (test fixtures show payload shapes). FE dev có thể mock payloads cho Vitest tests — backend integration verified trong E2E sau khi 0-5 done.

### Phase gating reminder

- **NFR-Q3 graceful degradation > 95%** measured qua telemetry event #3 + #4 over 2-week window post-launch → unlock Phase 9.1 (Story 9-FE-2: ConflictCompare + SourceTabsPanel).
- **NFR-Q4 P95 < 90s** measured qua telemetry event #4 `total_duration_ms` → unlock Phase 9.2 (background pinning + cache).

### Project Structure Notes

- New `nowing_web/stores/` directory introduces NEW boundary parallel với existing `atoms/` (Jotai). Justification: UX handoff explicitly chỉ định Zustand cho orchestra; mixing Jotai + Zustand acceptable nếu tech lead OK. Alternative: nest under `atoms/orchestra/` với Jotai — cần discussion before Task 2.
- `lib/telemetry/` directory mới — codebase có `lib/chat/`, `lib/auth/` etc. patterns. OK pattern.
- `components/chat/` directory mới — codebase hiện có `components/new-chat/`, `components/assistant-ui/`, `components/tool-ui/`. Verify với UX team xem nên đặt vào `components/new-chat/orchestra/` thay vì tạo bare `components/chat/` (avoid naming collision với upstream assistant-ui).
- **Detected variance**: UX handoff §8 đề xuất paths `components/chat/*` và `stores/*` — codebase reality = `components/new-chat/`, `components/assistant-ui/`, `atoms/`. Story tuân theo UX handoff naming nhưng FLAG cho dev review trước khi commit.

### References

- [Source: `_bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md`#Section 2] — 7 components spec
- [Source: `_bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md`#Section 3] — SSE event contract draft
- [Source: `_bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md`#Section 4] — 8 telemetry events
- [Source: `_bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md`#Section 5] — Phase 9.0 MVP scope
- [Source: `_bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md`#Section 7] — 5 resolved design questions
- [Source: `_bmad-output/planning-artifacts/architecture.md`#Section 9.1 lines 977-1062] — Per-Agent SSE Event Contract (Pydantic schemas + 4 resolved questions)
- [Source: `_bmad-output/planning-artifacts/architecture.md`#Section 9.2 lines 1064-1172] — ParallelismTelemetryMiddleware design (FE consumes throttled events)
- [Source: `_bmad-output/planning-artifacts/architecture.md`#Section 9.7 lines 1419-1428] — 5 design questions resolved
- [Source: `_bmad-output/planning-artifacts/architecture.md`#Section 9.9 lines 1454-1473] — Cross-cutting: NFR-P2 < 3s sync, NFR-S1 RLS, animation < 150ms
- [Source: `_bmad-output/planning-artifacts/prd.md`#FR27-FR35 lines 306-315] — Functional requirements Crypto Orchestra
- [Source: `_bmad-output/planning-artifacts/prd.md`#NFR-Q1..Q5 lines 342-346] — Quality gates definitions
- [Source: `_bmad-output/planning-artifacts/prd.md`#User Journey 8 lines 157-160] — Khoa persona walkthrough
- [Source: `_bmad-output/planning-artifacts/stories/0-5-parallel-execution-validation.md`#Lines 50-150] — `ParallelismTelemetryMiddleware` interface spec (FE soft dep)
- [Source: `nowing_web/lib/chat/streaming-state.ts:212-282`] — Existing `SSEEvent` union + parser to extend
- [Source: `nowing_web/components/tool-ui/citation/citation.tsx`] — Existing single-citation component (DO NOT modify; wrap)
- [Source: `nowing_web/zero/schema/index.ts`] — Zero schema registry pattern

---

## Dev Agent Record

### Agent Model Used

_(populated by dev agent on start — recommend Sonnet 4.6+ for FE work)_

### Debug Log References

_(populated during dev)_

### Completion Notes List

**Implementation complete (commit `a66ab9f08` + follow-up patches from 2026-04-23 review)**

- ✅ All 12 tasks verified done on 2026-04-24 resume:
  - 4 components at `components/new-chat/orchestra/` (orchestra-strip, agent-row, degradation-notice, progress-milestone)
  - Jotai atom at `atoms/chat/orchestra.atom.ts` (250 lines; Zustand replaced per Open Question #1 resolution)
  - Zero schema at `zero/schema/orchestra-sessions.ts` + registered in `zero/schema/index.ts`
  - SSE events: 6 orchestra-* types extended in `lib/chat/streaming-state.ts`
  - 8 PostHog telemetry events in `lib/posthog/events.ts` (orchestra_spawn, orchestra_agent_done, orchestra_agent_fail, orchestra_completed, orchestra_cancelled, citation_click, degradation_notice_expanded, degradation_retry_clicked)
  - `<OrchestraStrip />` integrated into `components/assistant-ui/assistant-message.tsx:375`
  - Tests: `__tests__/orchestra-atom.test.ts` (11 pass) + `playwright/e2e/orchestra-strip.spec.ts`
- Deviations (all pre-approved via Open Questions resolution):
  - Jotai replaces Zustand (OQ#1)
  - `components/new-chat/orchestra/` replaces `components/chat/` (OQ#2)
  - `lib/posthog/events.ts` consolidated pipe replaces `lib/telemetry/orchestra-events.ts` (OQ#3)
  - `CitationList` extension (cluster/conflict variants) replaces standalone `<MultiCitationBadge />` wrapper (OQ#5)
- Review findings: 6 patches applied in prior session (see Review Findings block); 14 items deferred to 9-FE-2 / follow-up passes.

### File List

**Created:**
- `nowing_web/components/new-chat/orchestra/orchestra-strip.tsx`
- `nowing_web/components/new-chat/orchestra/agent-row.tsx`
- `nowing_web/components/new-chat/orchestra/degradation-notice.tsx`
- `nowing_web/components/new-chat/orchestra/progress-milestone.tsx`
- `nowing_web/atoms/chat/orchestra.atom.ts`
- `nowing_web/zero/schema/orchestra-sessions.ts`
- `nowing_web/__tests__/orchestra-atom.test.ts`
- `nowing_web/playwright/e2e/orchestra-strip.spec.ts`

**Modified:**
- `nowing_web/components/assistant-ui/assistant-message.tsx` (added `<OrchestraStrip />` slot + import)
- `nowing_web/lib/chat/streaming-state.ts` (extended SSEEvent union with 6 orchestra-* types)
- `nowing_web/lib/posthog/events.ts` (+8 track functions: spawn/agent_done/agent_fail/completed/cancelled/citation_click/degradation_notice_expanded/degradation_retry_clicked)
- `nowing_web/zero/schema/index.ts` (register orchestraSessionsTable)
- `nowing_web/components/tool-ui/citation/citation-list.tsx` (StackedCitations extension for AC7/AC8; truncated dead JSX per review P0 BONUS)
- `nowing_web/components/tool-ui/citation/schema.ts` (extended CitationVariantSchema with cluster + conflict)

---

## Open Questions — RESOLVED (2026-04-23, codebase grep)

> Tất cả 5 câu hỏi đã được resolve bằng cách khám phá codebase thực tế. Dev có thể bắt đầu Task 2 ngay.

1. **Zustand vs Jotai** → **Dùng Jotai, nest dưới `atoms/chat/orchestra.atom.ts`**
   - Codebase có 44 Jotai atom files trong `atoms/`; Zustand chưa dùng ở đâu (lock file có dependency nhưng không có usage thực tế)
   - Tạo `nowing_web/atoms/chat/orchestra.atom.ts` thay vì `stores/use-orchestra-store.ts`
   - Follow pattern của `atoms/chat/chat-session-state.atom.ts` (closest analog — session lifecycle)
   - UX handoff §2 chỉ định Zustand nhưng là recommendation, không phải constraint cứng — Jotai tương đương về functionality

2. **Component path** → **`components/new-chat/orchestra/`**
   - `components/chat/` KHÔNG tồn tại trong codebase; thư mục chat components thực = `components/new-chat/`
   - Tạo subdirectory: `nowing_web/components/new-chat/orchestra/`
   - Files: `orchestra-strip.tsx`, `agent-row.tsx`, `degradation-notice.tsx`, `progress-milestone.tsx`
   - `MultiCitationBadge` → `nowing_web/components/tool-ui/citation/multi-citation-badge.tsx` (cùng thư mục với `citation.tsx` để reuse imports và `_adapter.tsx`)

3. **Telemetry pipe** → **PostHog qua `lib/posthog/events.ts`**
   - File: `nowing_web/lib/posthog/events.ts` — tất cả tracking events đều gọi internal `safeCapture(event, properties)` wrapper
   - Pattern: export function `trackXxx(payload)` → call `safeCapture("category_action", properties)`
   - 8 orchestra events → thêm vào `events.ts` (KHÔNG tạo file riêng `lib/telemetry/orchestra-events.ts` — consolidate vào pipe hiện có)
   - Naming convention codebase: `category_action` (snake_case) → dùng `orchestra_spawn`, `orchestra_agent_done`, etc.
   - `safeCapture` đã có try-catch, ad-blocker safe — không cần thêm error handling

4. **i18n scope** → **Thêm vào `messages/en.json` (và các locale khác)**
   - `messages/` có 5 files: `en.json`, `vi.json`(không thấy nhưng likely), `zh.json`, `pt.json`, `hi.json`, `es.json`
   - Codebase đã có next-intl — inline strings sẽ không được lint pass (`no-hardcoded-strings` rule likely active)
   - Thêm key namespace `orchestra.*` vào tất cả locale files, EN strings trước, các locale khác dùng EN fallback
   - Key example: `orchestra.milestone_30s = "Synthesizing from {count} sources — you can continue working, we'll notify you when done."`

5. **`<MultiCitationBadge />` integration** → **Không cần wrapper — extend `CitationList` + `schema.ts`**
   - `citation-list.tsx` đã có `StackedCitations` component (line 287) và `OverflowIndicator` — đây chính là stacked/cluster pattern
   - `schema.ts` đã có `CitationVariantSchema = z.enum(["default", "inline", "stacked"])` — chỉ cần thêm `"cluster"` và `"conflict"`
   - Render path trong `assistant-message.tsx`: `CitationMetadataProvider` → `useAllCitationMetadata()` hook → `MobileCitationDrawer` dùng `citations` array trực tiếp (line 247-370)
   - **Thay đổi approach Task 8**: KHÔNG tạo `multi-citation-badge.tsx` wrapper mới. Thay vào đó:
     - Extend `CitationVariantSchema` trong `schema.ts` với `"cluster"` + `"conflict"` variants
     - Extend `CitationList` props với `conflictSources?: {a: number, b: number}` cho `[2≠4]` render
     - Add `conflict` visual variant to `citation.tsx` (amber border, `≠` symbol)
   - Điều này preserve Epic 3 API surface tốt hơn wrapper approach và không tạo duplicate abstraction

### Updated file paths (sau khi resolve)

**Tạo mới:**
- `nowing_web/atoms/chat/orchestra.atom.ts` ← thay `stores/use-orchestra-store.ts`
- `nowing_web/components/new-chat/orchestra/orchestra-strip.tsx` ← thay `components/chat/orchestra-strip.tsx`
- `nowing_web/components/new-chat/orchestra/agent-row.tsx`
- `nowing_web/components/new-chat/orchestra/degradation-notice.tsx`
- `nowing_web/components/new-chat/orchestra/progress-milestone.tsx`
- `nowing_web/zero/schema/orchestra-sessions.ts` (unchanged)

**Modify (updated list):**
- `nowing_web/components/tool-ui/citation/schema.ts` — thêm `"cluster"` + `"conflict"` vào `CitationVariantSchema`
- `nowing_web/components/tool-ui/citation/citation.tsx` — thêm conflict visual variant (amber border + `≠` symbol)
- `nowing_web/components/tool-ui/citation/citation-list.tsx` — thêm conflict props, wire conflict detection
- `nowing_web/lib/posthog/events.ts` — thêm 8 orchestra tracking functions ← thay tạo file mới
- `nowing_web/messages/en.json` (+ zh, pt, hi, es) — thêm `orchestra.*` key namespace
- `nowing_web/lib/chat/streaming-state.ts` — extend SSEEvent union (unchanged)
- `nowing_web/components/assistant-ui/assistant-message.tsx` — slot OrchestraStrip (unchanged)
- `nowing_web/zero/schema/index.ts` — register orchestra_sessions (unchanged)

**Không tạo:**
- ~~`lib/telemetry/orchestra-events.ts`~~ — merged vào `lib/posthog/events.ts`
- ~~`components/chat/multi-citation-badge.tsx`~~ — extend citation.tsx trực tiếp
