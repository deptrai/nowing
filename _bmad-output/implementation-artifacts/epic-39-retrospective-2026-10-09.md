---
epic: 39
date: 2026-10-09
verdict: accepted-with-open-items
criteria: declared
headless: false
---

# Epic 39 Retrospective — Typed-Decision Layer (Jev Integration)

## Epic summary

- **Epic:** 39 — Typed-Decision Layer (Jev Integration). Tích hợp TypeSafe Jev (Choice/Score/Noul calibrated probabilities) phục vụ subagent routing, entity resolution, content guardrails, intent classification. Complement cho LLM, không thay thế.
- **Spec:** `_bmad-output/planning-artifacts/epics.md:5317` (Epic 39 + Non-Goals), nguồn research `technical-typesafe-ai-jev-integration-2026-09-21` + architecture spine `architecture-jev-decision-service-2026-09-21/ARCHITECTURE-SPINE.md` (AD-J1..J8).
- **Diff range:** `83e41ad4a..d51120fed` (93c40fbde^..d51120fed) — 27 non-merge commits, 0 merges, 119 app files (~20.7k churn). Story-39.x commits có subject-tag rõ ràng; 1 commit trong range là noise BMAD framework upgrade (8d8829fe7d) + 2 commit Epic 37 lẫn vào (16a8315f94, a418ca371) — đã note, không tính vào epic churn.
- **Stories:** 39.1, 39.1b, 39.2, 39.3, 39.4, 39.5, 39.6, 39.7, 39.8 — 8/8 `done` trong `sprint-status.yaml`, `pending_stories: []` (detect-epic --epic 39).
- **Story files:** `spec-39-{1,1b,2,3,4,5,6,7,8}-*.md` + `epic-39-context.md` trong `_bmad-output/implementation-artifacts/`.

### Evidence inventory

| Artifact | Trạng thái |
|---|---|
| Epic spec (epics.md:5317) | ✅ có, AC khai báo từng story |
| Story spec files (9 files) | ✅ có, kèm live-verify notes |
| Diff range + per-story commits (git_evidence.py) | ✅ `/tmp/ev39.json` |
| Sprint status | ✅ 8/8 done, retro key `epic-39-retrospective: optional` |
| Eval evidence | ✅ `nowing_backend/scripts/jev_eval/summary.md` — 96.3% VN accuracy, 308ms median, $0.0018/80 calls |
| Live verify scripts | ✅ `scripts/verify_entity_resolution_39_3.py`, `scripts/verify_content_guardrails_39_4.py` |
| Previous retro (Epic 38) | ✅ 5 action items open — check follow-through Phase 4 |
| Session logs | ❌ không có bản ghi session — process-lesson analysis bị thu hẹp |

## Findings

### Spec-to-implementation reconciliation (aggregate views)

- **8/8 story AC phản ánh vào code.** Riêng Story 39.6, context phòng thoại trong `VoiceSDRAgent` (`app/services/voice/agent_worker.py:374,946-950`) chưa có producer ngoài thực tế — chờ Story 38.7 Outbound Trigger Engine (`deferred-work.md:1908`, `BLOCKED`).
- **Amendment 39.4 (demote-not-drop)**: relevance-negative RAG demote về đuôi thay vì drop (`app/services/connectors/search/core.py:429-453`, `app/services/chainlens/private_provider.py:241-256`) vì Jev over-drop văn bản VN thiếu từ địa lý trực tiếp — 6/18 tin Q.3 chấm rel ≤0.09 dù đúng quận (`spec-39-4:96-102`). Amendment đúng và đã land.
- **39.5 borderline miss** (`intent_01` "Tìm quán phở ngon" → `recommendation` conf 0.97 vs ground truth `search`): nằm trong baseline 95% eval (`spec-39-5:87`); chấp nhận được, đã ghi nhận.
- **39.7 deferred items đã land**: Celery beat `evaluate_decision_daily_cost_alert` 15 phút (`app/celery_app.py:384`, `tasks/celery_tasks/decision_telemetry_task.py:19`); flag `--persist` ghi eval với `usage_type='decision_eval'` (`scripts/jev_eval/runner.py:751`).

### Duplication & structure

- **Port abstraction 100%**: không import `typesafe` nào ngoài `services/decision/backends/jev.py:126`; bảo đảm bởi `tests/unit/services/decision/test_import_guard.py:18`.
- **`ConfidenceGate` thiếu `passes_positive`** (`app/services/decision/gate.py:79-103`): chỉ có `passes` + `passes_negative`, dẫn tới `_noul_yes` hand-rolled ở `content_guardrails/service.py:99-106`. Disposition: defer.
- **Stub file lạ**: `app/tasks/jev_guardrails.py:45` khởi tạo `_ = DecisionService()` mà không gọi `decide()`, tự so khớp logic riêng, bỏ qua mọi feature flag và telemetry. Disposition: fix-now (xóa hoặc refactor qua service thật).
- **God-class candidate**: `services/decision/service.py` 662 dòng (routing backend + fallback retry + validation + session telemetry); `backends/llm_json.py` 426 dòng. Disposition: defer, cân nhắc tách telemetry/fallback thành module riêng.

### Pattern divergence (AD-J*)

- **(a) TokenUsage ghi nhận**: DB yêu cầu `workspace_id` + `user_id` NOT NULL → các call site thiếu `user_id` rơi về log-only, **không lưu DB**: `connectors/search/core.py:422` (RAG), `chainlens/ingest.py:113` (ingest nền), `bds_aggregator/orchestrator.py:327` (dedup nền), `corporate_verification_service.py:879` (verify công ty), `tasks/jev_guardrails.py:45` (stub không ghi gì). Disposition: fix-now — quyết định schema: cho `user_id` nullable trên usage rows, hoặc service-account user cho background decisions.
- **(b) Feature flags**: mọi call site chính đều check `decision_enabled()` + flag theo task; duy nhất `jev_guardrails.py:45` bỏ qua.
- **(c) Fail-open vs fail-closed**: fail-open đúng chuẩn ở `jev_router.py:223`, `entity_resolution/service.py:126`, `intent_classification/service.py:61`, `voice/semantic_gate.py:141`; fail-closed đúng ở `content_guardrails/service.py:166,177` (injection, mask_failed hard-drop) và `ingest.py:126` (drop chunk khi không redact được). **Ngoại lệ**: Finding P0-2 bên dưới.

### Diff-scope findings (reviewer, 3 lenses)

- **P0-1. Voice decide timeout nuốt transfer-to-human** — `app/services/voice/semantic_gate.py:51,161`: `VOICE_DECIDE_TIMEOUT_SECONDS` mặc định `0.45`s trong khi live verify `d51120fed` ghi batched 3-question call mất 313–765ms (transfer request 765ms); `use_fallback=False` + `except Exception → _FAIL_OPEN` khiến ~30–50% cuộc gọi timeout và nuốt yêu cầu gặp tổng đài viên. Comment code thừa nhận đây là trade-off có chủ đích, nhưng default quá thấp so với số liệu thực. Disposition: **fix-now** — nâng default lên ~0.8s hoặc tách timeout riêng cho nhánh `transfer_to_human`.
- **P0-2. Ingest filter fail-open** — `app/services/chainlens/ingest.py:138-144`: `except Exception: ... return list(chunks)` — khi Jev sự cố/timeout, dữ liệu cào chưa lọt PII/prompt-injection đi thẳng vào DB, vi phạm rule guardrail-fail-closed của epic (injection/mask_failed hard-drop ở mọi surface). Disposition: **fix-now** — ingest surface nhạy cảm cần fail-closed (drop batch nghi vấn hoặc requeue).
- **P1-1. `float()` ép kiểu ở module level** — `semantic_gate.py:51`: env rỗng/sai định dạng crash worker lúc import. Disposition: fix-now (dùng `_env_float` + `math.isfinite`).
- **P1-2. LLMJson backend không strip code fence** — `decision/backends/llm_json.py:413`: `json.loads(content)` trực tiếp; khi litellm hạ cấp `json_object`, Claude/Haiku bọc ```` ```json ```` → `JSONDecodeError` → `InvalidDecisionAnswer` hỏng toàn bộ fallback leg. Disposition: fix-now.
- **P1-3. Dedup key jev_router mỏng** — `agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py:260-264`: `dedup_key = last_human.id or user_text` — khi `id=None`, lặp câu hỏi ngắn trên instance cache bị chặn vĩnh viễn. Disposition: fix-now (thêm `thread_id`+turn index).
- **P1-4. Payload entity resolution phình to** — `entity_resolution/service.py:165-175`: `MAX_CANDIDATES_PER_ANCHOR=250` không cắt trường candidate → payload Jev/LLM hàng trăm KB, rủi ro context window/timeout 5s. Disposition: fix-now (giới hạn trường thiết yếu).
- **P1-5. Eval-gate CI nhắm sai branch** — `.github/workflows/jev-eval-gate.yml:14`: `branches: [main, dev]` trong khi nhánh tích hợp là `develop` → PR vào `develop` không chạy eval gate (Story 39.8). Disposition: fix-now (thêm `develop`).
- **P2-1.** `semantic_gate.py:202-205` `_confidently_no_respond` hardcode `0.8`, bỏ qua `ConfidenceGate.for_task("voice")` → `DECISION_VOICE_THRESHOLD` vô dụng với backchannel suppress. Defer.
- **P2-2.** `connectors/search/core.py:440-447` mutate `doc`/`chunk` in-place; exception giữa chừng trả về results nửa mask nửa không. Defer (clone dict trước).
- **P2-3.** `decision/validation.py:28` `_SUM_TOLERANCE=0.02`, `_SCORE_TOLERANCE=0.05` quá gắt cho fallback leg kém tính toán số thực → `InvalidDecisionAnswer` huỷ oan phản hồi hợp lý. Defer (auto-normalize về 1.0 trước khi validate).
- **P2-4.** `tasks/chat/persistence.py:241-250` guardrail trên user input chỉ log — **accept** (đúng thiết kế advisory ở `spec-39-4:125`).

## Behavior verification

- **Unit tests:** `pytest tests/unit/services/decision tests/unit/services/entity_resolution tests/unit/services/content_guardrails tests/unit/services/connectors tests/unit/services/chainlens tests/unit/tasks/chat -m unit` → **483 passed**, 0 failed, 32 deselected, 22s.
- **Eval evidence** (`scripts/jev_eval/summary.md:3-30`): 80 ca VN — **96.3%** (77/80), median latency **308ms**, **$0.0018/80 calls**. Per-task: SUBAGENT_ROUTING 100%, CONTENT_FILTER 100%, INTENT_CLASSIFY 95% (1 miss borderline), ENTITY_MATCH 90% (2 misses borderline).
- **Live verify scripts**: `verify_entity_resolution_39_3.py` (3 modes, Q.7/Q.9 dedup), `verify_content_guardrails_39_4.py` (battery + real listings + ingest + rag). Commit `6e12c960ea` ghi entity resolution 3 modes + router verified live.
- **Runtime trade-off đã đo**: `d51120fed` env-tunable decide timeout sau calibration live 313–765ms — liên quan trực tiếp P0-1.

## Previous-retro follow-through

Epic 38 retro (2026-10-01) ghi 5 action items; kiểm chứng code hiện tại:

| Item | Trạng thái | Evidence |
|---|---|---|
| AI-38.1 migration `workspace_sip_trunks` (P0) | ❌ chưa land | Model `app/models/workspace_sip.py:21` có `__tablename__`, nhưng **không có alembic migration nào** tạo bảng — `grep -rln "workspace_sip" alembic/versions/` rỗng |
| AI-38.2 Redis consumer `stream:prospect:engagement` (P1) | ❌ chưa land | `app/services/voice/outbound_trigger.py:59` chỉ có handler; không `XGROUP`/consumer loop nào |
| AI-38.3 hook `on_room_disconnected` → `process_post_call_qa_task` (P1) | ❌ chưa land | `agent_worker.py:968` chỉ `disconnect_event.set()`; task tồn tại (`voice_tasks.py:195`) nhưng không được gọi |
| AI-38.4 bảng ngày lễ VN trong `is_voice_curfew` (P2) | ❌ chưa land | `app/services/sequencer/scheduling.py:53` — grep holiday/tet/lunar rỗng |
| AI-38.5 BANT LLM-as-judge (P3) | ❌ chưa land | Chỉ heuristics trong `app/services/voice/billing.py` |

**Process finding:** 5/5 action items Epic 38 vẫn open sau epic 39 hoàn tất → retro action items không được track tới lúc đóng. Cần cơ chế (ví dụ gate pre-epic review open items) để items P0 không trôi.

## Action items

| # | Action item | Source | Priority | Owner |
|---|---|---|---|---|
| AI-39.1 | Nâng `VOICE_DECIDE_TIMEOUT_SECONDS` default ~0.8s hoặc tách timeout riêng cho `transfer_to_human` (P0-1) | `semantic_gate.py:51` | P0 | dev |
| AI-39.2 | Đổi ingest filter sang fail-closed — drop/requeue batch nghi vấn khi Jev error (P0-2) | `chainlens/ingest.py:138-144` | P0 | dev |
| AI-39.3 | Dùng `_env_float`+`math.isfinite` cho voice env parsing (P1-1); strip code fence trong `llm_json.py:413` (P1-2); bổ sung `thread_id`+turn vào dedup key `jev_router.py:260` (P1-3) | diff review | P1 | dev |
| AI-39.4 | Cắt trường candidate trong entity resolution payload (P1-4); sửa `jev-eval-gate.yml` branches → `develop` (P1-5) | diff review | P1 | dev |
| AI-39.5 | Quyết định telemetry schema cho background decisions thiếu `user_id` — nullable column hoặc service-account user | AD-J(a) divergence | P1 | architect |
| AI-39.6 | Xóa/refactor `app/tasks/jev_guardrails.py` stub — gọi qua DecisionService thật hoặc loại bỏ | scout | P1 | dev |
| AI-39.7 | Thêm `passes_positive` vào `ConfidenceGate`, bỏ `_noul_yes` hand-rolled; cân nhắc tách `service.py` (662 dòng) | duplication | P2 | dev |
| AI-39.8 | Đưa open items Epic 38 (AI-38.1..38.5, đặc biệt AI-38.1 migration P0) vào sprint backlog trước Epic 41; đề xuất gate pre-epic check open items | follow-through | P1 | PM/architect |
| AI-39.9 | `InboundIntentClassifier` (Telegram) nâng cấp regex → Jev khi có slot | `spec-39-5:113` | P3 | dev |
| AI-39.10 | Watch: demote-not-drop RAG vẫn tốn token context LLM — đo context-token delta và quyết định cap | `deferred-work.md:1867`, `spec-39-4:96` | P3 | dev |

## Acceptance verdict

**accepted-with-open-items** — criteria: **declared** (epic spec khai báo AC rõ, eval evidence trong `jev_eval/summary.md`).

> **Post-retro update (2026-10-10):** toàn bộ fix-now items đã land trên branch này — AI-39.1 (voice timeout default 0.8s + `_env_float` safe parse), AI-39.2 (ingest fail-closed drop-batch), AI-39.3 (code-fence strip `llm_json`, dedup key `thread_id:text` trong `jev_router`, env parse an toàn), AI-39.4 (trim entity candidate fields + CI branch `develop`), AI-39.6 (`jev_guardrails` wired `DecisionService.decide` thật), AI-39.7 (`ConfidenceGate.passes_positive` + clone-dict masking). Epic-38 carryover: AI-38.1 migration `244_add_workspace_sip_trunks`, AI-38.2 Redis consumer `stream:prospect:engagement` (Celery beat 1-min, consumer group + XACK), AI-38.3 disconnect hook → `process_post_call_qa_task.delay`, AI-38.4 solar holidays trong `is_voice_curfew`. Verification: `pytest -m unit` 960 passed / 0 failed, ruff clean, alembic head = 244. Vẫn mở (cần quyết định/feature scope): AI-39.5 schema decision, AI-38.5 BANT LLM-judge, AI-39.9 regex→Jev, AI-39.10 token watch.

> **Post-retro update 2 (2026-10-10):** cả 4 item trên cũng đã land (`f8dfcd944`) — AI-39.5: `token_usage.user_id` nullable (migration 245, system call ghi `external_metadata.system=true`, bỏ sentinel vì FK→user.id); AI-39.9: `InboundIntentClassifier.aevaluate_intent` + `is_researchy` qua `classify_intent`/`intent_classify` (regex fallback); AI-38.5: `bant_scoring` ScoreQuestion set 0–3/pillar → 0–25 pts + `aevaluate_bant_score`; AI-39.10: xác nhận `decide()` đã ghi `TokenUsage(usage_type=decision, cost_micros)` feed `evaluate_decision_daily_cost_alert` — không cần pipeline mới. Verification: 3742 unit tests passed, ruff clean. Lưu ý: `main_agent/classifier.py` chưa có caller (helper sẵn cho epic kế); downgrade migration 245 xóa các row `user_id IS NULL`. **Mục AI-39.10 trong retro doc / sprint item 14 (đo context-token delta demote-not-drop và chốt cap) vẫn để `status: open` theo dõi thực nghiệm.**

Lý do: 8/8 story done, AC reflected in code, unit suite 483 pass, eval 96.3% VN + latency/cost trong kỳ vọng, amendments có chủ đích và đã land (demote-not-drop). Tuy nhiên 2 P0 findings (voice timeout nuốt transfer, ingest fail-open lọt PII) là rủi ro thực cần fix trước khi epic tiếp theo dựa vào nền này — chúng là open items chứ không phải lý do reject, vì epic đã đạt AC khai báo và code hiện có ý thức ghi nhận trade-off (comment `semantic_gate.py:45-50`).

## Open questions

- Voice: timeout đã nâng lên 0.8s theo live verify 313–765ms; con số cuối cùng vẫn nên tinh chỉnh theo dữ liệu cuộc gọi thật nhiều hơn (giữ env-tunable).
- Telemetry `user_id` nullable vs service-account: quyết định schema cần architect xác nhận vì ảnh hưởng migration + dashboard.
- Story 39.6 context producer phụ thuộc Epic 38.7 outbound trigger engine (BLOCKED) — cần quyết định ưu tiên Epic 38.7 hay chấp nhận context rỗng.

## Assumptions

- Epic chọn tự động qua `--epic 39` (invocation rõ), `detect-epic --epic 39` trả 8/8 done, `pending_stories` rỗng.
- Chạy tương tác (headless: false) — không có "machine rejected" nào được áp.
- Diff range `83e41ad4a..d51120fed` lấy từ commit đầu Epic 39 (`93c40fbde^`) tới commit cuối (`d51120fed`); 3 commit ngoài phạm vi epic (BMAD upgrade + Epic 37) đã loại khỏi phân tích churn.
- Action items AI-39.x là proposed remediation chờ human apply — chưa sửa code trong retro này.

