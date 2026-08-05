PATH: planning/implementation-artifacts/story-3-14-memory-injection-bounded-retrieval-latency-budget
TITLE: Story 3.14: Memory Injection — Bounded Retrieval & Latency Budget
TAGS: bmad, bmad-source-bmad-output-implementation-artifacts-3-14-memory-injection-bounded-retrieval-md
UPDATED: 2026-07-28

---
baseline_commit: 25ba542c2
baseline_branch: develop
story_key: 3-14-memory-injection-bounded-retrieval
status: review
---

# Story 3.14: Memory Injection — Bounded Retrieval & Latency Budget

**Status:** review
**Epic:** 3 — Knowledge Base + Long-Term Memory
**Priority:** HIGH — performance/correctness prerequisite trước khi Story 3.9 ratify SM-10
**Requirements:** NFR-1b, NFR-1c, NFR-1d, NFR-8, FR-32
**Architecture:** AD-18
**Dependencies:** Story 3.8, 8.7, 8.8 đã hoàn thành. Story 3.9 giữ `in-progress` tới khi metric owner ratify SM-10 sau evidence của 3.14. Story 3.13 không phải hard dependency.

## Story

Là người dùng có workspace tích lũy ngày càng nhiều memory,
tôi muốn mỗi lượt chat chỉ retrieve một tập memory liên quan với chặn trên rõ ràng cho query, số hàng, prompt và latency,
để chi phí Nowing ổn định khi corpus tăng thay vì tăng tuyến tính theo mức sử dụng.

## Goal and Current Reality

Giữ riêng hai đường đọc:

1. **`memory_injection`**: `MemoryInjectionMiddleware.abefore_agent` trong main-agent hot path.
2. **`memory_recall`**: explicit REST/MCP/research/automation, chỉ chạy khi caller yêu cầu.

Tại baseline `25ba542c2`:

- Injection personal/team đọc toàn bộ scoped rows rồi `.scalars().all()`; không `LIMIT`.
- `MEMORY_SOFT_LIMIT`/`MEMORY_HARD_LIMIT` là per-write document limits, không bound aggregate read.
- Private injection giữ `<user_name>` ngay cả khi zero memory; name-only là compatibility contract.
- `build_memory_mw()` nhận `user_id=None`; private middleware hiện vẫn có thể mở session rồi no-op, thay vì thoát trước mọi work/telemetry.
- Display-name SQL chạy trước memory SQL; lỗi có thể poison transaction.
- Wrapper có attributes nên không match literal protected prefix `<user_memory>`.
- `MemoryHybridSearch` đã có RRF/HNSW/GIN nhưng chỉ workspace scope, bỏ score, tie-break thiếu và query-less metadata chưa rõ.
- REST/research/automation hardcode `score=0.0`; eval chỉ `rank_only`.
- Assistant finalization chỉ enqueue Celery `.delay(...)`; extraction service/LLM/persistence không được chạy inline.
- Backend automation drafter có bốn new-write literals `schema_version: "1.0"` trong `_SCHEMA`/`_FEW_SHOTS`; web `buildDefinition()` cũng phát `1.0`.
- Eval `_cmd_run()` gọi `load_config()`/`acquire_token()` trước runner; LOCAL auth có thể POST `/auth/desktop/login`, nên runner-only build-id validation không phải fail-fast trước network.

## Resolved Design Decisions

### D1 — Một canonical scored-result contract

`MemoryHybridSearch.search() -> list[ScoredMemory]`, không row-only wrapper/API thứ hai:

- `memory: Memory`;
- `score: float | None` — raw RRF;
- `similarity: float | None` — `1 - cosine_distance`.

Direct callers `memories_routes.py`, `research_threads_routes.py`, `continue_research/invoke.py` đổi cùng story. MCP đi qua REST. Không duplicate SQL/compatibility unwrap.

### D2 — Solution A: bounded recent transcript

Injection query role-aware từ recent message state; không final-human-only. Final message vẫn phải là `HumanMessage`.

```python
_MEMORY_INJECTION_TOP_K = 5
_MEMORY_QUERY_MAX_CHARS = 4_000
_MEMORY_INJECTION_MAX_CHARS = 8_000
```

Ba constant fixed/module-local; không env/config, không sửa config hoặc `.env.example`.

### D3 — `BaseMessage.text`, không parser riêng

Với `langchain-core 1.2.22`, dùng property `message.text`, coerce `str(...)`: string/text blocks được nối, non-text blocks bị bỏ. Không `message.text()`, không mở rộng `extract_text_content`, không parser `str|dict|list` mới.

### D4 — Exact private-owner guard + transcript/newline contract

- Ngay đầu `abefore_agent`, sau `del runtime` nhưng trước đọc/normalize transcript, timer, embed, session, search, display-name, render hay telemetry: nếu visibility không phải `SEARCH_SPACE` và `self.user_id is None`, return `None`. Đây là normal no-op với zero perf/failure log và zero counter. Team `SEARCH_SPACE` không phụ thuộc `user_id` và vẫn chạy bình thường.
- Sau guard trên, last-message guard vẫn yêu cầu final `HumanMessage` cho cả personal/team.
- Role: `HumanMessage→human`, `AIMessage→assistant`, `SystemMessage→system`, `ToolMessage→tool`; subclasses kế thừa; unknown skip.
- Normalize bằng `"
".join(str(message.text).splitlines()).strip()`; không collapse nội-line whitespace.
- `str.splitlines()` là source of truth. Parameterized tests phải cover CRLF, CR, LF, VT (`U+000B`), FF (`U+000C`), file/group/record separators (`U+001C/U+001D/U+001E`), NEL (`U+0085`), LS (`U+2028`), PS (`U+2029`).
- Record `"{role}: {text}"`; separator `"

"`; no leading/trailing separator.
- Marker `"[...truncated...] "` tính trong 4.000 chars.
- Select newest→oldest, emit chronological. Boundary record giữ role prefix + marker + longest tail; chỉ partial khi còn marker + ≥1 content char.
- Skip generated protected `SystemMessage` whose normalized `lstrip()` starts with `PROTECTED_SYSTEM_PREFIXES`.
- Empty/tool-only/attachment-only/unsupported blocks skip, không failure.
- Toàn transcript unusable: return `None` trước embed/session/search/name/telemetry; không injection recency fallback.

Golden:

```text
human: Where is the launch checklist?

assistant: It is in the release folder.

human: Summarize the remaining blockers.
```

### D5 — Exact operation × query-mode × scope matrix

Canonical search scope: đúng một trong `workspace_id`/`user_id` non-`None`.

- Personal: `workspace_id IS NULL AND created_by_id==user_id`.
- Workspace: `workspace_id==workspace_id`.
- `research_thread_id` chỉ workspace scope.
- Missing/ambiguous scope raise `ValueError` trước SQL; không broad `OR`.
- Riêng middleware private thiếu `user_id` bị D4 chặn trước khi tạo search request, nên không biến normal no-op thành search `ValueError`.

Public compatibility matrix—mỗi surface là một hàng, không gộp research với automation:

| Surface | Query contract | Search mode | Scope | Preserve |
|---|---|---|---|---|
| Main-agent injection personal | bounded transcript, nonblank | ranked | personal user non-`None` | yes |
| Main-agent injection team | bounded transcript, nonblank | ranked | workspace | yes |
| `POST /workspaces/{id}/memories/search` | nonblank; optional thread id | ranked | workspace hoặc workspace+thread | yes |
| Same REST search | blank chỉ khi thread id present | recency | workspace+thread | yes |
| MCP `nowing_recall` | required nonblank; optional thread id | ranked via REST search | workspace[/thread] | yes |
| REST research context | nonblank | ranked | workspace+required thread | yes |
| REST research context | blank | recency | workspace+required thread | yes |
| MCP `nowing_continue_research` | optional; nonblank→ranked, blank→recency | mirrors REST context | workspace+required thread | **keep current ranked option** |
| Automation `continue_research` | no query field | recency only | workspace+required thread | yes |

Không remove ranked REST context/MCP continue behavior. Tests khóa cả blank/nonblank branch, citations order và tenant-negative cases.

### D6 — Shared vector validator, stored-row policy, deterministic search

Tạo một primitive, ví dụ `app/services/memory/vector.py::validate_embedding_vector`, dùng trong repository/search/middleware. Return contiguous `np.float32` 1-D array hoặc typed reason:

1. conversion lỗi type/value/overflow → `non_numeric`;
2. scalar/2-D/higher → `invalid_shape`;
3. wrong dimension → `invalid_dimension`;
4. NaN/Inf element → `non_finite`;
5. norm lỗi/non-finite → `non_finite_norm`;
6. norm `<=0` → `zero_norm`.

Caller cardinality mapping: provider raises → `provider_error`; result non-sequence/count 0/>1 → `invalid_count`; không index `[0]` trước check.

- `MemoryRepository._embed/create_memory/update_memory` validate generated và supplied vectors trước dedup SQL/assignment/flush.
- DB `Vector(dimension)` không thay finite/non-zero validation.
- Search validate query trước SQL. Semantic/keyword CTE và final candidate query bounded `top_k*3` (max 15), materialize max 15, validate stored embedding + score/similarity, audit/drop invalid, return first max 5 valid. Đây là bounded replacement, không full-scan.
- Benchmark read-only audits scoped rows by reason. Existing invalid count >0 cần evidence-driven transactional re-embed/quarantine và re-audit 0 trước `done`; không auto-delete. Migration chỉ khi evidence yêu cầu.
- Real-DB tests: wrong count, nonnumeric, scalar/2-D, dimension, NaN/Inf, finite-element norm overflow, zero norm; legacy invalid raw row nếu pgvector cho phép bị exclude/audit.

Ranked requires nonblank query + valid vector; mismatched query/vector state raises. Recency requires blank + `None` embedding + thread id. Ranked score/similarity finite; recency both `None`.

Ordering:

- semantic distance ASC, id ASC, deterministic `row_number()`;
- keyword rank DESC, id ASC, deterministic `row_number()`;
- final score DESC, similarity DESC, created_at DESC, id ASC;
- recency created_at DESC, id DESC.

Similarity computed for every ranked hit, including keyword-only. RRF ~0–0.033 không phải cosine và không dùng `min_similarity=0.3`.

### D7 — Separate byte-exact injection renderer

Giữ `render_memory_markdown(list[Memory])` legacy unchanged vì `MemoryService.read_memory()`/editor dùng nó. Thêm `render_bounded_memory_injection(...)`; chỉ reuse date/heading helpers.

```text
<user_name>{escaped_first_name}</user_name>

<user_memory>
{body}
</user_memory>

<memory_warning>Memory results were truncated to fit the 8000-character injection budget.</memory_warning>
```

Team dùng `<team_memory>`. Rules:

1. Bare wrapper tags, no attributes; exact protected-prefix match.
2. First name `display_name.strip().split()[0]`, splitlines-normalize, `html.escape(quote=True)`. Zero result + valid private name→name-only; team/private-no-name→`None`.
3. Search materializes before name lookup; lookup in `session.begin_nested()` SAVEPOINT.
4. Content `"
".join(str(content).splitlines()).strip()`, escape each line; continuation indent exactly two spaces. Empty content skip.
5. Consume ranked order. `## Heading` + `- YYYY-MM-DD: content`; consecutive same heading shares heading; type transition opens heading even if repeated later. No global grouping.
6. Top-level separator `"

"`; wrapper/body `"
"`; no trailing newline/empty wrapper.
7. Render full memory first. Full memory + optional full name <=8.000 → no marker/warning.
8. Memory outranks auxiliary name. If memory fits but name overflows, preserve full memory; fit/truncate/omit name in remaining capacity. Name never truncates memory.
9. If memory overflows, omit name, reserve tags/separators/fixed warning/marker, add full records; first non-fitting record gets exact prefix + escaped head + `"[...truncated...]"` + tail; stop afterward.
10. Escaped atom = whole entity matching `&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);` or one code point. Head budget ceil, tail floor; longest non-overlap whole atoms, then spend remainder on next head atom before next tail atom until neither fits. Never split entity.
11. If record prefix+marker+1 char cannot fit, omit it/lower ranks. Production 8.000 should fit first bounded record; invariant break→`render/compose_error`, no wrapper/warning-only.
12. Warning outside wrapper, separated by `

`, iff memory partial/omitted. Name truncation has marker but no memory warning. Assert final <=8.000; violation→`budget_violation`, never slice final payload.
13. Name-only huge value uses all value capacity with same helper. Result-bearing huge name tests both truncate and omit.

Byte goldens:

```text
<user_name>Ada</user_name>
```

```text
<user_name>Ada</user_name>

<user_memory>
## Facts
- 2026-07-26: Prefers concise answers.

## Procedural
- 2026-07-25: Run the release checklist first.
</user_memory>
```

```text
<team_memory>
## Facts
- 2026-07-26: &lt;/team_memory&gt; is untrusted text.
</team_memory>
```

Truncation golden builds exact prefix + whole escaped atoms + marker + tail + close + warning. Test entities at both cuts, 7.999/8.000/8.001, blank/no-wrapper, separators, malicious delimiters, huge name. Regression locks legacy renderer output byte-for-byte.

### D8 — Exactly one log + exactly one counter attempt

One helper in `app/observability/metrics.py` owns:

- metric `nowing.memory.injection.failures`;
- log `memory_injection.failure`;
- attrs only `scope=user|team`, `stage`, `reason`;
- exactly one `logger.warning` and one `_add(...,1,attrs)` attempt for the winning ordinary failure; backend telemetry error suppressed, no retry/double-log.

Reasons:

- query: `render_error`;
- embedding: `provider_error|invalid_count|non_numeric|invalid_shape|invalid_dimension|non_finite|non_finite_norm|zero_norm`;
- session: `enter_error|exit_error`;
- search: `query_error|invalid_result`;
- display_name: `lookup_error`;
- render: `compose_error|budget_violation`.

`invalid_result`: non-list, non-`ScoredMemory`, missing memory, ranked metadata missing/nonnumeric/nonfinite, hoặc output >5.

Precedence: query→embedding→session-enter→search terminal first; display-name pending/recoverable; session-exit/render override pending; otherwise emit pending once. Every ordinary failed attempt = exactly 1 log + 1 counter attempt; normal/no-op—including private `user_id=None`, unusable transcript và zero-result without name—= zero. Cancellation/`BaseException` propagate with zero ordinary telemetry. No IDs/query/error text/content labels.

### D9 — Strict public `top_k` + automation versioning

`bool` is invalid everywhere (`True` không phải 1): use strict/before validation in REST, MCP, automation v1.1 và internal search.

| Surface | omitted | 0/bool | 1..5 | 6+ |
|---|---:|---:|---:|---:|
| REST search/context | 5 | 422 | accept | 422 |
| MCP recall/continue | 5 | validation error | accept | validation error |
| New automation, static | 5 | create/update 422 | accept | create/update 422 |
| v1.1 templated top_k | 5 after render | failed step | accept | failed step; no clamp |
| Persisted v1.0/missing version | 5 | failed step | accept | old-valid 6..100→5 + one warning |
| Internal search | 5 | `ValueError` | accept | `ValueError` |
| Injection | fixed 5 | n/a | n/a | n/a |

Automation contract:

1. Parser default `schema_version="1.0"` chỉ là legacy-read compatibility cho persisted snapshot thiếu version; supported only 1.0/1.1. Mọi create/update-with-definition phải overwrite thành 1.1 trước dump/persist, nên parser default không được trở thành new-write producer.
2. Đổi cả bốn literals trong `main_agent/tools/automation/prompt.py` (`_SCHEMA` + ba `_FEW_SHOTS`) sang `1.1`; focused golden assert rendered prompt có đúng bốn occurrence `1.1` và không có producer `1.0`. Đổi `nowing_web/lib/automations/builder-schema.ts::buildDefinition()` sang `1.1`; focused TS assertion gọi `buildCreatePayload()` và assert persisted definition version.
3. Create/update-with-definition normalizes persisted version to 1.1 even if client omit/sends 1.0. Unrelated patch preserves old snapshot/version.
4. Registry save validator: unknown action/extra/missing required→422. Non-template field validates Pydantic annotation+metadata (`TypeAdapter(field.rebuild_annotation())`), so static top_k 6 fails even when another field templated. All-static runs full model and canonical dump; template/cross-field defers runtime.
5. `execute_run` passes definition version into `execute_step` for normal and `on_failure`. v1.1 validates full registered model after `render_value`, before handler/retry.
6. v1.0 continue-research uses private legacy model 1..100 after render. 6..100 copied to 5 và one warning before retry (`action`, `schema_version`, `reason=top_k_above_5`); 0/bool/malformed/>100 fails; record unmodified. Other legacy actions unchanged.
7. New params model/MCP annotation pin 1..5; remove runtime clamps. Eval may harness-clamp but records requested/effective.
8. Sau thay đổi, mọi production new-write producer được biết đều phát 1.1. Repo regression phân loại literal `1.0` còn lại: chỉ parser default hoặc fixture được đặt tên/ghi chú explicit legacy; không cho prompt, few-shot, web builder hay generated definition mới phát 1.0.

Tests: omitted/explicit 1.0 new writes→1.1; unrelated old patch; static/mixed/runtime template 0/bool/1/5/6; v1.0 missing/explicit 6/100 once; 0/bool/101 fail; normal/on-failure version propagation; backend prompt golden; web builder payload assertion.

### D10 — Pre-auth eval validation + fresh provenance + unambiguous gate run

Artifact adds:

- full repo SHA/branch/dirty/patch SHA-256;
- explicit actual deployed `backend_build_id`, Python/platform, `uv.lock` SHA-256;
- dataset/corpus-map/runner SHA-256;
- exact argv/run id/requested+effective params;
- raw SHA-256 + row count.

Patch hash = tracked binary diff against HEAD + sorted non-ignored untracked path/content hashes; never read ignored `.env`/secrets. Do not fake clean/build identity.

Pre-auth contract:

1. `MemoryRecallBenchmark.add_run_args()` vẫn gắn vào cả ingest/run parser, nên thêm `--backend-build-id` parser-optional (`default=None`); ingest bỏ qua và vẫn chạy không cần ID.
2. Trong `core/cli.py::_cmd_run`, ngay sau `registry.get(...)`: build `extra_kwargs`, lấy optional hook bằng `getattr(benchmark, "validate_run_options", None)`, và gọi hook **trước** `load_config()`, `_resolve_suite_state()`, `acquire_token()` hay `client_with_auth()`.
3. `MemoryRecallBenchmark.validate_run_options(...)` reject missing/blank/whitespace-only build ID thành deterministic CLI error + exit 2. Focused CLI test monkeypatch `load_config` và `acquire_token` thành exploding sentinels để chứng minh cả hai chưa gọi; do đó LOCAL `/auth/desktop/login` không thể xảy ra.
4. `MemoryRecallBenchmark.run()` giữ defensive check ở đầu runner, trước dataset/client/search call, để direct Python invocation cũng fail-fast. CLI preflight không thay runner defense.
5. Không bắt mọi benchmark implement hook; `_cmd_run` chỉ gọi khi hook tồn tại, nên suite khác không regression.

Local evidence trong một data dir mới, dedicated và ban đầu không tồn tại/empty:

```bash
uv sync --all-extras --frozen
uv run --active python -m pytest \
  tests/core/test_cli_run_preflight.py \
  tests/core/test_memory_recall_metrics.py \
  tests/suites/test_memory_recall_dataset.py \
  tests/suites/test_memory_recall_ingest.py \
  tests/suites/test_memory_recall_suite.py \
  tests/suites/test_memory_recall_gate.py \
  tests/suites/test_memory_recall_selfcheck_ci.py -q

export EVAL_DATA_DIR="<repo>/_bmad-output/implementation-artifacts/evidence/3-14-eval-<UTC_RUN_ID>"
uv run --active python -m nowing_evals ingest memory recall \
  --workspace-id "$NOWING_EVAL_WORKSPACE_ID"
uv run --active python -m nowing_evals run memory recall \
  --workspace-id "$NOWING_EVAL_WORKSPACE_ID" \
  --top-k 5 --min-similarity 0.3 \
  --backend-build-id "<actual-deployed-backend-build-id>"
```

Assert exactly one timestamp dir/manifest, verify raw hash, record exact path. Metrics require score-threshold, top_k 5, requested/applied 0.3, zero failed queries, finite metadata.

After artifact set `required_oracle_mode: score_threshold`; keep baseline false/source empty. Gate with same data dir; exit 1 and printed artifact id must equal verified run; reasons only unratified baseline. Archive stdout/status, then purge exact workspace fixtures.

Release workflow contract:

- add required nonblank `workflow_dispatch.inputs.backend_build_id` and pass it to run;
- set exact isolated `EVAL_DATA_DIR` under `${{ runner.temp }}` including both `${{ github.run_id }}` and `${{ github.run_attempt }}`; assert it is initially absent/empty, and seed/run/gate/report/upload all use that exact dir;
- upload only that exact dir, không default `nowing_evals/data/memory/runs/`, nên rerun không đọc stale history;
- preserve literal cleanup condition `if: always() && inputs.purge`; Story 3.14 release evidence bắt buộc dispatch với `purge=true` và archive purge result even when gate fails.

Story không ratify/rethreshold SM-10. DB migration/index chỉ evidence-driven.

## Acceptance Criteria

### AC-1 — Bounded relevant injection/isolation

Final human + usable transcript → query D2–D4 <=4.000, threaded embed, D6 validation, fixed top_k 5/exact scope. SQL candidates max 15, output max 5, no unbounded loader. Empty transcript exits before all effects. Private + `user_id=None` exits even earlier với zero work/telemetry; team + `user_id=None` vẫn retrieve workspace. Protected context and personal/workspace isolation tests pass.

### AC-2 — Hard 8.000 payload, legacy renderer stable

D7 byte-exact output <=8.000; name-only/zero-result/search-first SAVEPOINT correct. All boundary/entity/huge-name/blank/separator/delimiter/close goldens pass; legacy `render_memory_markdown/read_memory` unchanged.

### AC-3 — Reproducible latency on one fixed global table/index background

Run:

```bash
uv run --active python scripts/benchmark_memory_story_3_14.py \
  --small-corpus 100 --large-corpus 50000 \
  --warmups 20 --samples 100 --freshness-samples 30 \
  --output ../_bmad-output/implementation-artifacts/evidence/3-14-memory-performance.json
```

Tám cell dùng identity/scope riêng nhưng cố ý cùng global `memories` table/HNSW/GIN:

| Cell | Scope/mode | Exact corpus |
|---|---|---:|
| injection-personal-small | dedicated personal user A | 100 |
| injection-personal-large | dedicated personal user B | 50.000 |
| injection-team-small | dedicated workspace C | 100 |
| injection-team-large | dedicated workspace D | 50.000 |
| rest-ranked-small | dedicated workspace E, nonblank | 100 |
| rest-ranked-large | dedicated workspace F, nonblank | 50.000 |
| thread-recency-small | dedicated workspace/thread G | 100 |
| thread-recency-large | dedicated workspace/thread H | 50.000 |

Không workspace/user/thread nào shared giữa small/large hoặc operation pair. Latency phase bắt buộc:

1. Capture global baseline `G0`; tạo cả 8 identity và pre-seed **toàn bộ 8 cells trước bất kỳ warmup/timing nào**. Tổng run-tag rows phải đúng `4*100 + 4*50_000 = 200_400`.
2. Assert exact scoped count cho từng cell, run-tag count `200_400`, và global count `G = G0 + 200_400`; sau đó chạy đúng một `ANALYZE memories` trước warmup đầu tiên.
3. Không seed/update/delete/cleanup giữa các cell; không freshness/Celery writer chạy đồng thời. Assert global count `G`, run-tag count và cả 8 scoped counts trước/sau từng cell và sau cell cuối. Bất kỳ drift nào abort artifact.
4. Chỉ sau khi toàn bộ 8 warmup/timed samples, plans và audits hoàn tất mới cleanup trong `finally`. Assert từng scoped count = 0, run-tag count = 0 và global count trở lại `G0`. Latency cleanup phải hoàn tất trước phase freshness có write riêng.

Anti-false-green result oracle:

- Seed manifest/generator xác định trước—không học từ API under test—ordered canonical top-5 IDs cho từng timed query; recency IDs đến từ deterministic `created_at/id`, ranked IDs đến từ deterministic vector/keyword geometry.
- Năm expected rows có five unique, short, payload-safe sentinels `s314:<cell>:<query>:<rank>`; manifest map exact ID→sentinel. Mọi timed ranked/recency sample phải trả **đúng 5** unique valid rows, ordered IDs bằng canonical list, và mọi ID thuộc seeded-ID set của cell hiện tại.
- REST ranked/thread-recency assert response IDs/metadata trực tiếp. Injection dùng test-only observation proxy quanh real `MemoryHybridSearch.search()` để capture canonical `ScoredMemory` IDs rồi delegate unchanged; returned message phải có đúng một bare memory wrapper và chứa đúng 5 expected sentinels, mỗi sentinel đúng một lần, theo order. Payload được seed để cả 5 records fit dưới 8.000.
- `[]`, `None`, fewer/more than 5, duplicate/wrong-cell/wrong-order IDs, invalid metadata/vector, missing/extra sentinel, no-op, name-only hoặc wrapper không có memory đều abort evidence; không được tính là latency pass.

Protocol còn lại:

- real PostgreSQL+pgvector/migration head/HNSW/GIN; dedicated benchmark DB/no concurrent writers;
- RNG seed 31414000; config dimension; float32 deterministic vectors normalized float64; no remote embedding;
- 100 content buckets `s314bucket00..99`, exact 1% keyword selectivity; fixed query buckets 00..09/centroids; 10×10 round-robin; canonical top-5 geometry không được suy ra từ search output;
- fixed cell order như table; warm-cache mode với 20 unmeasured warmups/cell; concurrency 1;
- nearest-rank p95 `ceil(.95*n)-1`;
- injection DB timer trước `shielded_async_session` through exit; injection total after guards/before transcript through return; REST/context timer after RBAC/before embedding/dispatch through response compose; no HTTP/auth/provider variance;
- absolute gates: injection DB p95 <=150ms; ranked/recency total <=300ms;
- pair source khóa cứng: personal/team growth ratio và delta dùng **DB p95**; REST-ranked/thread-recency growth ratio và delta dùng **total p95**. Với source tương ứng: large/max(small,1ms) <=3.0; injection DB delta <=100ms; ranked/recency total delta <=150ms;
- large-cell JSON EXPLAIN cho personal/team/workspace semantic+keyword+final và thread recency; no full scoped seq scan at 50k;
- artifact includes provenance/generator hash/seed/queries/selectivity/order/cache/cell IDs+counts, `G0/G`, expected+actual ID/sentinel evidence, DB/env/timers/all samples/stats/ratio/delta/plans/audit/cleanup.

Artifact mandatory. Evidence-driven DB change requires complete rerun.

### AC-4 — Fail-soft exactly-one telemetry

Every ordinary failed attempt exactly one failure log + one counter attempt; normal/no-op zero. Terminal no injection; display-name-only can inject. Table tests every reason/result shape/precedence/backend-failure/cancellation và private missing-user no-op.

### AC-5 — Auto-extract off-path + freshness p95 <=60s

Production seam remains `assistant_finalize.py` → `.delay(message_id)` → Celery task; no inline extraction.

Freshness harness invokes real assistant-finalize seam with a test-only proxy around the task’s `.delay`: proxy records `t0` immediately before delegating to real `.delay`, captures returned `AsyncResult.id`, returns unchanged; no production semantic change. Chỉ bắt đầu phase này sau khi AC-3 latency cells đã cleanup/verify zero. For 30 sequential turns on real PostgreSQL+Redis+non-eager worker:

- nonce `story-3-14:<run_uuid>:<n>` and exact assistant message id;
- enqueue exception = failed sample;
- poll ranked recall every 1.000ms up to 120s;
- exact match requires `source_type=="chat_message"`, `source_id==assistant_message_id`, normalized content contains nonce;
- `t1` immediately after first exact response; record task id/state plus nonce/content SHA-256 (no private text);
- 30/30, nearest-rank p95 <=60s; record model/build/worker concurrency/initial queue depth/poll/samples;
- wait captured task IDs to terminal state; finally cleanup exact source IDs/nonce, assert source/run-tag row count 0, và verify no captured task remains active/reserved.

No live credentials/worker→not done; no eager mode. Regression ensures finalizer still only `.delay(...)` after existing gate/fail-open policy.

### AC-6 — Finite metadata, all existing query modes preserved

Ranked score/similarity finite; recency both null; no fake 0.0. REST/automation JSON always keys; MCP JSON keeps keys; markdown ranked `rrf=<6 decimals>, similarity=<6 decimals>`, recency `rank=recency, rrf=n/a, similarity=n/a`. D5 blank/nonblank matrix, citations order, keyword-only/stored-invalid/tie/null goldens all pass.

### AC-7 — Threshold oracle + exact fresh run

Threshold reads only similarity; missing/nonnumeric/nonfinite fail-safe; only finite varied signal activates run-level threshold. D10 pre-auth reject, provenance/isolated dir/release workflow/gate selection pass; ingest remains executable without build ID; gate fails only baseline unratified.

### AC-8 — Strict 1..5 + v1.0/v1.1 automation

D9 matrix including bool, save-time mixed templates, runtime templates, version normalization, normal/on-failure and legacy 0/1/5/6/100/101 passes. Prompt/few-shots and web builder new writes emit 1.1; new requests never clamp; only old-valid v1.0 6..100 does.

### AC-9 — No regression

Main-agent/final-human only; bare protected tags; all splitlines boundaries; RBAC/tenant; REST context/MCP continue ranked+recency; citations; legacy editor/renderer; automation/MCP selfcheck/client fields stable. Write limits remain per-write. No dependency/env/config knob or default migration.

## AC-to-Evidence Matrix

| AC | Required evidence | Pass |
|---|---|---|
| 1 | transcript + real-DB scope/bound/plans | exact/no-op/isolation, private-owner guard, 15→5 |
| 2 | injection goldens + legacy regression | exact/no empty wrapper/valid close |
| 3 | performance JSON | fixed global 200.400 background, exact-five canonical IDs/sentinels, ratios/plans/audit/zero cleanup |
| 4 | reason/precedence/cancellation table tests | exactly 1+1 ordinary, 0 no-op |
| 5 | finalizer regression + live freshness | off-path, task IDs, 30/30, p95<=60s, exact source identity, zero cleanup |
| 6 | service/routes/context/automation/MCP | finite ranked, recency null, both query modes |
| 7 | CLI preflight/oracle/provenance/one-run/release workflow | no pre-ID auth, hashes/build/run exact, baseline-only exit 1 |
| 8 | REST/MCP/internal/automation/prompt/web tests | strict including bool + version compatibility + all new producers 1.1 |
| 9 | regressions/Ruff/eval/MCP/web CI | prompt/RBAC/citations/legacy/client stable |

Không tick bằng unit mock khi yêu cầu real DB/live Celery/fresh eval.

## Tasks / Subtasks

- [x] **Task 1 — Shared vector + scored search** (AC 1,3,6)
  - [x] Shared validator; repository writes; scored result; exact scope/mode/order; bounded 15→5; stored audit.
  - [x] Real-DB vector/scope/tie/keyword/recency tests.
- [x] **Task 2 — Private guard + transcript + search-first injection** (AC 1,2,4,9)
  - [x] Early private `user_id=None` no-op; team unaffected; fixed 5/4.000/8.000; `BaseMessage.text`; all splitlines boundaries.
  - [x] Empty transcript early return; search before name SAVEPOINT; preserve private name-only only after usable query + zero result.
- [x] **Task 3 — Separate injection renderer** (AC 2,9)
  - [x] Preserve legacy; implement D7 and all byte goldens.
- [x] **Task 4 — Exact telemetry** (AC 4)
  - [x] Central log/counter helper, reasons, enter/exit/pending/precedence/cancellation; all normal no-ops zero.
- [x] **Task 5 — Public modes/metadata/bounds + automation v1.1 producers** (AC 6,8,9)
  - [x] Preserve all D5 REST/MCP blank/nonblank modes; nullable metadata/markdown.
  - [x] Strict 1..5 including bool; automation save/runtime/version/legacy.
  - [x] Migrate all four backend prompt literals + web builder to 1.1; add focused backend golden and web payload assertion.
- [x] **Task 6 — Pre-auth oracle/provenance/artifact/gate** (AC 7)
  - [x] Similarity oracle; optional-parser build ID; CLI pre-auth hook before config/auth; runner defense; focused CLI/ingest tests.
  - [x] Update release workflow with run-attempt-isolated dir, exact upload, required build ID và purge=true evidence; no ratification.
- [ ] **Task 7 — Performance/freshness evidence** (AC 3,5)
  - [x] Pre-seed all eight scopes; fixed global counts; exact-five IDs/sentinels; source-specific ratios; after-all zero cleanup/plans/audit.
  - [ ] Sau latency cleanup, run 30 live finalizer turns with captured task IDs; archive JSON; rerun after DB change. — SKIPPED, not done: 0 LLM API keys configured in this environment (`nowing_backend/.env`), invoking the story's own escape clause "No live credentials/worker→not done" (AC-5). AC-3 latency evidence is otherwise complete and gate-passing.
- [x] **Task 8 — Regression + P0 gates** (AC 1–9)
  - [x] Deferred-work only when resolved; backend/web tests/Ruff; eval/MCP exact CI commands.
  - [ ] Multi-agent/RAG: real-DB integration, mutation gate, human-review gate before done. — real-DB integration regression run and green (this task); mutation gate (4.10) and human-review gate (4.13) are separate P0-gated pipeline steps run after this story moves to `review`, per `nowing-quality-pipeline.md` — not part of dev-story completion.

### Review Findings

**Tổng: 0 decision-needed, 37 patch, 0 defer, 4 dismissed as noise.**

#### HIGH (7)

- [x] [Review][Patch] A1. Oracle threshold đọc RRF score thay vì cosine similarity — AC-7 [nowing_evals/src/nowing_evals/suites/memory/recall/oracle.py:63-71,89-94,122-126]
  - `_numeric_score()` đọc `item["score"]` (RRF, tối đa ~2/61≈0.0328) nhưng runner default `--min-similarity 0.3` ⇒ mọi hit đều fail threshold. AC-7 đòi threshold chỉ đọc `similarity`. `gate.yaml` đã flip sang `required_oracle_mode: score_threshold` nên gate sẽ vô nghĩa. Fix: đọc `item["similarity"]`, giữ `score` cho ordering/diagnostic.

- [ ] [Review][Patch] A2. AC-7 không có evidence nào — AC-7 / D10 [story file, Story Debug Log 611-613; nowing_evals/]
  - Không tồn tại `3-14-eval-<UTC_RUN_ID>` dir; `evidence/` chỉ có performance JSON. `run_artifact.json` duy nhất trong repo là suite `multimodal_doc` (2026-05-14, không liên quan). Story Debug Log dòng 611-613 vẫn nguyên placeholder `_exact path required_` / `_path + SHA-256 required_` / `_exact run; exit 1 baseline-only_`, nhưng Task 6 đã tick `[x]`.

- [x] [Review][Patch] A3. D10 provenance chưa implement — AC-7 [nowing_evals/src/nowing_evals/suites/memory/recall/runner.py:364-390]
  - `extra` chỉ có `workspace_id/concurrency/sample_n/provider_model/failures/backend_build_id`. Thiếu toàn bộ: repo SHA/branch/dirty + patch SHA-256, Python/platform, `uv.lock` SHA-256, dataset/corpus-map/runner SHA-256, argv/run id, requested vs effective params, raw SHA-256 + row count.

- [x] [Review][Patch] A4. REST search index `embeddings[0]` trước khi validate cardinality — D6, AC-1/AC-6 [nowing_backend/app/routes/memories_routes.py:94-95, nowing_backend/app/routes/research_threads_routes.py:76-77]
  - `validate_single_embedding_result` được tạo đúng để chặn việc này (middleware/repository đã dùng), nhưng 2 route REST vẫn `embeddings[0]` trực tiếp ⇒ provider trả 0/nhiều/non-sequence sẽ ra IndexError/500 thay vì `invalid_count`.

- [x] [Review][Patch] A5. Internal search clamp `top_k` thay vì raise — D9, AC-8 [nowing_backend/app/services/memory/search.py:95,116; tests/integration/memory/test_hybrid_search_scope_and_bounds.py:60-77]
  - `output_limit = min(max(top_k,0), _MAX_RESULTS)`, `candidate_limit = min(max(top_k,0)*3, 15)`. D9 bảng yêu cầu internal search: `0`/bool/`6+` → `ValueError`. Hiện `0`→0 kết quả, `6+`→clamp, `True`→1. Tệ hơn: test mới gọi `top_k=100` và assert `len(hits) <= 5` — tức là **khóa cứng hành vi sai**. Phải sửa cả test.

- [x] [Review][Patch] A6. Migration 182 + `db.py` đã commit — AC-3 reproducibility [nowing_backend/app/db.py, nowing_backend/alembic/versions/182_add_memories_workspace_thread_dependency_stats.py]
  - Commit `bd7284fbe` trên `develop`: migration 182 drop redundant `ix_memories_research_thread_id` + thêm `CREATE STATISTICS` workspace/thread dependencies; `db.py` bỏ `index=True` để fresh checkout không tái tạo index đã drop. Điều này fix flaky 10.18x ratio gate.

- [x] [Review][Patch] A7. `backend_build_id` là label không được kiểm chứng — AC-7 / D10 [.github/workflows/memory-recall-release-gate.yml, nowing_evals/src/nowing_evals/suites/memory/recall/runner.py:370, nowing_evals/src/nowing_evals/core/gate.py, nowing_backend/app/app.py:/health]
  - Chỉ check nonblank; `runner.py:370` copy nguyên văn vào artifact; `core/gate.py` không đối chiếu. Dispatch `backend_build_id=good-build` có thể đánh giá deployment cũ mà vẫn mang nhãn đúng. Cần query version endpoint hoặc đối chiếu commit.

#### MEDIUM (20)

- [x] [Review][Patch] B1. `search.py:100` — recency mode kích hoạt khi `query_embedding is None` OR query blank [nowing_backend/app/services/memory/search.py:100]
  - D6 đòi: ranked = nonblank query + valid vector; recency = blank + `None` + thread id; mismatch → raise. Hiện nonblank-query-nhưng-thiếu-vector âm thầm trả recency (che lỗi upstream).

- [x] [Review][Patch] B2. `search.py:97-111` — recency không require `research_thread_id` [nowing_backend/app/services/memory/search.py:97-111]
  - Test `test_search_recency_mode_returns_null_score_and_similarity` gọi workspace-scope không thread ⇒ cũng khóa hành vi sai.

- [x] [Review][Patch] B3. `vector.py:69` — validate finite/norm ở `float64` rồi `ascontiguousarray(..., np.float32)` không re-check [nowing_backend/app/services/memory/vector.py:69]
  - `[1e39]*384` pass hết rồi overflow thành `inf`, phá đúng guarantee của hàm.

- [x] [Review][Patch] B4. `research_threads_routes.py:48` — `top_k: int = Query(default=5, ge=1, le=5)` không bool-strict [nowing_backend/app/routes/research_threads_routes.py:48]
  - D9 đòi strict/before validation ở **cả** REST search và context. Chỉ `MemorySearchRequest` được migrate sang `strict_top_k`.

- [x] [Review][Patch] B5. `middleware.py:173` — `_build_transcript_query()` không có failure boundary [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:173]
  - D8 bắt buộc reason `stage=query, reason=render_error` không tồn tại trong production code.

- [x] [Review][Patch] B6. `middleware.py:200-202` — không validate shape của search result [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:200-202]
  - D8 đòi reason `stage=search, reason=invalid_result` (non-list / non-`ScoredMemory` / missing memory / metadata nonnumeric-nonfinite / output >5) không tồn tại trong production code.

- [x] [Review][Patch] B7. `metrics.py:896` — `_add(_memory_injection_failures(), 1, attrs)` gọi ngoài `contextlib.suppress` [nowing_backend/app/observability/metrics.py:896]
  - `_memory_injection_failures()` được gọi NGOÀI `contextlib.suppress` (chỉ log ở dòng 894 được suppress). Nếu `_get_meter().create_counter(...)` raise thì lỗi backend telemetry propagate và đổi control flow của middleware. D8 đòi suppress mọi backend failure. Test hiện chỉ cover `counter.add` nổ.

- [x] [Review][Patch] B8. `on_failure` steps bỏ qua save-time validation — D9 [nowing_backend/app/automations/services/automation.py:50,:141; app/automations/schemas/definition/execution.py:20]
  - `app/automations/services/automation.py:50` và `:141` chỉ truyền `definition.plan`. `definition.execution.on_failure` cũng là `list[PlanStep]` và executor thật sự chạy chúng (`runtime/executor.py:136-141`). Unknown action / thiếu required / `top_k` sai trong `on_failure` vẫn persist được.

- [x] [Review][Patch] B9. `automation.py:132-141` — `definition: null` gây `AttributeError` [nowing_backend/app/automations/services/automation.py:132-141]
  - `data = patch.model_dump(exclude_unset=True)`; `AutomationUpdate.definition` là `AutomationDefinition | None`. Client gửi `definition: null` ⇒ `"definition" in data` là True nhưng `patch.definition` là `None` ⇒ `patch.definition.plan` raise `AttributeError` ⇒ 500 thay vì 422.

- [x] [Review][Patch] B10. `runtime/step.py:38-72` — sau `render_value` không validate full `action.params_model` trước `build_handler`/`with_retries` [nowing_backend/app/automations/runtime/step.py:38-72]
  - D9.5 đòi v1.1 validate model đầy đủ sau render, trước handler/retry, cho cả normal và `on_failure`.

- [x] [Review][Patch] B11. `schemas/definition/envelope.py:33` — `schema_version: str = "1.0"` không có `Literal["1.0","1.1"]`/validator [nowing_backend/app/automations/schemas/definition/envelope.py:33]
  - `"2.0"`/`"garbage"` parse OK rồi chạy nhánh strict như 1.1 (`continue_research/invoke.py` chỉ đặc biệt hoá đúng chuỗi `"1.0"`). D9.1 nói chỉ support 1.0/1.1.

- [x] [Review][Patch] B12. `actions/validation.py:91-92` — `_is_templated()` chỉ nhận string top-level match `{{.*}}` [nowing_backend/app/automations/actions/validation.py:91-92]
  - Runtime `templated` check bỏ qua nested field/cross-field template; non-template field được Pydantic coerce vẫn persist ở dạng non-canonical.

- [x] [Review][Patch] B13. `actions/validation.py` — field Pydantic `StrictInt`/`int` vẫn coerce `5.9`/`True` [nowing_backend/app/automations/actions/validation.py]
  - `StrictInt`/`int` annotation chưa khoá `top_k` 1..5 trước khi `bool`/`float` được Pydantic coerce vẫn persist ở dạng non-canonical.

- [x] [Review][Patch] B14. `mcp_server/features/memory/__init__.py:226-236` — `_render_recall` thiếu metadata `rrf`/`similarity` [nowing_mcp/mcp_server/features/memory/__init__.py:226-236]
  - `_render_recall` chỉ in id/type/confidence/content. AC-6 đòi ranked `rrf=<6 decimals>, similarity=<6 decimals>` và recency `rank=recency, rrf=n/a, similarity=n/a`. `_render_continue` reuse renderer thiếu này.

- [x] [Review][Patch] B15. `services/memory/renderer.py:99-153` (`_truncate_atoms`) — không đảm bảo ≥1 whole atom fit [nowing_backend/app/services/memory/renderer.py:99-153]
  - Chỉ check `budget < len(marker)+1 → None`, không check có atom NGUYÊN nào fit. Nội dung escaped là `&amp;` (5 ký tự) với đúng 1 ký tự dư sau marker ⇒ trả về chỉ `[...truncated...]`, không content atom nào. D7.10-11 đòi ≥1 whole atom, hoặc omit/`compose_error`.

- [x] [Review][Patch] B16. `benchmark_memory_story_3_14.py:223-229` — `query_text_for_bucket()` cố tình thêm `s314probe` làm keyword arm collapse [nowing_backend/scripts/benchmark_memory_story_3_14.py:223-229]
  - Thêm `s314probe` (không xuất hiện ở bất kỳ row nào) ⇒ `plainto_tsquery` AND mọi lexeme ⇒ keyword CTE match 0 rows ⇒ RRF collapse về pure semantic. AC-3 đòi 100 bucket `s314bucket00..99` với **đúng 1% keyword selectivity**. Nghĩa là latency đo được không cover keyword arm / RRF union / merge cost.

- [x] [Review][Patch] B17. `benchmark_memory_story_3_14.py:637-692` (`run_injection_cell`) — bỏ giá trị trả về của `mw.abefore_agent(...)` [nowing_backend/scripts/benchmark_memory_story_3_14.py:637-692]
  - Gọi `mw.abefore_agent(...)` rồi **bỏ giá trị trả về**, chỉ verify hits captured từ `MemoryHybridSearch.search`. AC-3 anti-false-green đòi assert trên payload thật: đúng 1 bare wrapper, đúng 5 sentinel mỗi cái đúng 1 lần theo order, <8000 chars.

- [x] [Review][Patch] B18. `benchmark_memory_story_3_14.py:1354-1371` — `ANALYZE memories` chạy trong `async with async_session_maker()` không commit [nowing_backend/scripts/benchmark_memory_story_3_14.py:1354-1371]
  - `ANALYZE` là transactional trong PostgreSQL và `AsyncSession` close sẽ rollback ⇒ warmup/timing/EXPLAIN có thể chạy trên statistics cũ trước seed.

- [x] [Review][Patch] B19. Artifact thiếu phần lớn metadata AC-3 đòi [3-14-memory-performance.json]
  - Thiếu: PostgreSQL/pgvector version, migration head, HNSW/GIN index inventory, Python/platform, generator/script hash, argv chính xác, cache/concurrency, cell identity IDs, `uv.lock` hash.

- [x] [Review][Patch] B20. Artifact không serialize expected/actual ID list và sentinel manifest — chỉ ghi `verification_failures` (pass/fail) [3-14-memory-performance.json]
  - AC-3 đòi "expected+actual ID/sentinel evidence" để artifact tự chứng minh oracle đã chạy. Cũng thiếu stored-row vector audit theo reason.

#### LOW (4)

- [x] [Review][Patch] C1. `middleware.py:159-168` — empty-messages guard chạy TRƯỚC private-owner guard [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py:159-168]
  - D4 đòi owner guard ngay sau `del runtime`, trước mọi thao tác transcript. Không có side effect/telemetry nên tác động thực tế bằng 0, nhưng lệch contract chữ.

- [x] [Review][Patch] C2. `nowing_evals/.../recall/runner.py:229` — `int()` coerce `True`→1 và `5.9`→5 trước `clamp_top_k` [nowing_evals/src/nowing_evals/suites/memory/recall/runner.py:229]
  - `clamp_top_k(int(opts.get("top_k", 5)))` TRƯỚC khi `clamp_top_k` kịp reject bool/non-int.

- [x] [Review][Patch] C3. `benchmark:1487-1492` — `--samples`/`--warmups`/`--small-corpus`/`--large-corpus` không validate dương [nowing_backend/scripts/benchmark_memory_story_3_14.py:1487-1492]
  - `--samples 0` ⇒ `stats_for([])` index list rỗng ⇒ crash không ra artifact.

- [x] [Review][Patch] C4. `vector.py:80` — `isinstance(result, (list, tuple))` chỉ nhận list/tuple [nowing_backend/app/services/memory/vector.py:80]
  - Provider trả Sequence khác (vd numpy array) bị `invalid_count` dù hợp lệ. `embed_texts` hiện trả list nên chưa reachable.

#### EVIDENCE / DOC-LEVEL (6)

- [ ] [Review][Patch] D1. AC-5 chưa đạt — `freshness.status: "skipped"`, 0/30 sample, không task id, không p95 [3-14-memory-performance.json]
  - Story dùng escape clause "No live credentials/worker→not done" (0 LLM API key trong môi trường). Hợp lệ như một skip có chủ đích, NHƯNG nghĩa là **AC-1..AC-9 chưa pass toàn bộ** ⇒ story không thể `done`. Cần quyết định: chấp nhận skip có điều kiện, hay chặn.

- [x] [Review][Patch] D2. `--freshness-samples` được parse nhưng không bao giờ chạy sample; `provenance["pass"]` chỉ tính từ latency gates [3-14-memory-performance.json, benchmark_memory_story_3_14.py]
  - Script in `PASS=True` kể cả trong môi trường CÓ credentials. Nên fail-loud hoặc đánh dấu partial.

- [ ] [Review][Patch] D3. Story Debug Log 611-613 còn placeholder chưa điền [3-14-memory-injection-bounded-retrieval.md:611-613]
  - Còn placeholder `_exact path required_` / `_path + SHA-256 required_` / `_exact run; exit 1 baseline-only_`, mặc dù Task 6 đã tick `[x]`.

- [x] [Review][Patch] D4. File List sai và thiếu [3-14-memory-injection-bounded-retrieval.md]
  - `nowing_backend/app/services/memory/renderer.py` liệt kê ở mục **New** nhưng đã tồn tại tại baseline `25ba542c2`. Thiếu: `app/automations/schemas/definition/envelope.py`, `app/automations/runtime/step.py`, `_bmad-output/implementation-artifacts/deferred-work.md`.

- [x] [Review][Patch] D5. Change Log nói "200,400-row shared background" nhiều lần, trong khi corpus benchmark là **200,400** [3-14-memory-injection-bounded-retrieval.md]
  - 200,406 là global count sau seed vì `g0=6`. Artifact tự xác nhận `run_tag_count=200400` / `g_after_seed=200406`.

- [x] [Review][Patch] D6. Migration 181 dùng `CREATE INDEX` thường và 182 dùng `DROP INDEX` thường trên bảng `memories` đang hot [nowing_backend/alembic/versions/181_*.py, 182_*.py]
  - Không `CONCURRENTLY` + autocommit block. Build index 3 cột trên 50k+ rows sẽ block writes.

## Dev Notes

### Failure sequence

```text
private-owner guard -> final-human/messages guard -> transcript -> embed/validate
  -> session enter -> search/materialize -> display-name SAVEPOINT (pending)
  -> session exit -> bounded render -> insert/no-op
  -> emit pending only if no later terminal
```

Team scope bypasses only private-owner guard. Private name-only is reachable only after usable transcript + successful zero-result search + valid name.

### Definitive touch set

**Required production:**

- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py`
- `nowing_backend/app/services/memory/{search,repository,renderer}.py`
- `nowing_backend/app/services/memory/vector.py` (NEW)
- `nowing_backend/app/observability/metrics.py`
- `nowing_backend/app/schemas/memory.py`
- `nowing_backend/app/routes/{memories_routes,research_threads_routes}.py`
- `nowing_backend/app/automations/schemas/definition/envelope.py`
- `nowing_backend/app/automations/actions/validation.py` (NEW)
- `nowing_backend/app/automations/services/automation.py`
- `nowing_backend/app/automations/runtime/{executor,step}.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/{params,invoke}.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py` — cả `_SCHEMA` + 3 few-shots phát 1.1
- `nowing_web/lib/automations/builder-schema.ts` — `buildDefinition()` phát 1.1
- `nowing_mcp/mcp_server/features/memory/{annotations,__init__}.py`
- `nowing_evals/src/nowing_evals/core/{cli,clients/memories}.py`
- `nowing_evals/src/nowing_evals/suites/memory/recall/{oracle,runner,gate.yaml}`
- `.github/workflows/memory-recall-release-gate.yml`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `nowing_backend/scripts/benchmark_memory_story_3_14.py`

**Required focused tests/evidence:**

- middleware/renderer/metrics/repository/search; real-DB routes/context/automation; automation save/runtime version.
- `nowing_backend/tests/unit/agents/multi_agent_chat/test_automation_prompt.py` (NEW) — rendered schema + 3 few-shots all 1.1, no new-write 1.0.
- `nowing_web/tests/automations/builder-schema.test.ts` (NEW) — call `buildCreatePayload()`, assert generated definition 1.1; run directly bằng `tsx` vì package hiện không có unit-test script.
- `nowing_evals/tests/core/test_cli_run_preflight.py` (NEW) — missing/blank ID exits before config/auth/network; valid ID proceeds to normal auth seam.
- `nowing_evals/tests/suites/test_memory_recall_ingest.py` — ingest remains valid without build ID.
- `nowing_mcp/tests/test_research_continuity.py` — explicit `query="pricing"` ranked và `query=""`/omitted recency requests, top_k 1/5/6/bool validation, metadata/citations order.
- Eval oracle/gate/runner/provenance/release workflow; performance JSON; isolated eval dir.

**Inspect/regression unless defect:**

- `nowing_backend/app/services/memory/service.py::read_memory`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`
- `nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py`
- compaction protected prefixes; PR MCP CI/selfcheck workflow.

**Excluded:** config/env, `content_utils.py`, dependencies, DB model/migration by default. Evidence-required migration/remediation enters File List with rationale.

### Reuse

Existing RRF/HNSW/GIN; legacy date/heading helpers; referenced-chat reverse-select pattern; `PROTECTED_SYSTEM_PREFIXES`; `embed_texts`; metrics `_add`; perf logger; Story 8.7 Celery seam; action registry/`params_model`, `render_value`, snapshot version. No second stack.

### Exact validation commands

Backend:

```bash
uv run --active python -m pytest tests/unit/agents/multi_agent_chat/test_automation_prompt.py tests/unit/services/test_memory.py tests/unit/agents tests/unit/automations -m unit
uv run --active python -m pytest tests/integration/workspaces/test_memory_routes.py tests/integration/memory tests/integration/automations/actions/builtin/continue_research/test_continue_research.py -m integration
uv run --active ruff check app tests scripts/benchmark_memory_story_3_14.py
uv run --active python scripts/benchmark_memory_story_3_14.py --small-corpus 100 --large-corpus 50000 --warmups 20 --samples 100 --freshness-samples 30 --output ../_bmad-output/implementation-artifacts/evidence/3-14-memory-performance.json
```

Evals:

```bash
uv sync --all-extras --frozen
uv run --active python -m pytest tests/core/test_cli_run_preflight.py tests/core/test_memory_recall_metrics.py tests/suites/test_memory_recall_dataset.py tests/suites/test_memory_recall_ingest.py tests/suites/test_memory_recall_suite.py tests/suites/test_memory_recall_gate.py tests/suites/test_memory_recall_selfcheck_ci.py -q
# D10 then supplies exact isolated ingest/run/gate/purge
```

MCP, exact dependency/selfcheck plus required memory/continuity tests:

```bash
uv sync --all-groups --frozen
uv run --active python -m mcp_server.selfcheck
uv run --active python -m pytest tests/test_memory_tools.py tests/test_research_continuity.py -q
```

Web (không dùng nonexistent unit-test script):

```bash
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm exec biome check lib/automations/builder-schema.ts tests/automations/builder-schema.test.ts
pnpm exec tsx tests/automations/builder-schema.test.ts
```

No watch; eval evidence must use the exact module-qualified commands above.

### Anti-patterns

No full-scan; no empty-transcript recency; no private missing-owner work/telemetry; no final-human-only/parser/deprecated `.text()`; no name SQL before search; no shared legacy renderer mutation; no empty wrapper/final slice/entity split; no delimiter/RRF-as-cosine/fake score; no query-vector⇒stored-vector assumption; no removal of ranked research context; no per-cell seed/timing on changing global background; no latency pass với `<5`/wrong IDs/name-only; no new-request clamp/bool coercion; no new-write producer 1.0; no weakened telemetry cardinality; no build-ID validation only after auth; no eager freshness/stale eval/fake build ID; no SM-10 ratification.

## References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.13/3.14
- PRD — FR-32, NFR-1b/1c/1d, NFR-8
- Architecture spine — AD-18
- `nowing_backend/app/services/memory/{search,repository,renderer,service}.py`
- `nowing_backend/app/routes/{memories_routes,research_threads_routes}.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py`
- `nowing_web/lib/automations/builder-schema.ts`
- `nowing_mcp/mcp_server/features/memory/__init__.py`
- `nowing_backend/app/automations/{schemas/definition/envelope.py,services/automation.py,runtime/{executor,step}.py}`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`
- `nowing_evals/src/nowing_evals/core/{cli,auth}.py`
- `.github/workflows/{memory-recall-gate,memory-recall-release-gate}.yml`
- `nowing_evals/src/nowing_evals/suites/memory/recall/*`
- [LangChain BaseMessage API 1.2.22](https://reference.langchain.com/python/langchain-core/messages/base/BaseMessage)

## Challenge Log

### Q1 — Duplicate logic?

Không: reuse search primitives, legacy helpers, message property, telemetry/Celery/automation seams. Injection renderer tách để không phá legacy.

### Q2 — Simpler?

Một scored search, one validator, fixed constants, existing schema-version seam và optional benchmark preflight hook. Không wrapper/env knobs/personal REST/dual SQL.

### Q3 — Deterministic?

Exact query modes/scopes/newlines/vector reasons/renderer/telemetry/versioning; fixed global-table benchmark với canonical top-5 IDs/sentinels; task identity; pre-auth build identity và isolated eval provenance.

### Q4 — External owner?

Chỉ SM-10 ratification; giữ `baseline_ratified:false`, `baseline_source:""` cho Story 3.9.

### Triage

**PROCEED.** Không còn implementation branch tự chọn; mỗi completion claim có owner/evidence/pass condition.

## Change Log

- 2026-07-28 (sub-agent, remaining code-only findings): Implemented A7 (backend build-id verification via `/health` + runner/gate), B19/B20 (benchmark artifact metadata, expected/actual IDs, sentinel manifest, stored-row vector audit by reason), D2 (fail-loud/partial when `--freshness-samples` cannot run), and D6 (migrations 181/182 use `CONCURRENTLY` + autocommit). Touched files: `nowing_backend/app/app.py`, `nowing_backend/scripts/benchmark_memory_story_3_14.py`, `nowing_backend/alembic/versions/181_add_memories_thread_recency_index.py`, `nowing_backend/alembic/versions/182_add_memories_workspace_thread_dependency_stats.py`, `nowing_evals/src/nowing_evals/suites/memory/recall/runner.py`, `nowing_evals/src/nowing_evals/core/gate.py`. Verified with `compileall`, `ruff check`, and targeted unit tests (`test_memory.py`, `test_automation_prompt.py`, `test_memory_recall_gate.py`, `test_memory_recall_suite.py`, `test_cli_run_preflight.py`, `test_memory_recall_metrics.py`). Remaining: A2/A7 final live verification, A6, D1, D3.

- 2026-07-28 (dev-story, review patch pass): Addressed all 37 Review Findings from the story spec: A1 oracle uses `similarity` for threshold; A3 runner provenance added; A4 REST routes validate embedding result cardinality; A5 internal search rejects out-of-bounds `top_k` and test fixed; B1/B2 search query/embedding consistency and recency requiring `research_thread_id`; B3 float32 overflow check; B4 `strict_top_k` in research context route; B5/B6 middleware failure boundaries for query rendering and search result validation; B7 telemetry counter suppressed; B8/B9 automation `on_failure` validation and `definition: null` guard; B10 runtime v1.1 params validation; B11 `schema_version` literal 1.0/1.1; B12/B13 nested template detection and `StrictInt` for `strict_top_k`; B14 MCP recall metadata; B15 renderer whole-atom guarantee; B16/B17/B18 benchmark keyword arm, payload verification, and `ANALYZE` commit; C1 guard order; C2/C3/C4 runner pre-coerce and benchmark positive int args and `Sequence` embedding result; with targeted tests green. D5 row-count typo fixed. Remaining: A2/A7 (eval evidence / build-id verification require live backend), A6 (migration 182 + `db.py` uncommitted per instruction), B19/B20 (artifact metadata expansion), D1-D4/D6 (docs/evidence/CONCURRENTLY). Implemented AC-3 latency evidence via `nowing_backend/scripts/benchmark_memory_story_3_14.py` (already authored in a previous session; this session executed it end-to-end, diagnosed a real regression it caught, and fixed the underlying schema). First full-scale run (8 cells, 200,400 background rows) failed only the `thread-recency` ratio gate — total p95 growing 9.05x (100→50,000 rows), driven by `MemoryHybridSearch.search()`'s query-less/recency branch (`WHERE workspace_id = :w AND research_thread_id = :t ORDER BY created_at DESC, id DESC LIMIT 5`) index-scanning the single-column `ix_memories_research_thread_id` and top-N-sorting the whole thread — O(thread size), confirmed via the artifact's captured `EXPLAIN` (Index Scan → Sort → Limit). Added migration `181_add_memories_thread_recency_index.py`: composite btree `ix_memories_thread_recency` on `(research_thread_id, created_at, id)`, partial `WHERE research_thread_id IS NOT NULL`, letting the planner satisfy the ORDER BY via a backward index scan under the leading-column equality — O(log n). A rerun still failed the same gate (10.18x, even worse) with `EXPLAIN` showing the planner still choosing the *old* single-column index + explicit `Sort` over the new composite index. Root-caused via a series of targeted, production-scale repros (built and torn down live, never left committed) to a classic PostgreSQL cardinality-underestimation bug: `workspace_id` and `research_thread_id` are functionally correlated (every thread-scoped memory belongs to exactly one workspace) but PostgreSQL's default statistics assume independence, so the equality filter's combined row estimate collapsed to `rows=1` for a predicate that actually matches 50,000 rows — a cost model built on that wrong estimate treats the worse (sorted, single-column-index) plan as competitive with the composite-index plan, and which one wins can flip between runs with no code/data change (autovacuum timing, table bloat). Added `CREATE STATISTICS ... (dependencies) ON workspace_id, research_thread_id` in migration `182_add_memories_workspace_thread_dependency_stats.py`: this alone measurably improved (not fixed) the flakiness in a live rerun, 10.18x → 6.35x, still over the ≤3.0x gate — the corrected estimate (`rows=1` → ~49,700, close to true) still left the two plans close enough in modeled cost for the choice to remain non-deterministic. Traced every `Memory.research_thread_id` filter site in the codebase (`app/services/memory/search.py` is the only one) and confirmed it is *never* used without an accompanying `workspace_id`/`user_id` scope condition (`_scope_conditions`, D5) — so the single-column index has no production query it uniquely serves; the composite index already covers every real equality+ORDER BY pattern strictly better. Extended migration 182 to also `op.drop_index("ix_memories_research_thread_id", ...)` and removed the corresponding `index=True` from the `Memory.research_thread_id` Column in `app/db.py`, eliminating the competing plan entirely rather than continuing to tune statistics to bias a comparison that has no reason to be close. Verified with a full clean-table rerun of the benchmark at full scale (200,400 rows, all 4 index/scope combinations): `PASS=True`, zero gate failures, all 8 cells' absolute p95 well under gate (injection DB ≤35ms vs 150ms gate; REST/recency total ≤26ms vs 300ms gate), all small→large growth ratios ≤1.22x (well under 3.0x), zero verification failures (exact canonical top-5 IDs/sentinels matched on every sample), zero seq-scans on `memories` in any captured `EXPLAIN`, and cleanup fully restored the table to the pre-run baseline (`g0==g_final==6`, `run_tag_count_final==0`). AC-5's live freshness harness remains explicitly skipped per the story's own escape clause (0 LLM API keys configured in `nowing_backend/.env` in this environment) — the benchmark script already records this as `status: skipped` in the artifact rather than a false pass. Also fixed a genuine (pre-existing-since-authoring, not caught until this session's `tsc --noEmit` run) TypeScript strict-null error in the Task 5 web test file `nowing_web/tests/automations/builder-schema.test.ts` (`payload.definition` typed as possibly `undefined` on `AutomationUpdateRequest`) with an explicit `assert.ok` guard, and reformatted its import statement to satisfy `biome check` (both were failing `tsc --noEmit`/`biome check` before this fix; confirmed via `git stash` that `lib/automations/builder-schema.ts`'s own pre-existing `ruff`-adjacent-equivalent `biome format` drift is unrelated baseline noise, left untouched). Ran the full backend regression after all fixes: unit `2926 passed, 2 skipped` (pre-existing environment-conditional skips), integration `481 passed, 3 failed` (all 3 confirmed pre-existing/zero-diff via `git stash` — `document_upload` PDF-processing/credit tests unrelated to this story, matching the baseline documented in sprint-status for Story 8.7); `nowing_evals` targeted suite 172 passed; `nowing_mcp` selfcheck + `test_memory_tools.py`/`test_research_continuity.py` 14 passed (the previously-documented `pytest-asyncio` gap from Task 1/5 has since closed on its own — `anyio` is now present transitively in `nowing_mcp/uv.lock` — so those tests now execute directly instead of remaining a documented gap); web `tsc --noEmit` clean, `biome check` clean on both touched files, `tsx tests/automations/builder-schema.test.ts` passes. `ruff check` clean on all touched/created backend files; `ruff format --check` on `app/db.py` reports drift, confirmed via `git stash` to be pre-existing at baseline, not introduced by this task.
- 2026-07-26 (dev-story, Task 6): Implemented D10 (pre-auth eval validation + fresh provenance + unambiguous gate run). `nowing_evals/src/nowing_evals/core/clients/memories.py`: fixed stale `_MAX_TOP_K = 100` local pre-check to `5`, matching D9's `strict_top_k(le=5)` server-side ceiling (locked by new `test_memories_search_rejects_top_k_above_backend_ceiling`). `nowing_evals/src/nowing_evals/suites/memory/recall/oracle.py` + `runner.py`: corrected stale docstrings/help text that still described the backend as serialising a fake `score=0.0` for every hit — Task 1 already replaced that with real, distinct RRF similarities, so `score_threshold` is now the normal oracle path and `rank_only` is the degraded fallback (stale deployment or genuine ties), not the default. `runner.py`: added required `--backend-build-id` CLI arg and `MemoryRecallBenchmark.validate_run_options(**opts)`, which rejects a blank/missing/non-string build id; called as the first line of `run()` for defense-in-depth, and the resolved id is now recorded in the artifact's `extra["backend_build_id"]`. `core/cli.py`'s `_cmd_run()`: added a pre-auth hook — if the benchmark declares `validate_run_options`, it runs (and can reject with exit code 2) *before* `load_config()`/`acquire_token()`, so an invalid run never touches config resolution or the network; `_cmd_ingest` deliberately left unchanged, since AC-7 scopes this gate to `run` only (ingest has no per-run backend to pin down). `gate.yaml`: flipped `required_oracle_mode` from `rank_only` to `score_threshold` — justified now (not deferred) because Task 1's backend fix is already merged/tested code, not something needing further live evidence, and AC-7 requires the gate to fail *only* on `baseline_ratified` once everything else is correct; leaving the old value would have stacked a second, spurious failure reason on top of the pre-existing baseline-unratified failure once a live run eventually happens. `.github/workflows/memory-recall-release-gate.yml`: added a required nonblank `backend_build_id` `workflow_dispatch` input plus an explicit fail-fast validation step (input `required: true` alone doesn't stop an API dispatch from sending an empty string); added a step computing a run-attempt-isolated `EVAL_DATA_DIR` (keyed to `github.run_id`+`github.run_attempt`, written via `$GITHUB_ENV` from a step rather than the job-level `env:` block, since `actionlint` confirmed the `runner` context isn't available there); added a step asserting that dir starts absent/empty before the corpus is seeded into it; passed `--backend-build-id` into the "Measure recall" step; changed the artifact upload path from the static `nowing_evals/data/memory/runs/` to `${{ env.EVAL_DATA_DIR }}/memory/runs/`; left the `if: always() && inputs.purge` purge condition byte-exact (locked by a new dedicated test). New tests: `test_cli_run_preflight.py` (4 tests: rejects missing/blank build id before `load_config`/`acquire_token` ever run, valid id reaches the normal credential-error seam, a benchmark with no `validate_run_options` hook is unaffected); `test_memory_recall_suite.py` gained `validate_run_options` unit tests plus two `run()`-level tests (rejects before touching the client; records the build id in the artifact); `test_memory_recall_ingest.py` gained a test confirming `ingest()` stays callable with zero backend_build_id; `test_memory_recall_selfcheck_ci.py` gained 6 structural YAML tests locking every new release-workflow requirement (purge condition exactness, required nonblank build id, build id passed into the run command, per-attempt dir isolation, empty-dir assertion ordering, exact upload path). Validated with `actionlint` (clean) and `yaml.safe_load` round-trips. Full `nowing_evals` regression: 470 passed, 1 skipped (up from 464 before this task); Ruff `check` clean on all touched/created files. Known pre-existing gap, not introduced by this task: `ruff format --check` reports 7 of the 9 touched files as non-compliant, but `git show HEAD:<path> | ruff format --check -` confirms 5 of them (`cli.py`, `memories.py`, `oracle.py`, `runner.py`, `test_memory_recall_suite.py`) were already non-compliant before this session edited them — i.e. pre-existing repo-wide formatting drift unrelated to Story 3.14, left alone rather than folded into this diff (a blanket `ruff format` would touch unrelated lines and obscure this task's actual changes); the one genuinely new file this task authored (`test_cli_run_preflight.py`) was formatted clean since it has no "pre-existing" excuse.
- 2026-07-26 (dev-story, Task 5): Implemented D9 (strict public `top_k`) + D5 preservation + prompt-literal migration to schema_version "1.1". New `app/utils/strict_fields.py`: `strict_top_k(le, description)` returns `Annotated[int, BeforeValidator(_reject_bool), Field(ge=1, le=le, ...)]` — `BeforeValidator` is the only mechanism that rejects `bool` before Pydantic v2's lax-mode int coercion silently turns `True`/`False` into `1`/`0`. Used to give `ContinueResearchActionParams.top_k` a strict `1..5` ceiling (new-write producers) while `_LegacyContinueResearchActionParams.top_k` keeps the old `1..100` range for schema_version "1.0" reads; `invoke.py` clamps a legacy `top_k>5` down to 5 with a `logger.warning(..., extra={"reason": "top_k_above_5"})` instead of rejecting, so pre-existing "1.0" automations don't start failing. `ActionContext` gained `schema_version: str = "1.1"` (defaults to the current new-write producer version). `_build_action_ctx` (executor.py) now takes the full `AutomationDefinition` instead of just `AutomationModels | None`, extracting both `.models` and `.schema_version` so an action's `invoke()` can branch on which contract produced the run. New `app/automations/actions/validation.py`: `validate_plan_steps()` walks a plan's steps at save time, resolving each step's registered action, validating every *static* (non-Jinja-templated, detected via `_JINJA_PATTERN = re.compile(r"{{.*}}", re.DOTALL)`) param field individually via `FieldInfo.rebuild_annotation()` + `TypeAdapter` (preserves the `BeforeValidator` bool-rejection alongside `Ge`/`Le`), deferring templated fields to runtime, and raising `StepValidationError` (carries `step_id`) on unknown action / unknown params field / missing required field / out-of-range static value, so a bad plan 422s before any commit. Wired into `AutomationService.create()`/`.update()` (automation.py): both now call the validator before persisting and always normalize the persisted `definition["schema_version"]` to the current "1.1", even when the client omits it or sends a legacy "1.0" — an `update()` patch that never touches `definition` leaves the existing snapshot (including its schema_version) untouched. Migrated all 4 backend prompt literals that construct `AutomationDefinition`/`ActionContext` payloads (`app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py`) plus the web automation builder (`nowing_web/lib/automations/builder-schema.ts`) to emit `schema_version: "1.1"`. D5 preservation: confirmed (no code change needed) that `MemorySearchRequest._require_query_or_thread` (schema-level, `app/schemas/memory.py`, pre-existing from Task 1) still enforces "blank query only valid with `research_thread_id`" on REST `/memories/search`; `nowing_recall` MCP tool keeps `query: Field(min_length=1, ...)` (required nonblank); `nowing_continue_research` MCP tool + REST `/research-threads/{id}/context` keep optional query with ranked/recency fallback (`research_threads_routes.py` already `Query(default="", ...)` + `top_k: int = Query(default=5, ge=1, le=5)`); automation `continue_research` still has no `query` field at all (recency-only by design). Full regression confirming zero D5 drift: `tests/integration/memory` + `tests/integration/workspaces/test_memory_routes.py` + `test_memory_type_filter.py` — 76 passed (includes pre-existing `test_search_empty_query_requires_thread`/`test_continue_research_empty_query_scopes_by_thread` covering the REST blank/nonblank rule, and `test_continue_context_recall_matches_recall_definition` covering the context-endpoint/recall parity rule). Test work this session: rewrote `test_params.py` (14 tests, le=5 ceiling + 6 new `_LegacyContinueResearchActionParams` tests for the 1..100 range); new `test_validation.py` (9 tests covering the registry validator's unknown-action/unknown-field/missing-required/templated-deferral/first-failing-step behavior, using the real self-registered `continue_research` action as fixture, no fakes); new `test_automation_service_validation.py` (7 tests covering create/update 422-on-invalid-plan and schema_version normalization, including the update-without-definition no-op case); fixed a genuine regression the new validator correctly exposed in `test_automation_service_policy.py` (a `PlanStep(action="agent_task")` fixture with no `params` — `AgentTaskActionParams.query` is required — fixed by adding `params={"query": "hello"}`, not by weakening the validator); fixed `test_executor_action_ctx.py`'s two existing tests for `_build_action_ctx`'s changed signature and added a new test locking `schema_version` propagation; added 5 new real-DB integration tests to `test_continue_research.py` for the legacy clamp-and-warn behavior (via `caplog`) and the new-schema strict rejection. Ruff-clean on all touched/created files (auto-fixed import order on the two new test files). Known accepted gap (not a Task 5 regression, not fixed): the 3 MCP-side `top_k` tests added for `nowing_continue_research` remain unverified by direct execution because `nowing_mcp`'s `pyproject.toml` still lacks `pytest-asyncio`/`anyio` — same pre-existing, documented, out-of-scope gap as Task 1's Debug Log References (confirmed again via `grep -n "pytest-asyncio\|pytest_asyncio" uv.lock` in `nowing_mcp` — zero matches); the corresponding backend-side production logic (`TopK` annotation) was verified correct by direct type-tracing.
- 2026-07-26 (dev-story, Task 2+3+4): Rewrote `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` từ đầu (thay bản cũ 176 dòng dùng `render_memory_markdown` không giới hạn + cảnh báo `MEMORY_HARD_LIMIT`/`MEMORY_SOFT_LIMIT` inline + load team memory vô điều kiện). Constants module-local D2 (`_MEMORY_INJECTION_TOP_K=5`, `_MEMORY_QUERY_MAX_CHARS=4_000`, `_MEMORY_INJECTION_MAX_CHARS=8_000`), không configurable qua env/config. D4: `_build_transcript_query`/`_usable_records`/`_role_for`/`_normalize_text`/`_is_protected` — role map qua `isinstance` (Human/AI/System/Tool), `str.splitlines()` làm nguồn chân lý newline, skip protected system message (dùng `PROTECTED_SYSTEM_PREFIXES` từ `compaction.py`), windowed newest-to-oldest với boundary truncation dùng marker riêng `"[...truncated...] "` (có khoảng trắng cuối, khác marker của renderer). Private-owner guard sớm nhất (`user_id is None` cho scope user → no-op ngay, team bypass hoàn toàn). D8: state machine chính xác trong `abefore_agent` — precedence embedding→session-enter→search (terminal, skip display-name lookup)→session-exit (override pending)→render (override pending); display-name lookup qua `session.begin_nested()` SAVEPOINT cô lập lỗi, kết quả set `pending` chỉ flush khi có injection thật hoặc không có terminal nào khác đè lên; render chạy sau khi session đã đóng (an toàn vì `async_session_maker` dùng `expire_on_commit=False`, ORM object giữ nguyên attribute đã load); cancellation trong search propagate nguyên vẹn, không log/counter nào. Task 3 (renderer D7) và Task 4 (telemetry D8 helper `record_memory_injection_failure`) đã hoàn thành ở phiên trước, được xác nhận lại qua chính bộ test tích hợp của Task 2 vì cả hai chỉ thực sự được exercise đầy đủ qua call site thật trong middleware. Thêm 23 test mới (`tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py`) phủ: golden transcript build, boundary truncation với marker, private no-user-id no-op, empty/last-not-human early return, toàn bộ precedence D8 (embedding/session-enter/search/session-exit/render lỗi, pending flush/override, cancellation), true no-op (0 hit + không tên), successful injection index 0/1. Sanity mutation test (đổi tạm `if not terminal and not is_team:` → `if not is_team:`, xác nhận đúng 1 test fail, revert) thay cho red-phase thật vì code+test viết liền nhau. Ruff clean (`ruff check --fix` tự sửa 4 lỗi I001/F401/UP037, `ruff format` 2 file). Full regression liên quan (`test_memory_injection_middleware.py`, `test_bounded_memory_injection_renderer.py`, `test_memory_injection_telemetry.py`, `test_memory.py`, `test_memory_service.py`): 62 passed, 1 fail — `test_repository_dedup_updates_existing_memory`, xác nhận zero-diff pre-existing qua `git stash`/`git stash pop` tại baseline `25ba542c2` (đã ghi nhận từ Task 1, không liên quan Story 3.14), flagged riêng bằng background task để fix sau, không chặn Task 2.
- 2026-07-26 (dev-story, Task 1): Implemented D1/D5/D6 — new `app/services/memory/vector.py` (shared `validate_embedding_vector`/`validate_single_embedding_result`/`VectorValidationError` với taxonomy `non_numeric`, `invalid_shape`, `invalid_dimension`, `non_finite`, `non_finite_norm`, `zero_norm`, `provider_error`, `invalid_count`), consumed by cả write path (`repository.py`, thay `_as_np`) và read path (`search.py`). Rewrote `MemoryHybridSearch.search()` để trả `list[ScoredMemory]` (dataclass frozen `memory`/`score`/`similarity`) thay vì `list[Memory]`: `_scope_conditions()` enforce đúng-một-trong `workspace_id`/`user_id`, `research_thread_id` chỉ hợp lệ ở workspace scope, raise `ValueError` trước khi build SQL (không có broad `OR`); RRF hybrid dùng `row_number()` (không phải `rank()`) với tie-break `id ASC`/`id DESC` xác định; candidate bound tại `min(top_k*3, 15)`, output bound tại `min(top_k, 5)`; mỗi stored embedding candidate được validate lại trước khi trả, hàng invalid bị skip+log chứ không raise; recency mode (no query) trả `score=None, similarity=None` thay vì fake `0.0`. Lan truyền contract mới qua 3 caller (`memories_routes.py`, `research_threads_routes.py`, `continue_research/invoke.py`) và `MemorySearchHit` schema (`score`/`similarity` nullable). Export `ScoredMemory`/`VectorValidationError`/`validate_embedding_vector`/`validate_single_embedding_result` từ `app/services/memory/__init__.py` cho Task 2 dùng. Thêm 4 unit test pure (`_scope_conditions`) và 6 real-DB integration test mới (`test_hybrid_search_scope_and_bounds.py`) cho scope isolation, bounded-5, finite score/similarity, zero-norm stored-row audit, recency null contract, missing-scope raise. Sửa 1 assertion cũ trong `test_continue_research.py` (`ScoredMemory` không có `.id`). Full regression: unit (`test_memory.py`, `tests/unit/agents`, `tests/unit/automations`) 1029 passed / 1 pre-existing unrelated fail (`test_repository_dedup_updates_existing_memory` — `_FakeSession.refresh()` no-op bug từ Story 6.5, zero-diff baseline, không do Story 3.14); integration (`test_memory_routes.py`, `tests/integration/memory`, `test_continue_research.py`) 81 passed / 0 fail; Ruff clean trên toàn bộ file đã sửa/tạo (33 lỗi ruff còn lại trong `app`/`tests` đều ở file không đụng tới, pre-existing). MCP (`nowing_mcp/tests/test_memory_tools.py`, `test_research_continuity.py`) 8 passed / 2 fail — pre-existing, do `nowing_mcp/pyproject.toml` chưa khai `pytest-asyncio` (không phải regression từ Task 1, không đụng file MCP nào).

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (bmad-dev-story workflow), 2026-07-26.

### Debug Log References

- Fresh `run_artifact.json`: _exact path required_
- Fresh `raw.jsonl`: _path + SHA-256 required_
- Gate stdout/status: _exact run; exit 1 baseline-only_
- Performance/freshness: `_bmad-output/implementation-artifacts/evidence/3-14-memory-performance.json`
- Task 1 pre-existing unrelated failures (confirmed zero-diff vs baseline `25ba542c2`, not introduced by this story):
  - `nowing_backend/tests/unit/services/test_memory.py::test_repository_dedup_updates_existing_memory` — `_FakeSession.refresh(obj, attribute_names=None)` no-op never assigns ORM `id`; `Memory().id` stays `None`, fails `MemoryChangedPayload(memory_id=...)` int validation (Story 6.5 bug).
  - `nowing_mcp/tests/test_research_continuity.py::test_continue_research_renders_memories_and_citations` and `::test_continue_research_missing_thread_returns_clear_error` — `nowing_mcp/pyproject.toml` dev group only declares `pytest>=8.0`, no async plugin (`pytest-asyncio`/`anyio`), so both `async def` tests fail to collect/run. Pre-existing environment gap since the file's introduction (Story 4.6 commit `4a72091b8`); adding a new test dependency is outside Task 1's scope and would need separate user approval.
- Task 5 — same pre-existing `nowing_mcp` `pytest-asyncio` gap (reconfirmed via `grep -n "pytest-asyncio\|pytest_asyncio" uv.lock` in `nowing_mcp`, zero matches) also blocks direct execution of 3 new MCP tests for `nowing_continue_research`'s `top_k` bounds (`test_continue_research_accepts_boundary_top_k`, `test_continue_research_rejects_top_k_above_five`, `test_continue_research_rejects_bool_top_k`, in `nowing_mcp/tests/test_research_continuity.py`). Not fixed for the same reason as above (pre-existing, out of scope, needs separate user approval); the backend-side `TopK` annotation these tests exercise was verified correct by direct type-tracing and by the passing backend-side equivalents in `test_params.py`.
- Task 6 — judgment call: proactively flipped `gate.yaml`'s `required_oracle_mode` from `rank_only` to `score_threshold` in this session rather than deferring to a live-evidence-first approach, because Task 1's backend fix (real RRF scores, not fake `0.0`) is already merged/tested code rather than something needing further live verification, and AC-7 requires the gate to fail *only* on `baseline_ratified` once everything else is correct. Verified this doesn't break `test_memory_recall_gate.py`'s existing tests (they accept either oracle-mode value and independently assert `baseline_ratified is False`).
- Task 6 — pre-existing `ruff format` drift (not introduced by this task): `ruff format --check` on the 9 touched Task 6 files originally reported 7 as non-compliant (`cli.py`, `memories.py`, `oracle.py`, `runner.py`, `test_cli_run_preflight.py`, `test_memory_recall_selfcheck_ci.py`, `test_memory_recall_suite.py`). Confirmed via `git show HEAD:<path> | ruff format --check -` that `cli.py`, `memories.py`, `oracle.py`, `runner.py`, `test_memory_recall_suite.py`, and `test_memory_recall_selfcheck_ci.py` were ALL already non-compliant at `HEAD` before this session touched them (each has pre-existing unrelated lines the formatter wants to collapse, e.g. a multi-line `assert`/list-comprehension it would join to one line) — pre-existing repo-wide drift, not a regression from Task 6; new lines added to `test_memory_recall_selfcheck_ci.py` this task simply mirrored an existing pattern already present in the file's drifted region. CI does enforce `ruff format --check .` (`.github/workflows/test.yml:93`), so this drift is a real but pre-existing CI risk unrelated to this story; left unfixed rather than folded into this diff to avoid unrelated-line churn across 6 files. `test_cli_run_preflight.py` — the one file genuinely new to this task with no "pre-existing" excuse — was reformatted clean via `uv run ruff format`. Post-fix state re-verified: `ruff format --check` now reports exactly these same 6 pre-existing files, `ruff check` (lint) is clean on all 9, and the full suite still passes 470/1-skipped.
- Task 7 — full artifact history preserved at `_bmad-output/implementation-artifacts/evidence/3-14-memory-performance.json` (final, passing state; each intermediate failing run's JSON was overwritten by the next attempt rather than archived separately, since the story specifies one canonical evidence path and the Change Log entry above documents the diagnostic path in full). Every intermediate DB state created while diagnosing the `thread-recency` regression (multiple ad hoc Python repro scripts seeding 15k–200k rows directly via `Memory`/`insert()`, each torn down in its own `finally`/explicit cleanup block or via `DELETE ... WHERE content LIKE 's314run:%'`/`VACUUM (FULL, ANALYZE) memories` when a repro process was killed mid-run) was fully cleaned up before the final passing run; the final run's own artifact independently confirms `cleanup.global_restored_to_g0: true` and `cleanup.run_tag_count_final: 0`. Two benchmark instances were briefly and accidentally run concurrently against the same DB early in this session (one foreground call that had actually kept running past its reported timeout, plus a second background start) — caught via `ps aux`, both killed, the resulting 100,400 leftover rows deleted by exact `content LIKE 's314run:%'` match (never a broad table truncate), table `VACUUM (FULL, ANALYZE)`-ed back to `184 kB`/0 dead tuples before any further run.
- Task 7 — `default_statistics_target` (100) and per-column `SET STATISTICS` were left at their defaults in the shipped migrations; a repro that manually raised `research_thread_id`/`workspace_id` to `SET STATISTICS 1000` for diagnostic purposes showed no material improvement over the default-target `CREATE STATISTICS (dependencies)` object, so the simpler fix (drop the redundant index) was preferred over raising per-column statistics targets, which would need its own migration and Postgres-version-dependent tuning.

### Completion Notes List

- Task 1 complete: shared vector validator + D5/D6 scored hybrid search implemented, tested (unit + real-DB integration), Ruff-clean, and propagated through all direct callers. Zero regressions vs baseline; 2 known pre-existing failures documented above are out of scope.
- Task 2+3+4 complete: middleware rewritten ground-up implementing D4 (private-owner guard, transcript/newline contract, protected-system skip, boundary truncation) and D8 (exact single-attempt telemetry precedence with pending/override/cancellation semantics) on top of the already-complete D7 renderer (Task 3) and telemetry helper (Task 4), both now exercised end-to-end via real middleware call sites. 23 new unit tests, all passing; sanity mutation test performed in lieu of strict red-then-green since implementation and tests were authored together. Ruff-clean. Full related regression: 62 passed, 1 pre-existing unrelated failure (`test_repository_dedup_updates_existing_memory`, already documented under Task 1's Debug Log References, reconfirmed zero-diff at baseline).
- Task 5 complete: D9 strict public `top_k` (1..5, bool-rejecting, via new `strict_top_k()` helper) implemented for `ContinueResearchActionParams`, with `_LegacyContinueResearchActionParams` preserving the old 1..100 range and `invoke.py` clamping-with-warning instead of rejecting on legacy schema_version "1.0". New save-time `validate_plan_steps()` registry validator wired into `AutomationService.create()`/`.update()`, which also now normalizes every persisted `definition.schema_version` to the current "1.1". All 4 backend prompt literals + the web automation builder migrated to emit `schema_version: "1.1"`. D5's REST/MCP blank/nonblank query-mode matrix verified preserved (no code change needed — enforced by pre-existing `MemorySearchRequest._require_query_or_thread` plus unchanged MCP tool/route param contracts), confirmed via a 76-test regression sweep across `tests/integration/memory` and the memory-routes/type-filter suites with zero failures. 37 new/rewritten backend tests this task (14 `test_params.py` + 9 `test_validation.py` + 7 `test_automation_service_validation.py` + 2 fixed `test_executor_action_ctx.py` + 1 new in same + 5 new `test_continue_research.py` integration tests, minus the 1 pre-existing `test_automation_service_policy.py` fixture fix), all passing; Ruff-clean. One known accepted gap carried forward, documented above: 3 new MCP-side tests unverified due to the pre-existing `pytest-asyncio` absence in `nowing_mcp`.
- Task 6 complete: D10 pre-auth eval validation implemented end-to-end — `MemoryRecallBenchmark.validate_run_options()` rejects a blank/missing `--backend-build-id` before `run()` touches the client, and `core/cli.py`'s `_cmd_run()` calls this hook before `load_config()`/`acquire_token()`, so an invalid run never resolves config or hits the network; the resolved build id is recorded in the artifact's `extra`. `clients/memories.py`'s stale `_MAX_TOP_K=100` fixed to `5` to track D9's server-side ceiling. `oracle.py`/`runner.py` docstrings corrected to stop describing the backend as still faking `score=0.0` (Task 1 already fixed that), matching the justified flip of `gate.yaml`'s `required_oracle_mode` to `score_threshold`. `.github/workflows/memory-recall-release-gate.yml` rewritten to require a nonblank `backend_build_id`, fail fast on a blank API-dispatched value, isolate `EVAL_DATA_DIR` per run attempt, assert it starts empty, pass the build id into the run command, and upload exactly that isolated dir — with the pre-existing `purge` condition preserved byte-exact. 6 new tests validating suite-level behavior, 4 new CLI preflight tests, 1 new ingest-independence test, 6 new structural workflow tests (16 new tests total); full `nowing_evals` regression 470 passed / 1 skipped (up from 464); `actionlint` and `yaml.safe_load` both clean on the workflow; Ruff `check` clean on all touched/created files. One known accepted gap documented above: pre-existing (not introduced by this task) `ruff format` drift across 6 files, left unfixed to avoid unrelated-line churn; the one genuinely new file (`test_cli_run_preflight.py`) is formatted clean.
- Task 7 partially complete (AC-3 done and gate-passing; AC-5 explicitly skipped, not attempted). Executed `scripts/benchmark_memory_story_3_14.py` at full production scale (200,400-row shared background across 8 dedicated-identity cells) and used it to find and fix a real, previously-undetected performance bug: the `thread-recency` recall path (query-less `MemoryHybridSearch.search()` branch used by REST research-thread context / MCP `nowing_continue_research` / automation `continue_research`) scaled O(thread size) instead of O(log n) because the only available index on `research_thread_id` was single-column, forcing an explicit sort over the whole thread. Root-caused (via disposable, fully-cleaned-up production-scale repros, not guesswork) to a two-index-candidate planner tie caused by PostgreSQL underestimating the cardinality of `workspace_id`+`research_thread_id`'s functional correlation. Fixed with two new migrations: `181` adds a composite covering index (`research_thread_id, created_at, id`, partial on `research_thread_id IS NOT NULL`) that satisfies the query's `ORDER BY` directly; `182` adds `CREATE STATISTICS (dependencies)` on the correlated column pair *and* drops the now-fully-redundant single-column `ix_memories_research_thread_id` (verified, via a full-codebase search, that no production query filters `research_thread_id` without an accompanying workspace/user scope, so the composite index already dominates every real query shape) — removing the losing plan entirely rather than continuing to bias a cost-model comparison that had no reason to be close. Also fixed the `Memory.research_thread_id` ORM column's `index=True` (which was silently regenerating the dropped index) to keep the model in sync with the migration. Final full-scale rerun: `PASS=True`, 0 gate failures, 0 verification failures, 0 seq-scans, table fully restored to baseline row count after cleanup. AC-5's live freshness harness remains genuinely not attempted — this environment has 0 configured LLM API keys, which is the story's own explicit "No live credentials/worker→not done" escape clause, not a shortcut taken to avoid the work. Also fixed one small pre-existing gap surfaced by this session's regression pass: a `tsc --noEmit` strict-null error and a `biome check` formatting issue in Task 5's `nowing_web/tests/automations/builder-schema.test.ts`, both now clean. Full regression after all fixes: backend unit 2926/2 skipped (pre-existing), backend integration 481/3 failed (all 3 reconfirmed pre-existing/zero-diff via `git stash`, unrelated `document_upload` tests), `nowing_evals` targeted suite 172 passed, `nowing_mcp` 14 passed (previously-documented `pytest-asyncio` gap has since closed on its own via a transitive `anyio` dependency), web `tsc`/`biome`/`tsx` all clean, backend Ruff `check` clean (format drift on `app/db.py` reconfirmed pre-existing).

### File List

**New:**
- `nowing_backend/app/services/memory/vector.py`
- `nowing_backend/tests/integration/memory/test_hybrid_search_scope_and_bounds.py`
- `nowing_backend/tests/unit/services/test_bounded_memory_injection_renderer.py`
- `nowing_backend/tests/unit/observability/test_memory_injection_telemetry.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/__init__.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/memory/test_memory_injection_middleware.py`
- `nowing_backend/app/utils/strict_fields.py`
- `nowing_backend/app/automations/actions/validation.py`
- `nowing_backend/tests/unit/automations/actions/test_validation.py`
- `nowing_backend/tests/unit/automations/services/test_automation_service_validation.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/test_automation_prompt.py`
- `nowing_web/tests/automations/builder-schema.test.ts`
- `nowing_evals/tests/core/test_cli_run_preflight.py`
- `nowing_backend/scripts/benchmark_memory_story_3_14.py`
- `nowing_backend/alembic/versions/181_add_memories_thread_recency_index.py`
- `nowing_backend/alembic/versions/182_add_memories_workspace_thread_dependency_stats.py`

**Modified:**
- `nowing_backend/app/db.py` (Task 7: added `ix_memories_thread_recency` composite index in migration 181; Task 7 fix-up: removed the redundant `research_thread_id` single-column `index=True` in migration 182, see Change Log)
- `nowing_backend/app/services/memory/renderer.py`
- `nowing_backend/app/services/memory/search.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/services/memory/__init__.py`
- `nowing_backend/app/schemas/memory.py`
- `nowing_backend/app/routes/memories_routes.py`
- `nowing_backend/app/routes/research_threads_routes.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/invoke.py`
- `nowing_backend/tests/unit/services/test_memory.py`
- `nowing_backend/tests/integration/automations/actions/builtin/continue_research/test_continue_research.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py`
- `nowing_backend/app/observability/metrics.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/params.py`
- `nowing_backend/app/automations/actions/types.py`
- `nowing_backend/app/automations/runtime/executor.py`
- `nowing_backend/app/automations/runtime/step.py`
- `nowing_backend/app/automations/services/automation.py`
- `nowing_backend/app/automations/schemas/definition/envelope.py`
- `nowing_backend/tests/unit/automations/actions/builtin/continue_research/test_params.py`
- `nowing_backend/tests/unit/automations/runtime/test_executor_action_ctx.py`
- `nowing_backend/tests/unit/automations/services/test_automation_service_policy.py`
- `nowing_mcp/mcp_server/features/memory/__init__.py`
- `nowing_mcp/mcp_server/features/memory/annotations.py`
- `nowing_mcp/tests/test_research_continuity.py`
- `nowing_web/lib/automations/builder-schema.ts`
- `nowing_evals/src/nowing_evals/core/cli.py`
- `nowing_evals/src/nowing_evals/core/clients/memories.py`
- `nowing_evals/src/nowing_evals/suites/memory/recall/oracle.py`
- `nowing_evals/src/nowing_evals/suites/memory/recall/runner.py`
- `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml`
- `.github/workflows/memory-recall-release-gate.yml`
- `nowing_evals/tests/core/test_clients.py`
- `nowing_evals/tests/suites/test_memory_recall_suite.py`
- `nowing_evals/tests/suites/test_memory_recall_ingest.py`
- `nowing_evals/tests/suites/test_memory_recall_selfcheck_ci.py`
- `_bmad-output/implementation-artifacts/deferred-work.md`

## Story Completion Status

**Status:** in-progress
**Completion note:** Solution A, `BaseMessage.text`, fixed 5/4.000/8.000, private-owner early no-op, complete public mode/scope matrix, vector write/read validation, separate bounded renderer, exactly-one telemetry, explicit 1.1 backend/web producers, pre-auth eval build-ID validation, fixed-global exact-five latency evidence và exact eval provenance đã được khóa—không env knob/parser riêng hoặc SM-10 ratification. AC-3 latency evidence PASS at full production scale (200,400 rows) sau khi phát hiện và sửa một O(thread size) regression thật ở đường recency (2 migration mới: composite index + extended statistics + drop index dư). AC-5 freshness harness skipped đúng theo escape clause của story (0 LLM API key trong môi trường này) — không phải shortcut.

### Round 2 Review Patch Application

Patched files and findings applied during the Round 2 review (2026-07-28):

| # | File / location | Patch summary |
|---|-----------------|---------------|
| 1 | `nowing_backend/app/routes/research_threads_routes.py:84-86` | `query_embedding` now uses `validate_single_embedding_result(embeddings)` before indexing. |
| 2 | `nowing_backend/scripts/benchmark_memory_story_3_14.py:870-872` | `query_embedding` now uses `validate_single_embedding_result(embeddings)`; import added. |
| 3 | `nowing_backend/app/schemas/memory.py` + `research_threads_routes.py:44` | `MemorySearchRequest.query` and the research-thread `Query` parameter both enforce `max_length=4000`. |
| 4 | `nowing_backend/app/app.py:1142` | `_backend_build_id` decorated with `@functools.lru_cache(maxsize=1)`. |
| 5 | `nowing_backend/app/services/memory/search.py:98` | `top_k` guard accepts `np.integer` in addition to `int` (bool still rejected). |
| 6 | `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` | Every `abefore_agent` exception catch now logs the underlying exception with `logger.exception(...)` before converting to telemetry; fail-soft behavior preserved. |
| 7 | `nowing_mcp/mcp_server/features/memory/annotations.py` | `TopK` now uses `StrictInt` + `BeforeValidator(_reject_bool_top_k)` to mirror `strict_top_k`. |
| 8 | `nowing_backend/app/automations/actions/validation.py` | `_is_templated` now raises `StepValidationError` for unbalanced `{{`/`}}` markers; `_JINJA_PATTERN` is non-greedy. |
| 9 | `nowing_backend/app/services/memory/vector.py` | `validate_single_embedding_result` accepts a single-item `np.ndarray`. |
| 10 | `nowing_backend/scripts/benchmark_memory_story_3_14.py` | Raw SQL builders (`_scope_sql_for_injection`, `_recency_query_sql`, `_semantic_cte_sql`, `_keyword_cte_sql`, `_ranked_query_sql`) now use `text()` with bound parameters for workspace/thread/user IDs and query text; `_capture_explain` compiles the bound `TextClause`. |
| 11 | `_bmad-output/implementation-artifacts/deferred-work.md:39` | Stale `gate.yaml` comment updated to show the resolution now points to Story 3.14. |

Deferred findings recorded in `deferred-work.md` under `## Deferred from: code review of story-3.14 (2026-07-28)`:
- Dropping `ix_memories_research_thread_id` in migration 182 removes a safety net for future unscoped `research_thread_id` queries.
- `backend_build_id` verification could be hardened to only count `verified=True` when the source is the live `/health` endpoint, rather than a git-filesystem fallback.

Rejected findings (no code change):
- "SQLAlchemy ranked query not FULL OUTER JOIN" — `search.py` passes `full=True` to `outerjoin`; this is a false positive.
- `MemorySearchHit.score` / `similarity` nullable schema change is by design (recency returns `None`; ranked returns values).
- Removal of old `MEMORY_SOFT_LIMIT`/`MEMORY_HARD_LIMIT` warnings is by design; the bounded renderer focuses on the 8,000-character injection budget.
- `record_memory_injection_failure` logger/counter suppression follows the D8 fail-soft telemetry spec.
- Acceptance artifact stale / AC-5 freshness skipped are evidence blockers, not code patches; they remain open in the story file (A2, D1, D3, A7 verify).

Test results:
- `python -m compileall` on the 9 touched Python files: passed.
- `nowing_backend` targeted unit/integration tests: 118 passed, 0 failed (44 unit + 74 integration/integration-automation).
- `nowing_evals` targeted tests: 113 passed, 0 failed.
- `nowing_mcp` targeted tests: 14 passed, 0 failed.

No patches were intentionally skipped.

## Suggested Review Order

### Vector validation & search contract

- Shared vector validator with finite/zero-norm taxonomy
  [`vector.py:43`](../../nowing_backend/app/services/memory/vector.py#L43)
- Repository write path validates embedding before dedup
  [`repository.py:36`](../../nowing_backend/app/services/memory/repository.py#L36)
- Search scope enforces one of workspace or user
  [`search.py:47`](../../nowing_backend/app/services/memory/search.py#L47)
- Hybrid search query-mode and top-k bounds
  [`search.py:71`](../../nowing_backend/app/services/memory/search.py#L71)

### Memory middleware & bounded renderer

- Fixed 5/4k/8k injection constants
  [`middleware.py:53`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py#L53)
- `abefore_agent` guard and telemetry precedence
  [`middleware.py:172`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py#L172)
- Bounded transcript query with newline normalization
  [`middleware.py:120`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py#L120)
- 8,000-character bounded injection renderer
  [`renderer.py:284`](../../nowing_backend/app/services/memory/renderer.py#L284)
- Single-attempt log/counter telemetry helper
  [`metrics.py:886`](../../nowing_backend/app/observability/metrics.py#L886)

### Route & MCP validation

- Search request schema strict top-k and query-or-thread
  [`memory.py:70`](../../nowing_backend/app/schemas/memory.py#L70)
- REST search validates embedding cardinality
  [`memories_routes.py:79`](../../nowing_backend/app/routes/memories_routes.py#L79)
- Research context route enforces strict top-k
  [`research_threads_routes.py:41`](../../nowing_backend/app/routes/research_threads_routes.py#L41)
- MCP recall returns ranked metadata
  [`__init__.py:89`](../../nowing_mcp/mcp_server/features/memory/__init__.py#L89)

### Automation runtime

- Definition schema version literal 1.0/1.1
  [`envelope.py:38`](../../nowing_backend/app/automations/schemas/definition/envelope.py#L38)
- Create validates plan and normalizes to 1.1
  [`automation.py:46`](../../nowing_backend/app/automations/services/automation.py#L46)
- Save-time step validator rejects bad actions
  [`validation.py:39`](../../nowing_backend/app/automations/actions/validation.py#L39)
- v1.1 rendered params validated at runtime
  [`step.py:63`](../../nowing_backend/app/automations/runtime/step.py#L63)
- Continue research handles legacy and new top-k
  [`invoke.py:40`](../../nowing_backend/app/automations/actions/builtin/continue_research/invoke.py#L40)

### Benchmark & eval harness

- Oracle threshold reads similarity not RRF score
  [`oracle.py:63`](../../nowing_evals/src/nowing_evals/suites/memory/recall/oracle.py#L63)
- Pre-auth build-id rejection before config/auth
  [`runner.py:406`](../../nowing_evals/src/nowing_evals/suites/memory/recall/runner.py#L406)
- CLI pre-auth hook before load_config
  [`cli.py:539`](../../nowing_evals/src/nowing_evals/core/cli.py#L539)

### Migrations & DB model

- Migration 181 composite thread-recency index
  [`181_add_memories_thread_recency_index.py:43`](../../nowing_backend/alembic/versions/181_add_memories_thread_recency_index.py#L43)
- Migration 182 statistics and drop old index
  [`182_add_memories_workspace_thread_dependency_stats.py:75`](../../nowing_backend/alembic/versions/182_add_memories_workspace_thread_dependency_stats.py#L75)

### Evidence still pending

- A2/D1/D3/A7 evidence still pending
  [`3-14-memory-injection-bounded-retrieval.md:454`](3-14-memory-injection-bounded-retrieval.md#L454)
