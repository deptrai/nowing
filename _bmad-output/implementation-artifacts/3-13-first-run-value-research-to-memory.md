---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 3-13-first-run-value-research-to-memory
status: done
---

# Story 3.13: First-Run Value — Research Run sinh ra Memory

**Status:** done
**Epic:** 3 — Knowledge Base + Long-Term Memory
**Priority:** HIGH — first-run value / FR-40
**Requirements:** FR-40, FR-32, NFR-1b, M1
**Architecture:** AD-11, AD-11.1, AD-18
**Dependencies:** Story 3.8 và 8.8 đã hoàn thành. Story 8.7 code-complete theo sprint status nhưng P0 human-review gate vẫn mở; story này chỉ reuse `check_extract_allowed` sau khi re-verify baseline và không được merge-ready nếu caveat đó chưa được resolve hoặc chấp nhận rõ ràng. Story 3.13 có thể triển khai song song với 3.14 nhưng không được đánh dấu done cho tới khi bounded injection contract của 3.14 có trên integration baseline và regression test chứng minh research memory đi qua cùng ngân sách 8.000 chars. Story 9.6a là dependency mềm cho provenance recipe đầy đủ; bản tối thiểu của story này không chờ 9.6a.

## Story

Là người dùng mới của Nowing,
tôi muốn research/scrape run đầu tiên tự tạo ra những memory bền vững,
để `nowing_recall` có nội dung hữu ích ngay trong session đầu mà không cần chat trước hoặc dữ liệu mẫu giả.

## Goal and Current Reality

Tại baseline `25ba542c2`:

- Registry có 15 research-producing capabilities: `amazon.scrape`, `google_maps.scrape`, `google_maps.reviews`, `google_search.scrape`, `instagram.scrape`, `instagram.details`, `reddit.scrape`, `tiktok.scrape`, `tiktok.comments`, `tiktok.trending`, `tiktok.user_search`, `web.crawl`, `youtube.scrape`, `youtube.comments` và `chainlens.research`.
- REST door có sync (`record_run`) và async (`create_pending_run` rồi `finalize_run`); agent door baseline chỉ có sync `record_run`, không có async agent dispatcher.
- `Run` giữ `workspace_id`, nullable `user_id`, `capability`, immutable input snapshot, serialized `output_text`, status và cost. REST truyền `user_id`; agent door baseline chưa truyền `user_id`, nên attribution phải được sửa trước khi agent-origin extraction có thể qua anonymous guard.
- `MemoryExtractionService` chỉ có `extract_from_turn`; caller duy nhất là Celery task sau assistant finalization.
- Enum `MemorySourceType.SCRAPER_RUN` đã tồn tại, nhưng chưa có writer nào tạo scraper-run memory và chưa có `source_run_id` UUID provenance.
- `Memory.source_id` là integer còn `Run.id` là UUID; không được ép UUID vào `source_id` hoặc đổi kiểu cột này.
- `runs` có retention 30 ngày và cleanup cơ hội. Memory không được phụ thuộc cứng vào lifecycle của run log.
- Auto extraction đã có global kill-switch, per-workspace opt-in, spend cap, rate limit, anonymous guard, confidence threshold, max-items và `memory_create` token accounting.
- Không seed welcome/sample memory. Dữ liệu giả làm sai mental model và gây rác cho injection.

## Resolved Design Decisions

### D1 — Hook sau successful run, không hook riêng từng platform

Research-memory extraction được kích hoạt từ shared run-completion seam sau khi `Run` trạng thái thành công đã commit. Không thêm callback vào 15 executor và không duplicate logic giữa REST/agent hoặc sync/async.

Executable seam bắt buộc là helper dùng chung `enqueue_run_memory_extraction_after_commit(run_id)`, chỉ được gọi sau khi `record_run` hoặc `finalize_run` return thành công và transaction ghi run đã commit. Baseline coverage là REST sync + REST async + agent sync; story không giả định một async agent door chưa tồn tại.

Mọi capability đang đăng ký trong capability registry là research-producing ở baseline. Core helpers như `read_run` và `search_run` không đi qua registry recorder này và không được extract lại.

Failed, cancelled hoặc still-running run không tạo memory.

### D2 — Extraction ngoài request critical path

Run response phải hoàn tất độc lập với memory extraction. Shared completion seam chỉ enqueue durable background work sau commit; không gọi LLM, embedding hoặc repository inline trong REST/agent response và không làm successful scrape thất bại nếu enqueue/extraction lỗi.

Task phải load `Run` bằng run UUID và mở session riêng. Celery retry chỉ dùng cho transient LLM/network failures; auth/config failures giữ semantics hiện có của chat extraction.

Tái dùng module/pattern của `memory_extraction_task.py`. Transient failure phải retry; auth/config/validation failure phải terminal, không retry và không thay đổi kết quả capability đã trả.

### D3 — Tái dùng canonical extraction policy, không tạo memory subsystem thứ hai

Refactor phần dùng chung của `MemoryExtractionService` để cả chat-turn và research-run paths dùng chung:

- extraction system prompt và untrusted-content boundary;
- JSON parsing/validation;
- confidence threshold và max-items;
- `check_extract_allowed` authoritative gate;
- `MemoryRepository.create_memory` cho embedding/dedupe/versioning/events;
- `record_token_usage` với `usage_type=memory_create`;
- transaction discipline và pending `memory.changed` event flush.

Research path được phép có source-specific prompt builder nhưng không copy toàn bộ service hoặc tự insert `Memory` rows.

Chat path hiện cho phép per-fact persistence failure và commit phần còn lại; run path không được kế thừa behavior đó. Run extraction phải rollback toàn bộ memory batch, `memory_create` usage và completion marker nếu bất kỳ embedding/persistence step nào thất bại, trong khi `extract_from_turn` vẫn backward-compatible trừ khi một story riêng thay đổi contract chat.

### D4 — Provenance tối thiểu trong story này

Thêm `Memory.source_run_id` UUID nullable, soft reference, không foreign key cứng. Khi tạo memory từ run:

- `source_type = SCRAPER_RUN`;
- `source_id = NULL`;
- `source_run_id = Run.id`;
- workspace và creator lấy từ run;
- `research_thread_id` chỉ set khi có mapping hợp lệ, không suy đoán từ string `Run.thread_id`.

Agent door phải truyền active chat/user context vào `record_run(user_id=...)`. Nếu không có trustworthy creator, run vẫn được ghi nhưng extraction skip trước LLM với structured `missing_creator`/anonymous reason; không tự suy diễn workspace owner và không bypass `check_extract_allowed`. `research_thread_id` chỉ được set từ một root `NewChatThread` đã load và validate; subagent-shaped `Run.thread_id` như `parent::task:call_x` không được copy thẳng.

Không đổi kiểu `Memory.source_id`. Không kéo retention của `runs`. Không giữ `Run.output_text` vô hạn.

Story 9.6a sẽ sở hữu recipe đầy đủ `source_capability` + immutable `source_input`, backfill/hardening và contract phục vụ re-validation. Nếu 9.6a đã merge trước khi implement story này thì writer phải populate các field đó; nếu chưa, story này chỉ ghi `source_run_id` và không tạo schema trùng.

### D5 — Source payload có chặn trên và không thực thi instruction trong dữ liệu

Prompt research extraction chứa capability, input snapshot và serialized output của run. Dùng serialized persisted representation thay vì gọi lại capability.

Input/output được coi là dữ liệu không tin cậy. Prompt phải nói rõ không follow instruction nằm trong scraped content. Toàn bộ source gồm capability + serialized input + serialized output phải nằm trong deterministic `RUN_MEMORY_SOURCE_CHAR_CAP`; phân bổ/truncation phải ổn định và test riêng cho input lớn, output lớn và cả hai cùng lớn. Không gửi payload vô hạn và không gọi lại capability.

Không tạo memory từ output rỗng hoặc chỉ có whitespace. Không ghi nguyên payload thành một memory mặc định; chỉ ghi facts qua extractor và threshold hiện có.

### D6 — Idempotency gồm cả trường hợp zero facts

Celery delivery và completion callbacks có thể at-least-once. Thêm durable state schema-explicit trên `Run`: `memory_extraction_status` (`pending|completed|skipped|failed`), `memory_extraction_completed_at` và nullable `memory_extraction_skip_reason`. Một run chỉ được tính là một logical extraction:

- Nếu run đã có memory với cùng `source_run_id`, task return trước LLM.
- Nếu extraction thành công nhưng không có qualifying fact, commit `completed` marker để redelivery không gọi LLM và tính phí lại.
- Memory batch, `memory_create` usage row và terminal extraction state commit cùng một transaction của run path.
- Crash trước commit không để partial rows làm lần retry bỏ qua công việc thật.
- Crash sau commit nhưng trước ack được guard bởi source marker/memory rows.

Task phải acquire row lock/compare-and-set trước LLM để hai workers đồng thời chỉ có một worker được gọi LLM. Memory rows, token usage và terminal status commit trong cùng transaction; event chỉ flush sau commit. `skipped` là terminal cho policy/gate/missing-creator reasons; transient failure không được ghi terminal trước khi retry budget cạn.

Không dùng content-only dedupe làm idempotency key. Semantic dedupe vẫn do repository xử lý, nhưng source run identity phải giữ được.

### D7 — Recall trả citation tới run

REST memory response và MCP `nowing_recall` phải expose provenance tối thiểu đủ để caller biết fact đến từ `run_<uuid>`:

- `source_type`;
- `source_run_id`;
- `citation = "run_<uuid>"`;
- citation/source descriptor ổn định trong `MemoryRead`, `MemorySearchHit`, REST JSON, MCP JSON và MCP markdown.

Citation là soft link: nếu run còn trong retention thì read/history flow resolve được run gốc. Nếu run đã cleanup, memory vẫn tồn tại và recall không lỗi; recipe lâu dài thuộc Story 9.6a.

### D8 — NFR-1b áp dụng tự nhiên qua canonical renderer

Memory từ research dùng cùng bảng, repository, search và renderer với memory chat. Không có prompt injection path riêng và không bypass ngân sách aggregate 8.000 chars của Story 3.14.

Đây là completion gate: implementation có thể bắt đầu trước khi 3.14 merge, nhưng Story 3.13 không được chuyển done nếu integration baseline chưa có bounded renderer và regression test chưa chứng minh research-created memory chịu cùng aggregate budget.

## Acceptance Criteria

### AC-1 — Successful platform run tạo memory

**Given** workspace mới không có memory và auto extraction được bật,
**When** một capability trong inventory 15-entry ở trên hoàn tất thành công với output chứa durable facts,
**Then** background extraction tạo tối đa configured max-items memory có `source_type=SCRAPER_RUN`, `source_run_id` đúng và workspace/creator đúng; agent-origin run phải có explicit creator attribution hoặc structured skip trước LLM,
**And** run response không chờ extraction.

### AC-2 — ChainLens research dùng cùng pipeline

**Given** `chainlens.research` hoàn tất thành công qua REST sync, REST async hoặc agent sync door,
**When** completion được persist,
**Then** cùng shared extraction pipeline được enqueue đúng một logical lần,
**And** không có ChainLens-only memory implementation.

### AC-3 — Recall có first-run value và citation

**Given** extraction của run đầu đã hoàn tất,
**When** gọi `/memories/search` hoặc MCP `nowing_recall`,
**Then** ít nhất một qualifying fact được trả thay vì empty result,
**And** `MemoryRead`, `MemorySearchHit`, REST JSON, MCP JSON và MCP markdown chỉ ra `source_type=SCRAPER_RUN`, `source_run_id` và citation `run_<uuid>` trỏ về run gốc.

### AC-4 — Gates và cost controls được giữ nguyên

**Given** global switch off, workspace opt-out, anonymous/missing-creator run, wallet reserve failure, spend-cap exhaustion hoặc rate-limit exhaustion,
**When** run hoàn tất,
**Then** extraction LLM không được gọi và không tạo memory,
**And** structured skip reason dùng cùng vocabulary/telemetry của Story 8.7/8.8.

### AC-5 — Failure isolation

**Given** enqueue, extraction LLM, embedding hoặc memory persistence lỗi,
**When** capability run đã thành công,
**Then** run vẫn successful và output vẫn đọc được,
**And** transient extraction failures retry theo policy,
**And** auth/config/validation failures không retry,
**And** lỗi ở bất kỳ fact nào rollback toàn bộ run-memory batch, completion marker và `memory_create` usage; không có partial commit hoặc duplicate charge.

### AC-6 — Idempotency

**Given** cùng run completion được delivered nhiều lần,
**When** task chạy lại hoặc hai workers bắt đầu đồng thời cho success có facts hoặc success có zero facts,
**Then** không gọi LLM lại, không tạo duplicate memory, không emit duplicate `memory.changed`, và không ghi duplicate `memory_create` usage.

### AC-7 — Retention independence và schema safety

**Given** run gốc bị cleanup sau retention,
**When** recall memory đã tạo,
**Then** memory vẫn đọc/search/render được và không raise vì dangling soft reference,
**And** migration không đổi `Memory.source_id` integer và không tạo FK cứng tới `runs.id`.

### AC-8 — Bounded source and injection

**Given** run input/output lớn hoặc chứa instruction độc hại,
**When** extract,
**Then** combined capability + serialized input + serialized output bị truncate deterministically trong `RUN_MEMORY_SOURCE_CHAR_CAP`, scraped instructions không được follow,
**And** memory tạo ra đi qua cùng bounded retrieval/rendering path và aggregate 8.000-char budget của Story 3.14.

### AC-9 — M1 instrumentation

**Given** signup/workspace creation, first run và first non-empty recall có timestamps,
**When** tính first-run funnel,
**Then** telemetry đủ để đo signup/workspace-created → first successful research run → first recalled research memory,
**And** low-cardinality counters `run_memory_enqueued_total`, `run_memory_created_total`, `run_memory_zero_fact_total`, `run_memory_skipped_total{reason}`, `run_memory_failed_total` và `run_memory_retried_total` cùng first-success/first-recall timestamps không chứa scraped payload,
**And** product target M1 là không quá 15 phút; unit test không fake wall-clock product SLO.

## Implementation Contract

| Concern | Required contract |
|---|---|
| Eligible doors | REST sync, REST async, agent sync; exact 15-capability inventory ở Goal section |
| Completion hook | `enqueue_run_memory_extraction_after_commit(run_id)` only after committed successful `record_run`/`finalize_run` |
| Background task | Reuse `memory_extraction_task.py` pattern; separate DB session; transient-only retry |
| Attribution | REST and agent pass `Run.user_id`; missing creator skips before LLM with structured reason |
| Idempotency | `Run.memory_extraction_status/completed_at/skip_reason` + row lock/CAS before LLM |
| Atomicity | Memory batch + `memory_create` usage + terminal marker in one transaction; events after commit |
| Provenance | Nullable indexed `Memory.source_run_id` UUID, no FK; keep integer `source_id` unchanged |
| Recall fields | `source_type`, `source_run_id`, `citation=run_<uuid>` in REST and MCP JSON/markdown |
| Source bound | Deterministic `RUN_MEMORY_SOURCE_CHAR_CAP` over capability + input + output |
| Completion dependency | Story 8.7 P0 caveat resolved/accepted and Story 3.14 bounded path proven on integration baseline |

## Tasks / Subtasks

- [ ] **T1 — Schema + migration cho soft run provenance**
  - [ ] Thêm `Memory.source_run_id` UUID nullable, indexed, không FK.
  - [ ] Thêm `Run.memory_extraction_status`, `memory_extraction_completed_at` và `memory_extraction_skip_reason` cho durable facts/zero-fact/skip idempotency.
  - [ ] Giữ nguyên `Memory.source_id` integer.
  - [ ] Cập nhật ORM, Pydantic response, repository create/update contract và migration downgrade.
  - [ ] Nếu schema 9.6a đã tồn tại, reuse thay vì tạo migration/field cạnh tranh.
  - [ ] Không reuse revision `181`; baseline tracked head là `180` và dirty tree đã có untracked `181_add_memories_thread_recency_index.py`. Chọn integration head rõ ràng rồi tạo revision mới trong worktree riêng.

- [ ] **T2 — Extract common pipeline từ chat service**
  - [ ] Giữ `extract_from_turn` backward-compatible.
  - [ ] Thêm run-specific entry point dùng cùng parser, policy, gate, token accounting và repository.
  - [ ] Tạo bounded, injection-resistant prompt từ capability/input/output.
  - [ ] Không gọi LLM cho empty output hoặc disallowed gate.
  - [ ] Run path rollback toàn batch + usage + terminal marker khi bất kỳ embedding/persistence step nào lỗi; không thay đổi partial-success semantics hiện có của chat path.

- [ ] **T3 — Durable background task + idempotency state**
  - [ ] Reuse `memory_extraction_task.py` để thêm Celery task cho run UUID với session riêng và transient-only retry policy.
  - [ ] Implement durable terminal state cho facts, zero-fact và policy skip.
  - [ ] Acquire row lock/CAS trước LLM; test hai workers đồng thời chỉ tạo đúng một LLM call cho facts và zero facts.
  - [ ] Guard facts path bằng `source_run_id` và commit memories + usage + terminal state atomically.
  - [ ] Flush `memory.changed` đúng một lần sau commit.

- [ ] **T4 — Wire shared run-completion seam**
  - [ ] Implement `enqueue_run_memory_extraction_after_commit(run_id)` và gọi sau successful `record_run`/`finalize_run` return, không enqueue bên trong pre-commit transaction.
  - [ ] Cover REST sync, REST async và agent sync; không yêu cầu async agent door chưa tồn tại.
  - [ ] Agent door truyền active creator vào `record_run(user_id=...)`; missing creator có explicit terminal skip reason trước LLM.
  - [ ] Enqueue chỉ sau run commit; failed/running/cancelled không enqueue.
  - [ ] Enqueue failure chỉ log/metric, không đổi capability result.

- [ ] **T5 — Recall provenance/citation contract**
  - [ ] Expose `source_run_id` và `citation=run_<uuid>` trong `MemoryRead`, `MemorySearchHit` và REST search/read payloads.
  - [ ] Propagate qua MCP `nowing_recall` JSON lẫn markdown và client schemas.
  - [ ] Resolve citation khi run còn tồn tại; dangling soft link fail-soft sau cleanup.
  - [ ] Không hardcode score hoặc làm regression contract của Story 3.14.

- [ ] **T6 — Telemetry**
  - [ ] Implement low-cardinality counters `run_memory_enqueued_total`, `run_memory_created_total`, `run_memory_zero_fact_total`, `run_memory_skipped_total{reason}`, `run_memory_failed_total` và `run_memory_retried_total`.
  - [ ] Event/timestamps đủ đo first-run funnel mà không lưu scraped payload vào metric labels.
  - [ ] Token usage tiếp tục là `memory_create`; không debit wallet ngoài AD-8.

- [ ] **T7 — Tests**
  - [ ] Unit: deterministic combined input/output source bound, malicious instruction, parse/filter/max-items, empty output và invalid JSON.
  - [ ] Unit: every Story 8.7/8.8 gate prevents LLM call.
  - [ ] Unit: REST sync/async + agent sync success; failed/cancelled/still-running; recorder commit failure; enqueue exception; no response regression.
  - [ ] Unit: agent `Run.user_id` attribution and missing-creator skip.
  - [ ] Unit: transient LLM/network retry; auth/config/validation no-retry.
  - [ ] Unit/integration: idempotency with facts, zero facts, two-worker concurrency, pre-commit crash and post-commit redelivery.
  - [ ] Integration: force second-fact persistence failure; assert zero memories, zero usage, no terminal completion and no event.
  - [ ] Integration with real Postgres: UUID source field, index, soft dangling reference and migration downgrade.
  - [ ] Contract: enumerate all 15 registered research capabilities; execute representative platform + `chainlens.research` through REST sync/async and agent sync.
  - [ ] Contract: REST + MCP JSON/markdown recall returns `source_type`, `source_run_id` và stable run citation.
  - [ ] Regression: existing chat extraction, run recording, billing, memory search and 3.14 bounded injection suites.

- [ ] **T8 — Documentation and quality gates**
  - [ ] Document first-run behavior and feature flags; do not claim durable re-validation before 9.6a.
  - [ ] Re-verify Story 8.7 gate contract and record resolution/acceptance of its open P0 human-review caveat.
  - [ ] Do not mark done until Story 3.14 bounded renderer is on the integration baseline and research-memory 8.000-char regression passes.
  - [ ] Ruff/format/type checks for touched backend/MCP code.
  - [ ] Targeted unit + integration tests, then backend regression baseline.
  - [ ] Run mutation/test-quality/security/human-review gates required by repository policy before merge.

## Testing Requirements

### Test Matrix

| Case | Expected invariant |
|---|---|
| Platform sync success | Run commits, extraction enqueues once, response does not wait |
| Platform async success | Pending run finalizes, extraction enqueues once |
| ChainLens REST sync/async + agent sync | Same pipeline and provenance as platform verbs; no assumed async agent door |
| Failed/cancelled run | No extraction task |
| Empty output | No LLM, durable completed/no-op state |
| Gate disabled/capped/rate-limited/anonymous | No LLM and structured skip telemetry |
| Qualifying facts | Atomic memories + usage, events after commit |
| Zero qualifying facts | No memory, no repeated LLM on redelivery |
| Duplicate delivery | No duplicate memory, event or token usage |
| Two concurrent workers | Exactly one LLM call and one terminal transaction for facts and zero facts |
| Second fact persistence failure | Whole batch, usage, marker and event rollback |
| Huge/malicious input or output | Deterministic combined-source truncation, instructions treated as data |
| Auth/config failure | Terminal no-retry; capability response unchanged |
| Run deleted by retention | Memory remains searchable; citation degrades without exception |
| MCP/REST recall | `SCRAPER_RUN` + `source_run_id` + `run_<uuid>` visible in JSON and markdown |

## Project Structure Notes

### Current State of UPDATE Files

- `nowing_backend/app/db.py`: `Memory.source_id` remains integer and has no `source_run_id`; `Run.user_id` is nullable and run extraction has no durable state. Add the soft UUID provenance and explicit run-extraction state without FK or source-id type changes.
- `nowing_backend/alembic/versions/`: tracked head reaches revision `180`; dirty tree contains untracked revision `181_add_memories_thread_recency_index.py`. Create from a deliberately selected integration head in this story's worktree; do not reuse `181`; preserve downgrade.
- `nowing_backend/app/services/memory/extraction.py`: only `extract_from_turn` exists and owns canonical prompt/parser/gate/accounting/event flow; current per-fact error handling can commit a partial chat batch. Extract shared policy while preserving chat behavior and make run extraction all-or-nothing.
- `nowing_backend/app/services/memory/repository.py`: `create_memory` owns embedding/dedupe/versioning/events but has no run UUID provenance input. Extend its contract rather than directly inserting memory rows.
- `nowing_backend/app/services/memory/extract_budget.py`: `check_extract_allowed` is the authoritative kill-switch/opt-in/wallet/spend/rate/anonymous gate. Reuse it unchanged and ensure missing creator cannot bypass it.
- `nowing_backend/app/capabilities/core/runs.py`: `record_run` and `finalize_run` own their commits; there is no extraction enqueue. Preserve run success/failure/retention behavior and invoke the shared enqueue seam only after successful helper return.
- `nowing_backend/app/capabilities/core/access/rest.py`: sync and async paths already pass `user_id` and use the shared run lifecycle. Add post-commit enqueue without delaying or changing responses.
- `nowing_backend/app/capabilities/core/access/agent.py`: baseline is sync-only and records success/error without `user_id`. Thread active creator into run recording, add post-commit enqueue for success only and do not invent an async agent dispatcher.
- `nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py` and `nowing_backend/app/celery_app.py`: chat extraction task, transient retry taxonomy and Celery include already exist. Reuse this module/pattern for run UUID work.
- `nowing_backend/app/schemas/memory.py`: response/search schemas expose `source_type/source_id` but no run UUID or citation. Add both without breaking existing fields.
- `nowing_backend/app/routes/memories_routes.py`: REST mapping currently propagates only existing provenance. Carry `source_run_id` and stable citation through read/search responses.
- `nowing_mcp/mcp_server/features/memory/`: JSON relays memory items but markdown drops provenance. Preserve existing recall ranking/content while adding run provenance to both formats.
- Matching unit/integration/contract tests: extend existing chat extraction, spend-gate, REST, agent, run-truncation and MCP suites before adding new scaffolds.

Do not edit or absorb the dirty working tree currently implementing Story 3.14/6.5. Implement this story in its own git worktree branched from the declared baseline or a deliberately selected integration commit.

## References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.13, FR-40 and M1
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-11.1 and AD-18
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-25.md` — readiness P-4/C-2
- `_bmad-output/implementation-artifacts/8-7-auto-extract-spend-budget-cap.md` — canonical gate/cost policy
- `_bmad-output/implementation-artifacts/3-14-memory-injection-bounded-retrieval.md` — 8.000-char injection contract
- `nowing_backend/app/services/memory/extraction.py` — existing chat extraction
- `nowing_backend/app/capabilities/core/runs.py` — shared run lifecycle and retention
- `nowing_backend/app/capabilities/core/access/rest.py` and `agent.py` — sync/async doors
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — ChainLens research pipeline

## Dev Agent Record

### Agent Model Used

Not started

### Debug Log References

Not started

### Completion Notes List

Not started

### File List

Not started

## Review Findings (code review 2026-08-08)

Scope: commits `d8dd83ebb`..`4abc80437` — 16 files, 2225 lines (memory provenance pipeline).

**decision-needed:** 0

**patch (medium) — fixed 2026-08-08:**
- [x] [Review][Patch] Missing workspace causes stuck `pending` status — `run_extraction.py:274-281` returned `[]` without terminal marker when workspace is None. CAS already set `pending`, so redelivery fails CAS and run is stuck forever. Fix: write `STATUS_SKIPPED` with reason `"missing_workspace"` before returning. [edge]

**defer:** 2 (text() anti-pattern in search.py — pre-existing, not introduced by this diff; REST/MCP endpoint integration tests — Pydantic model tests verify the contract)

**dismissed:** 15 (CAS not implemented — FALSE POSITIVE, CAS IS in task file; terminal marker not atomic — FALSE POSITIVE, marker is in same transaction; idempotency race — FALSE POSITIVE, CAS handles concurrency; context window terminal — intentional design, deterministic prompt; _mark_terminal atomicity — only one worker reaches it after CAS; source truncation non-deterministic — not reachable, run.input is always JSON; token usage failure — handled by task's `except Exception` handler; unserializable input — not reachable; AC-1 PARTIAL — FALSE, `test_run_extraction_creates_memory_with_run_provenance` covers it; AC-2 FAIL — FALSE, pipeline is capability-agnostic, no ChainLens-only code exists; AC-4 PARTIAL — FALSE, `test_run_memory_gates.py` covers all gate conditions; AC-5 PARTIAL — FALSE, `test_run_extraction_is_all_or_nothing_on_second_fact_failure` + `test_persistence_failure_leaves_no_partial_batch` cover it; AC-6 FAIL — FALSE, `test_two_concurrent_workers_make_exactly_one_llm_call` + `test_redelivery_after_completion_makes_no_llm_call` cover it; AC-9 PARTIAL — FALSE, counters tested at `test_run_memory_telemetry.py:105-106`)

**Note:** Acceptance Auditor only looked at the diff (unit tests) and missed the existing integration test suite (`tests/integration/memory/test_run_memory_*.py` — 34 tests across 6 files). The integration suite covers AC-1, AC-4, AC-5, AC-6 comprehensively.

## Change Log

- 2026-07-27: Validation hardening added explicit agent attribution, executable after-commit seam, durable concurrent idempotency state, atomic run-batch semantics, complete recall citation contract, combined source bounds, concrete telemetry/tests, dependency gates and per-file current-state notes.
- 2026-07-27: Story created from FR-40/readiness P-4/C-2 with shared run-completion design, bounded extraction, soft UUID provenance, zero-fact idempotency and ChainLens parity pinned.
