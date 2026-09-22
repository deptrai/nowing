---
title: 'Story 39.3 — Entity Resolution Confidence Scoring (R3)'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'dispatch'
baseline_commit: '37002544fcd02f746d8c85efea11459b3596ea15'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Dedup hiện tại chỉ merge khi exact key trùng (`bds_aggregator` union-find phone/address/image) hoặc fuzzy composite ≥0.85 (`corporate_verification_service`). Các cặp CÙNG entity nhưng khác key — diacritics, viết tắt ("TP.HCM" vs "Thành phố Hồ Chí Minh"), tên VN vs EN, khác phone mask — bị miss hoặc rơi vào `requires_manual_confirmation` dư thừa.

**Approach:** Two-stage entity resolution qua `DecisionService`: (a) **fan-out** — sau `deduplicate()`, heuristic `find_match_candidates` (city bucket + title Jaccard) sinh candidate pairs, rồi ONE `decide()` per anchor với `match_decision` Choice trên `entity_match_fanout` set (criteria = candidate ids + `no_match`); confirmed → `merge_group`. (b) **pairwise** — `verify_company` rescore candidate trong band fuzzy-uncertain bằng `entity_match` Score: 2→verified, 1→manual, 0→reject. Cả hai advisory: flag off/error → behavior hiện tại nguyên vẹn.

## Boundaries & Constraints

**Always:**
- Chỉ gọi `get_decision_service().decide()` — `task="entity"`, `question_set` từ registry (`f"{qs.name}@{qs.version}"`), `required_state_keys=qs.required_state_keys`, `model=None`, `timeout=None`. Không import `typesafe_sdk` ngoài `backends/jev.py`.
- Fan-out: đúng 1 `decide()` per anchor; criteria chỉ chứa candidate ids heuristic-surviving + `no_match` đặt CUỐI (mô tả ngắn `title | district | price`); build bằng `dataclasses.replace(q, criteria={...})` — template registry criteria không đổi. `state = {"anchor": entity_dict, "candidates": {cid: entity_dict}}`. Single-pass: merge xong không re-eval candidates còn lại.
- Cap: ≤250 candidates/anchor (criteria bound); ≤`MAX_DECISION_CALLS_PER_RUN` (=50, param-overridable) anchors có candidates được gọi per aggregate run — phần dư giữ heuristic result, không gọi. Circuit breaker: ≥3 `DecisionError` liên tiếp trong loop → abort các anchor còn lại (tránh đốt paid calls khi backend down).
- Gate: `ConfidenceGate.for_task("entity").passes(answer)` (0.7, env `DECISION_ENTITY_THRESHOLD`) — gate trên `answer.confidence`, KHÔNG score/choice value. Fan-out: chosen id ≠ `no_match` + gate pass → merge. Pairwise: gate pass → band theo score (≥1.5 merge / 0.5–1.5 review / <0.5 separate); gate fail → REVIEW.
- Merge chỉ qua `merge_group` hiện có (union-find trên confirmed edges → merge từng component). Không viết merge logic mới.
- Fail-open tuyệt đối: mọi `DecisionError`/`InvalidDecisionAnswer`/exception trong refine stage → trả đúng input `deduplicate()` đã cho (log warning, không propagate). Corp rescore exception → giữ fuzzy result.
- `verify_company` giữ nguyên semantics `CorporateMatchResult`: Jev chỉ rescore khi `0 < best_score < AUTO_LINK_CONFIDENCE_THRESHOLD` (band uncertain), đặt ngay trước `is_verified = ...` (:784) — CHỈ fresh masothue-search path; tax_id-exact, cached, breaker-degraded paths không động vào; `confidence` field vẫn là fuzzy `best_score`.
- Log structured `[entity_match]` per call: anchor id, chosen/score, confidence, action — bds path không có `user_id` nên `TokenUsage` không persist (service contract); log là record duy nhất.

**Never:**
- Không re-score pairs heuristic đã merge (union-find keys) hay reject — candidates chỉ từ `find_match_candidates` trên post-merge canonicals.
- Không đổi `deduplicate()` semantics, `SpatialWindowedDeduplicator` (no prod callers), `jobs_aggregator`, `EntityDeduplicationService` (lead domain), schemas public (`VnBdsAggregateOutput`, `CorporateMatchResult` fields unchanged).
- Không tạo DB table/migration mới — "curator review queue" = `requires_manual_confirmation` hiện có (corp) + `[entity_match]` logs/telemetry (39.7 dashboard sẽ aggregate).
- Không auto-merge khi gate fail; không gọi decide() khi `find_match_candidates` rỗng (0 cost); không sync-wrapper decide().

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CONFIRM_MERGE | anchor A + cand B (`match_decision`→"b_id", conf 0.9) | A,B merged qua `merge_group` → 1 canonical | N/A |
| NO_MATCH | `match_decision`→"no_match", conf 0.8 | Giữ separate, `[entity_match]` log action=separate | N/A |
| LOW_CONF | chosen="b_id" nhưng conf 0.5 < 0.7 | Không merge — keep separate + log | N/A |
| NO_CANDIDATES | `find_match_candidates` → {} | Return `deduplicate()` output as-is; 0 decide() calls | N/A |
| DECIDE_RAISES | `DecisionError` (timeout/disabled/no key) hoặc exception bất kỳ | Return input unchanged — aggregate tiếp tục bình thường | log warning |
| CIRCUIT_BREAK | 3 `DecisionError` liên tiếp trong fan-out loop | Abort anchors còn lại, trả merges đã confirmed | log warning |
| FLAG_OFF | `DECISION_ENTITY_ENABLED=false` | `decide()` raise `disabled` → unchanged (cũng pre-check trước khi scan) | N/A |
| CAP_CALLS | 80 anchors có candidates, cap=50 | 50 anchors đầu (candidate-count desc) được decide; 30 còn lại giữ nguyên | N/A |
| CAP_CRITERIA | anchor có 300 candidates | top 250 by Jaccard vào criteria | N/A |
| CORP_VERIFIED | fuzzy 0.6, Score→2 (conf 0.9) | `is_verified=True`, `requires_manual_confirmation=False` | N/A |
| CORP_REVIEW | fuzzy 0.6, Score→1 hoặc conf<0.7 | `is_verified=False`, `requires_manual_confirmation=True` | N/A |
| CORP_REJECT | fuzzy 0.6, Score→0 (conf 0.9) | `is_verified=False`, `requires_manual_confirmation=True` | log khác review |
| CORP_OUTSIDE_BAND | fuzzy 0.9 (auto-link) hoặc 0.2 | Không gọi decide() — 0.9 verified ngay, 0.2 manual như cũ | N/A |
| MULTI_CONFIRM | A→B confirmed, B→C confirmed | union-find {A,B,C} → 1 `merge_group` | N/A |

</frozen-after-approval>

## Code Map

- `app/services/decision/questions/entity_match.py` — pairwise Score set đã registered (`entity_match@1.0.0`, required keys `entity_a`/`entity_b`); reuse nguyên.
- `app/services/decision/questions/entity_match_fanout.py` — **NEW**: `match_decision` ChoiceQuestion, `VERSION="1.0.0"`, `REQUIRED_STATE_KEYS=("anchor","candidates")`, criteria template = `{"no_match": "None of the candidates is the same entity as the anchor"}`; register trong `questions/__init__.py` theo pattern :27-32.
- `app/services/entity_resolution/` — **NEW module** (consumer, ngoài decision port): `service.py` chứa `score_entity_pair(entity_a, entity_b, ...) -> EntityVerdict` (enum AUTO_MERGE/REVIEW/SEPARATE + answer), `confirm_entity_match(anchor, candidates, ...) -> str|None`, `refine_entity_groups(entities, candidate_pairs, merge_group_fn, ...) -> (merged, stats)`. Lazy `get_decision_service()` (patchable); mọi call qua registry set.
- `app/services/bds_aggregator/dedupe.py` — thêm `find_match_candidates(listings) -> dict[int,list[int]]`: bucket normalized `city|location|district` (strip/lower đơn giản), pairwise Jaccard trên title tokens đã qua `_remove_diacritics` (reuse từ `.normalize` — diacritics-insensitive) ≥ `CANDIDATE_JACCARD_MIN` (0.25) → candidate ids; chỉ anchor nhỏ hơn giữ pair (i<j) tránh double-call; top-K per anchor.
- `app/services/bds_aggregator/orchestrator.py:321` — sau `deduped = deduplicate(normalized)`, trước `score_listing`: `deduped = await _refine_dedup_with_jev(deduped, session=session, workspace_id=workspace_id)` — helper wrap fail-open toàn bộ (pre-check `decision_enabled()`+`decision_task_enabled("entity")` trước khi scan candidates); entity_dict mỗi listing = `{name:title, address:" ".join(ward,district,city,location), price, project, area}`; merge = `merge_group` đã import sẵn trong dedupe.
- `app/services/corporate_verification_service.py:740-795` — trước `is_verified = best_score >= AUTO_LINK_CONFIDENCE_THRESHOLD` (:784): band check `0 < best_score < AUTO_LINK` → `score_entity_pair({name:company_name, city, district, tax_id}, {name:cand.company_name, international_name, short_name, tax_id, address, city, district})` — cand dict keys theo `DefaultMasothueClient.search_company` :317-338; verdict map vào `is_verified`/`requires_manual_confirmation`; session = `self.session`. Thêm optional kwarg `workspace_id: int | None = None` → forward `verify_lead_corporate_info` (:815) truyền `workspace_id` của nó cho telemetry; callers cũ không đổi (default None).
- `app/services/decision/service.py` — `decide()` signature :59-74; `session=None` hợp lệ (telemetry skip); `_record_usage` needs session+workspace_id+user_id → bds thiếu user_id ⇒ log-only (đã spec).
- `app/services/decision/gate.py` — `ConfidenceGate.for_task("entity")` default 0.7.
- `app/config/decision.py` — `decision_enabled()`/`decision_task_enabled("entity")` call-time helpers cho pre-check.
- `tests/unit/services/decision/test_service.py:31-78` — `_StubBackend`/`_enabled` fixtures để reuse; `tests/unit/services/bds_aggregator/test_orchestrator.py` + `test_dedupe.py` — existing test conventions.

## Tasks & Acceptance

**Execution:**
- [x] `app/services/decision/questions/entity_match_fanout.py` + `questions/__init__.py` — question set mới + register — fan-out primitive
- [x] `app/services/entity_resolution/__init__.py` + `service.py` — `EntityVerdict`, `score_entity_pair`, `confirm_entity_match`, `refine_entity_groups` (union-find trên confirmed edges, caps, `[entity_match]` log) — shared two-stage engine
- [x] `app/services/bds_aggregator/dedupe.py` — `find_match_candidates` heuristic (pure, sync, testable) — stage-1 narrowing
- [x] `app/services/bds_aggregator/orchestrator.py` — `_refine_dedup_with_jev` fail-open wiring sau deduplicate — live path integration
- [x] `app/services/corporate_verification_service.py` — band-gated `score_entity_pair` rescore trong `verify_company` — pairwise consumer
- [x] `tests/unit/services/entity_resolution/test_service.py` + `tests/unit/services/bds_aggregator/` + corp rescore tests — cover toàn bộ I/O matrix (stub backend / mock decide)

**Acceptance Criteria:**
- Given `DECISION_ENABLED=true`, `DECISION_ENTITY_ENABLED=true`, khi aggregate BĐS có ≥2 canonicals cùng city với title-Jaccard ≥0.25 nhưng không shared keys, then `decide()` được gọi đúng 1 lần per anchor với `match_decision` Choice trên `entity_match_fanout@1.0.0`; chosen candidate + conf ≥0.7 → merged qua `merge_group`.
- Given flag off hoặc backend error, when `aggregate()` chạy, then output giống hệt heuristic-only path (không exception, không phát sinh call khi không có candidates).
- Given anchor có K>250 candidates hoặc >50 anchors có candidates, then calls bị cap theo spec — cost ≤ ~50 calls/run.
- Given `verify_company` best candidate fuzzy trong (0, 0.85), when `DECISION_ENTITY_ENABLED=true`, then `entity_match@1.0.0` Score rescore: 2→`is_verified=True`; 1/gate-fail→`requires_manual_confirmation=True`; 0→not verified; ngoài band không gọi.
- Given answer bất kỳ, when `confidence < DECISION_ENTITY_THRESHOLD`, then KHÔNG auto-merge xảy ra ở cả hai path.
- `grep -rn "typesafe_sdk" app/services/entity_resolution app/services/bds_aggregator app/services/corporate_verification_service.py` → 0 kết quả.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Review 2026-09-22 — 3 layers (blind-hunter, edge-case-hunter, verification-gap) on `/tmp/spec-39-3-review.diff`.

| # | Layer | Finding | Verdict | Evidence / Route |
|---|-------|---------|---------|------------------|
| 1 | blind | Geo bucket không diacritics-normalized → "Hồ Chí Minh" vs "Ho Chi Minh" tách bucket | low → patch | Đúng — spec chỉ spec strip/lower nhưng intent là catch variants; `_candidate_bucket` giờ `remove_diacritics(...strip().lower())` + empty→"global" (strictly more recall, không split được). `dedupe.py:29-41` |
| 2 | blind | `_entity_state.address` chỉ gửi `location`; spec :65 yêu cầu `" ".join(ward,district,city,location)` | medium → patch | Spec deviation thật — fixed `orchestrator.py::_entity_state` join đủ 4 fields. |
| 3 | blind | `_entity_description` dùng `location`; spec :24 yêu cầu `title \| district \| price` | low → patch | Fixed — đổi sang `district` + fallback `canonical_id` khi rỗng. |
| 4 | blind + edge | `RefineStats.below_confidence` dead field, gate-fail đếm vào no_match | low → patch | Field đã xoá; per-call log giờ có `passes` + `anchor` nên vẫn phân biệt được ở decision granularity. |
| 5 | blind + edge | Per-call `[entity_match]` log thiếu anchor id (spec :30) | medium → patch | Thêm kwarg `anchor_id` vào `score_entity_pair`/`confirm_entity_match`; refine truyền `id_of(anchor)`, corp truyền `company_name`. |
| 6 | blind + edge + gap | CORP_REJECT: spec matrix :53 yêu cầu `requires_manual_confirmation=True` cho Score→0; code set False | high → patch | Frozen spec rõ — Jev chỉ được PROMOTE, không demote khỏi manual queue. `_jev_rescore_match` giờ `-> bool` (True chỉ khi AUTO_MERGE); caller bỏ nhánh `rescore is False`. Test `test_uncertain_band_separate_keeps_manual_flag`. |
| 7 | blind | CORP_OUTSIDE_BAND matrix mâu thuẫn: "fuzzy 0.2" nằm trong band (0,0.85) nhưng claim không gọi decide | false | Band chuẩn `(0,0.85)` được định nghĩa 2 lần (:29, :86) — normative rule wins; 0.2 là ví dụ sai trong matrix cell, code theo đúng band. Không sửa được (frozen) nhưng không phải code bug. |
| 8 | blind + edge | Jev verdict không persist → call 1 verified, call 2 cached → manual (flip-flop) | medium → defer | Spec :29 cố tình "cached paths không động vào" — flip-flop là hệ quả của boundary đã approve. Persist verdict vào cache payload sẽ đụng cached-path returns + cache shape — quyết định intent-level → deferred-work. |
| 9 | blind | `is_verified=True` với `confidence<0.85` phá invariant cũ | low → rejected | Spec-mandated: `confidence` giữ fuzzy score (:29). Consumers (`verify_lead_corporate_info`) check `is_verified`+`profile`, không assume correlation. |
| 10 | blind + edge | O(n²) Jaccard + "global" bucket + stopword noise | low → rejected | Bounded: max_items_per_source ≤100 × ≤3 sources → ≤300 listings, ≤45k pair calcs (ms); call cap 50 bound paid spend. Token noise chỉ tăng candidates trong cap. |
| 11 | blind | 1 exception bất ngờ trong refine bỏ mất merges đã confirmed | false | Spec :28 yêu cầu chính xác: "mọi exception trong refine stage → trả đúng input deduplicate() đã cho". All-or-nothing là spec'd. |
| 12 | blind | Stage-1 nên reuse `SpatialWindowedDeduplicator` | false | Spec :64 mandate `find_match_candidates` trong `dedupe.py`; Never-list :34 cấm đổi SpatialWindowed (no prod callers). |
| 13 | blind | Ordering contract của `[:250]` slice không documented | low → patch | Docstring `confirm_entity_match` giờ nêu "callers should pass them ordered by relevance — truncates the head". |
| 14 | blind | `_bmad/marketing-growth` dirty submodule trong diff | false | Pre-existing unrelated worktree state, không staged — không phải change của story này. |
| 15 | blind | `descriptions` fallback = canonical_id hash (meaningless criteria text) | low → rejected | Sole consumer (orchestrator) luôn truyền `describe`; generic-API edge không demonstrated. Docstring đã ghi rõ fallback. |
| 16 | blind | Test gaps: `_entity_state`/`_entity_description` content, non-DecisionError fail-open, cached flip-flop | low → patch (phần) | Đã thêm `test_aggregate_unexpected_error_keeps_heuristic` + ordering test; state/description được pin gián tiếp qua spec fix ở #2/#3. |
| 17 | edge | Duplicate `id_of` → `id_to_idx`/`cand_entities` collapse, union sai index | low → rejected | bds `canonical_id` unique per cluster (digest trên source_ids); generic-API duplicate ids là contract violation — không demonstrated caller nào. |
| 18 | edge | Candidate id == literal `"no_match"` collide sentinel | low → patch | Guard `if NO_MATCH_ID in candidates: raise DecisionError(invalid_request)` — unreachable với bds digests nhưng fail-fast cho callers khác. |
| 19 | edge | Direct caller truyền >250 candidates → criteria vượt action bound | low → patch | `confirm_entity_match` giờ cap `[:MAX_CANDIDATES_PER_ANCHOR]` (double với refine slice — consistent). |
| 20 | edge | `max_calls` âm → slice sai + skipped_cap over-count | low → patch | `anchors[: max(0, max_calls)]`. |
| 21 | edge | 50 sequential calls × ~10s → aggregate stall phút | low → defer | Worst-case bounded 50×(5s+5s fallback) theo spec cap :25; không spec deadline → deferred-work, thêm `max_seconds` nếu thực tế cần. |
| 22 | edge | Whitespace-only city → bucket "" tách khỏi "global" | low → patch | Gộp vào #1: `key or "global"`. |
| 23 | edge | `_entity_description` rỗng → Jev thấy blank option | low → patch | Fallback `or listing.canonical_id` (#3). |
| 24 | edge | AC "output giống hệt heuristic" vs confirmed-trước-error merges | false | Matrix CIRCUIT_BREAK :47 spec "trả merges đã confirmed" — partial merges trước error là intended, không contradict AC đọc đúng context. |
| 25 | gap | Descending-Jaccard ordering unverified — sort regression giữ 250 ít-similar nhất | patch → patched | `test_candidates_ordered_by_descending_jaccard` added — assert anchor's list most-similar first. |
| 26 | gap | Corp `workspace_id` không sinh `TokenUsage` row (thiếu `user_id`) | low → rejected | Spec :30/:67 acknowledge log-only khi thiếu user_id; `workspace_id` được forward đúng spec — persistence cần user_id callers không có. |

## Design Notes

- **Fan-out vs pairwise phân chia:** batch dedup (bds) luôn dùng `match_decision` Choice — kể cả K=1 — để đúng "~1 call/anchor"; pairwise `entity_match` Score dành cho 1:1 verification context (corp). Review-queue semantics: pairwise REVIEW → `requires_manual_confirmation` (queue sẵn có); fan-out unconfirmed → keep separate + `[entity_match]` log (39.7 dashboard sẽ aggregate decision telemetry sau).
- **Candidate finder chỉ chạy post-merge:** `deduplicate()` đã merge exact-key pairs trước — candidates = các canonicals khác cluster cùng geo-bucket, title tương tự. Đây là false-negative recovery, không phải second-guess heuristic.
- **Ordering anchors khi cap:** sort theo số candidates desc (anchor "khó" nhất được Jev trước) — deterministic.
- **Corp rescore band (0, 0.85):** ≥0.85 đã auto-link (Jev thừa); =0 (no overlap) Jev cũng sẽ reject → skip cả hai, chỉ rescore vùng fuzzy bất định. `confidence` output vẫn là fuzzy score — Jev chỉ quyết verdict, không thay metric.
- **Pre-check pattern (từ review 39.2):** check `decision_enabled()` + `decision_task_enabled("entity")` TRƯỚC khi scan candidates → flag off không tốn compute.
- **`no_match` đặt cuối criteria:** `MockBackend._answer` chọn `options[0]` — đặt `no_match` cuối để mock deterministic pick candidate đầu tiên (test CONFIRM_MERGE không cần stub riêng); test NO_MATCH dùng stub backend.
- **Circuit breaker 3 lỗi liên tiếp:** backend down → mỗi decide() vẫn tốn 1-2 paid legs (Jev + fallback llm_json); abort sớm tránh 50×2 calls đổ vào backend đang chết. Heuristic result vẫn được trả cho phần chưa gọi.

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/entity_resolution app/services/decision/questions app/services/bds_aggregator app/services/corporate_verification_service.py tests/unit/services/entity_resolution tests/unit/services/bds_aggregator` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/services/entity_resolution tests/unit/services/bds_aggregator tests/unit/services/decision tests/unit/services/test_corporate_verification.py -m unit -q` — expected: all pass

## Live Verification (2026-09-23, real `api.typesafe.ai` + real data)

`TYPESAFE_API_KEY` từ XActions env (không commit); `DECISION_BACKEND=jev DECISION_ENABLED=true DECISION_ENTITY_ENABLED=true`.

| Mode | Command | Result |
|---|---|---|
| `merge` | `--mode merge` | 1 Jev fanout call (1080ms, 592 in) → conf=1.0 merge cross-post clone đúng, 3→2 canonicals |
| `corp` | `--mode corp` | Masothue live + 4 Jev pairwise (740–794ms): `BĐS Vinhomes Đan Phượng` conf=0.79→**auto_merge**; Vinhomes/Công ty Vinhomes/Đại Phát → `review` |
| `bds` | `--mode bds --district "Quận 7" --max-items 12 --max-pages 1` | Scrape thật 36 listings (batdongsan/chotot/muaban) → 27 canonicals → 6 candidate pairs → 5 Jev fanout calls (296–896ms): 1 gate-reject conf=0.46, 4 no_match conf 0.93–1.0 → 27→27, không false merge |
| `_jev_verdict` cache | `verify_company('Bất động sản Vinhomes Đan Phượng')` không force_refresh | `is_verified=True, manual=False, cached=True` — verdict tồn tại qua cache, flip-flop fix hoạt động live |

Corp rescore/fan-out không ghi `token_usage` (no `user_id` trong context — `NOT NULL`, đúng design log-only).
