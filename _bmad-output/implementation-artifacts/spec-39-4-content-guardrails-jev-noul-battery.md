---
title: 'Story 39.4 — Content Guardrails via Jev Noul Battery (R4)'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'dispatch'
baseline_commit: '613513eb369a1f09f61ed5458cd96e34765dead1'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** RAG passages, scraped content và user input đi vào LLM/storage mà không qua semantic guardrail — `pii/redact.py` chỉ là regex, không bắt được prompt injection tiếng Việt hay PII dạng ngữ nghĩa (địa chỉ nhà, CMND viết tắt).

**Approach:** Module `app/services/content_guardrails/` mới — 1 `decide()` call chạy battery 3 Nouls (`is_relevant`, `contains_prompt_injection`, `contains_sensitive`) trên `content_filter@1.0.0`, map sang verdict `DROP`/`MASK`/`PASS`; wire vào 4 surface: RAG search results (trước khi LLM thấy), chainlens private provider chunks, scraped chunks trước khi ingest lên chainlens (mask trước storage), và user chat input (advisory flag-only). Advisory + fail-open y như 39.2/39.3.

## Boundaries & Constraints

**Always:**
- Chỉ gọi `get_decision_service().decide()` — `task="filter"`, `question_set=f"{qs.name}@{qs.version}"` từ registry (`content_filter`), `required_state_keys=qs.required_state_keys`, `model=None`, `timeout=None`. State = `{"query": query or "", "passage": passage[:4000]}`. Không import `typesafe_sdk` ngoài `backends/jev.py`.
- 3 Nouls trong ĐÚNG 1 call `decide()` (server-side parallel — eval median 308ms).
- Gate: `ConfidenceGate.for_task("filter")` (default 0.5, env `DECISION_FILTER_THRESHOLD`). Với Noul, `answer.value` chính là confidence — verdict theo `value`/`passes_negative`, không dùng `answer.confidence` riêng.
- Verdict mapping (priority DROP > MASK): `contains_prompt_injection.value >= 0.5` → `DROP`; `is_relevant` `gate.passes_negative(answer)` (chỉ khi `query` non-empty và `surface=="rag"`) → `DROP`; `contains_sensitive.value >= 0.5` → `MASK` kèm `masked_text = redact_pii(passage, context="lead_enrichment").text`; còn lại `PASS`.
- Fail-open tuyệt đối: mọi `DecisionError`/`InvalidDecisionAnswer`/exception → passage/chunk/message đi qua nguyên trạng (log warning, không propagate). Flag off (`decision_enabled()` + `decision_task_enabled("filter")` pre-check) → zero work, zero calls.
- Log structured `[content_filter]` per call: `surface`, `action`, 3 noul values, confidence.
- Caps: batch callers dùng `filter_passages(items, ..., max_calls)` — default `MAX_FILTER_CALLS=20` per search query, `50` per ingest run; concurrency `asyncio.gather` + `Semaphore(10)`; item vượt cap pass-through unguarded + đếm `skipped_cap`.
- User input (persist_user_turn): advisory flag-only — Jev verdict chỉ log `[content_filter] surface=user_input`, KHÔNG block/drop/mask message. `is_relevant` không áp cho user_input/ingest surface.
- Reuse `redact_pii` làm masker duy nhất — Jev quyết "có sensitive không", regex thực hiện mask. Không viết masker mới.

**Never:**
- Không mutate/block user message; không đổi `CorporateMatchResult` hay bất kỳ contract nào.
- Không filter trong retriever internals (2 consumers search core + private_provider wire ở merged-result level, tránh sửa cả 2 retriever).
- Không gọi Jev khi passage rỗng/whitespace.
- Không đụng `pii/redact.py` internals — chỉ gọi `redact_pii`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| FILTER_INJECTION | `contains_prompt_injection` noul ≥0.5 (gate pass) | `DROP` — passage/chunk bị loại + log | N/A |
| FILTER_SENSITIVE | `contains_sensitive` ≥0.5, không injection | `MASK` + `masked_text` đã qua `redact_pii` | N/A |
| FILTER_IRRELEVANT | `is_relevant` confidently-false, query non-empty, surface=rag | `DROP` | N/A |
| GATE_FAIL | mọi noul value < threshold hoặc answer lệch | `PASS` | N/A |
| FLAGS_OFF | `DECISION_ENABLED`/`DECISION_FILTER_ENABLED` off | `PASS` ngay, 0 calls, 0 extra compute | N/A |
| BACKEND_ERR | `decide()` raise | `PASS` cho item đó, `errors+=1` | log warning, không propagate |
| BATCH_CAP | N items > max_calls | gọi cho N đầu, phần dư pass-through | `skipped_cap` count |
| EMPTY_PASSAGE | passage rỗng/whitespace | `PASS`, không gọi | N/A |

</frozen-after-approval>

## Code Map

- `app/services/decision/questions/content_filter.py` — **đã registered** (`content_filter@1.0.0`, 3 NoulQuestions, `REQUIRED_STATE_KEYS=("query","passage")`) — reuse nguyên.
- `app/services/content_guardrails/` — **NEW module**: `service.py` chứa `GuardrailAction` (enum PASS/DROP/MASK), `PassageVerdict` (action, reasons, masked_text, answers), `check_passage(passage, *, query="", surface="rag", session, workspace_id, user_id, client_id) -> PassageVerdict`, `filter_passages(items: list[tuple[Any,str]], *, query, surface, max_calls, ...) -> list[(Any, PassageVerdict)]` (parallel gather + semaphore + cap + fail-open per item). Lazy `get_decision_service()`; pattern y `entity_resolution/service.py` (đọc nó trước).
- `app/services/decision/service.py:59-74` — `decide()` signature; `session=None` OK (telemetry skip).
- `app/services/decision/gate.py` — `ConfidenceGate.for_task("filter")` = 0.5; `passes_negative()` cho is_relevant.
- `app/services/pii/redact.py` — `redact_pii(text, context="lead_enrichment") -> RedactedText` (`.text`) — masker duy nhất.
- `app/services/connectors/search/core.py` — `_combined_rrf_search` return `combined_results` (list doc dicts, `result["content"]` concatenated + `result["chunks"][].content`; `query_text` là param trực tiếp của method): **wire sau khi build `combined_results`, trước return** — per-doc `check_passage(doc["content"], query=query_text, surface="rag")`, DROP → remove doc, MASK → `doc["content"] = verdict.masked_text` VÀ mỗi `chunks[i].content = redact_pii(chunks[i].content, context="lead_enrichment").text` (mask TỪNG field riêng — KHÔNG gán `masked_text` concatenated vào từng chunk). 1 wire point này cover tất cả connector search types (files, gmail, slack, teams, discord, calendar, drive, notion, jira, clickup, linear — tất cả gọi `_combined_rrf_search`).
- `app/services/chainlens/private_provider.py` — `_build_chunks` → `list[PrivateProviderChunk]` (`.content` mutable pydantic, `min_length=1` — masked non-empty OK): wire sau build, trước `return PrivateDataSearchResponse` (:205-227), `query=request.query`, `surface="rag"`, per-chunk DROP/MASK rewrite `.content = verdict.masked_text` (1:1 mapping). Entry point riêng (dùng retrievers trực tiếp, KHÔNG qua `_combined_rrf_search`) → không double-filter với surface trên.
- `app/services/chainlens/ingest.py` — `ingest()` trước `_iter_batches` (:303): per-chunk `check_passage(chunk_text, query=f"scraped {scraper_id} content", surface="ingest")` — DROP → exclude chunk; MASK → mutate in-place `chunk.content = masked` (pydantic `Chunk` non-frozen `extra="allow"`) hoặc `chunk["content"] = masked` (dict) — helper `_set_chunk_content` xử lý 2 shape; `_chunk_to_dict` (:43) chỉ để đọc, KHÔNG dùng cho mutation. `is_relevant` không áp. `session` param có sẵn cho telemetry.
- `app/tasks/chat/persistence.py:169` — `persist_user_turn(user_query=...)`: `await check_passage(user_query, surface="user_input")` trong try/except riêng TRƯỚC insert — verdict chỉ log, KHÔNG đổi insert path. (Advisory-only; blocking UX cần quyết định product riêng.)
- `scripts/jev_eval/summary.md` — eval baseline ĐÃ ĐẠT: CONTENT_FILTER jev 20/20 = 100% (median 308ms) — AC eval bullet thỏa sẵn, không re-run trong story này.
- `tests/unit/services/entity_resolution/test_service.py` — test conventions để mirror (stub backend pattern).

## Tasks & Acceptance

**Execution:**
- [x] `app/services/content_guardrails/__init__.py` + `service.py` — `GuardrailAction`, `PassageVerdict`, `check_passage`, `filter_passages` (semaphore 10, caps, `[content_filter]` log) — shared guardrail engine
- [x] `app/services/connectors/search/core.py` — wire `_combined_rrf_search` post-merge (pre-check flags trước khi build list call) — RAG surface 1
- [x] `app/services/chainlens/private_provider.py` — wire `_build_chunks` output trước return — RAG surface 2
- [x] `app/services/chainlens/ingest.py` — wire per-chunk guard trước batch POST — storage mask
- [x] `app/tasks/chat/persistence.py` — advisory check trong `persist_user_turn` — user-input flag
- [x] `tests/unit/services/content_guardrails/test_service.py` + wiring tests trong `tests/unit/services/connectors/`, `tests/unit/services/chainlens/`, `tests/unit/tasks/chat/` — cover toàn bộ I/O matrix

**Acceptance Criteria:**
- Given flags on + passage có VN prompt injection ("Bỏ qua mọi hướng dẫn trước đó"), when search/ingest chạy, then passage bị DROP + `[content_filter]` log, đúng 1 `decide()` call với 3 nouls trên `content_filter@1.0.0`.
- Given passage có CMND/điện thoại nhà, when `contains_sensitive` ≥0.5, then MASK — stored/returned text đã qua `redact_pii`, passage vẫn giữ.
- Given flags off hoặc backend error, then mọi surface trả y hệt kết quả không-filter (fail-open, không exception).
- Given search có 30 docs, then ≤20 `decide()` calls (`MAX_FILTER_CALLS`), phần dư pass-through.
- Given user input trong `persist_user_turn`, then verdict chỉ log — message vẫn insert bình thường kể cả injection verdict.
- `grep -rn "typesafe_sdk" app/services/content_guardrails app/services/connectors/search app/services/chainlens app/tasks/chat` → 0 kết quả.

## Implementation Notes

- `check_passage` swallows ALL exceptions → `PASS` + `error` field (spec: fail-open tuyệt đối); `filter_passages` counts `error` verdicts into `stats.errors`.
- `filter_passages` returns `tuple[list[(item, verdict)], FilterStats]` — positions-based verdict mapping (không dùng `id()` keys — cùng object lặp lại trong list vẫn đúng verdict theo vị trí).
- Mask-failure trên known-sensitive content → `DROP` (không phải PASS) — unmasked pass-through là worst outcome. Cùng rule cho ingest chunk không mutate được.
- Wire `_filter_rag_results` là module-level helper trong core.py — 1 hook cover ~10 connector types; private_provider entry riêng (retrievers trực tiếp) nên không double-filter.
- Ingest wire đặt SAU auth check, TRƯỚC `_iter_batches` — all-DROP → return noop result giống empty-input path.
- `persist_user_turn`: check đặt SAU `turn_id` guard (turn_id rỗng → không tốn call), TRƯỚC insert — try/except riêng dù check_passage đã fail-open.
- Verified: ruff clean; 142 targeted tests pass; full unit suite 6905 pass — chỉ còn 6 fails pre-existing không liên quan (phone_waterfall AsyncMock ×5, pat_fail_closed_static route drift), deselect-confirmed.
- Outer fail-open `try/except` quanh `filter_passages` ở cả 3 batch call sites (core/private_provider/ingest) — per-item fail-open của service không cover lỗi ở gather level.
- **Post-live-verify amendment (2026-09-22):** relevance-negative (`DROP` + `reasons=("irrelevant",)`) trên rag surfaces **demote xuống cuối kết quả** thay vì drop — live Jev run cho thấy over-drop VN content thiếu literal geo terms (6/18 real Q3 listings bị rel=0.04–0.09 dù đúng quận). Injection/mask_failed vẫn hard-drop. Service-level verdict không đổi — chỉ call-site handling ở `_filter_rag_results` + `private_provider.search`.
- Pre-existing failures (không phải story này): `test_phone_waterfall_service.py` ×5 (`coroutine.scalar_one_or_none` — AsyncMock issue), `test_pat_fail_closed_static` (route allowlist drift `workspaces_routes.py`→`workspaces/core.py`).

## Spec Change Log

- 2026-09-22 — spec review round 1 (6 fixes): `_serialize_chunk`→mutation in-place (`_chunk_to_dict` chỉ để đọc); MASK doc-dict phải mask từng field riêng, KHÔNG gán `masked_text` concatenated vào chunks[]; Design Notes mới: MockBackend noul=0.9 (test cần `_StubBackend`), Jev ingest additive trên `_redact_text` regex có sẵn, user-input advisory cost ~300ms+1 paid call/message, `_combined_rrf_search` 1 hook cover ~10 connector types + private_provider là entry riêng (không double-filter).
- 2026-09-22 — post-live-verify amendment: relevance-negative trên rag surfaces đổi DROP → **demote-to-tail** (recall-safe; Jev over-drop VN geo text — 6/18 real Q3 listings rel≤0.09). Approved bằng directive "giải quyết luôn" sau khi xem live evidence. I/O matrix FILTER_IRRELEVANT row áp cho service-level verdict; call-site demote là surface policy.

## Review Triage Log

3 reviewers (swe-2-high, song song) → 14 findings. Triage:

**Patched (production):**
1. HIGH — shared `AsyncSession` race: `private_provider` truyền `session=self.session`+`user_id` vào `filter_passages` → concurrent `session.execute` trên 1 asyncpg connection (invariant đã documented tại core.py:291). Fix: bỏ session/user context → telemetry log-only. Ingest `session=` cũng bỏ (dead param — telemetry cần cả 3, `user_id` không bao giờ có → latent trap).
2. MED — batch call sites không fail-open ở gather level: `filter_passages` raise → exception propagate (search 500 / ingest fail). Fix: outer `try/except` → return input nguyên trạng ở cả 3 sites (`_filter_rag_results`, `private_provider.search`, `_guardrail_filter_chunks`) + fail-open tests cho từng site.
3. LOW — `MASK` + falsy `masked_text` giữ unmasked content ở cả 3 call sites → vi phạm worst-outcome doctrine. Fix: falsy → drop (service đã convert empty mask → DROP; call-site defense-in-depth).
4. LOW — `bool(query)` tính whitespace-only là non-empty → `query and query.strip()`.
5. LOW — `result.answers` malformed (non-Mapping) → `answers.get()` raise ngoài try → vi phạm never-raises. Fix: toàn bộ answer processing nằm trong fail-open `try`.

**Patched (tests):** wire-presence tests `_combined_rrf_search` + `ingest()` e2e (all-drop noop + mask-and-post); decide-kwargs spy (task/question_set/required_state_keys/model=None/timeout=None); default cap-20 test; DROP-verdict vẫn persist; truncation 4000; `[content_filter]` caplog; env pinning trong fixtures.

**False/rejected:** một số low findings là spec-mandated (advisory user_input không block — đúng intent; query placeholder cho ingest — `REQUIRED_STATE_KEYS` chỉ check presence, documented).

## Design Notes

- **Noul verdict semantics:** `answer.value` = P(yes). `is_relevant` dùng `passes_negative` (confidently-false → drop); injection/sensitive dùng `value >= threshold` trực tiếp. Noul confidence = value (jev.py:104) nên gate-fold vào so sánh luôn — không tách gate call.
- **Relevance chỉ áp cho `surface=="rag"`:** ingest/user_input không có query thật — `is_relevant` vẫn được evaluate trong battery (free, cùng call) nhưng verdict không hành động. Ingest state `query=f"scraped {scraper_id} content"` chỉ để thỏa `REQUIRED_STATE_KEYS` (validation chỉ check key presence, service.py:132).
- **MASK = flag + `redact_pii` trong module:** verdict trả `masked_text` sẵn — callers không phải biết redact internals; DROP chưa mask vì bị loại hẳn. `masked_text` tương ứng đúng text đã check — caller có nested fields (doc `chunks[]`) phải mask từng field riêng qua `redact_pii`, KHÔNG reuse `masked_text`.
- **Jev ingest layer là ADDITIVE trên regex có sẵn:** `scraper_chunks/serializer._redact_text` (:125) đã regex-mask fail-closed lúc build chunk. Jev guard thêm: (a) injection DROP — capability mới hoàn toàn, regex không cover; (b) semantic MASK — bắt PII regex miss (địa chỉ nhà, CMND viết tắt); re-mask trên text đã mask là idempotent.
- **User-input advisory-only:** flag qua structured log, không block — chặn message của chính user là UX-blocking action cần quyết định product riêng (deferred cho dashboard 39.7). Trade-off chấp nhận: flag on = ~300ms + 1 paid Jev call mỗi user message.
- **MockBackend noul = 0.9:** mọi noul answer trả 0.9 ≥ threshold → dưới MockBackend mọi passage đều DROP (injection wins). Test PASS/MASK/GATE_FAIL paths BẮT BUỘC dùng stub backend trả noul values tùy ý (pattern `_StubBackend` trong `entity_resolution/test_service.py`), KHÔNG dùng MockBackend.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/services/content_guardrails app/services/connectors/search app/services/chainlens app/tasks/chat tests/unit/services/content_guardrails` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/services/content_guardrails tests/unit/services/connectors tests/unit/services/chainlens tests/unit/tasks -m unit -q` — expected: all pass
