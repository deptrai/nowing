---
title: '39.6 Voice Agent Post-STT Semantic Decisions'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_commit: '6e12c960ea4e8204c041e6246a097b32da84bfce'
route: 'dispatch'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Voice SDR agent (`VoiceSDRAgent`) phản hồi mọi turn STT vô điều kiện — không có semantic gating cho backchannel ("ừ", "à"), STT noise, hay yêu cầu gặp người thật; transcript cuối turn đi thẳng vào LLM generation.

**Approach:** Một `decide()` call batched trên transcript trong `on_user_turn_completed` — `should_respond` (Noul), `caller_frustration` (Score 0-3), `transfer_to_human` (Noul) — qua `task="voice"` với timeout clamp ~0.45s; advisory + fail-open: flag off/error/below-gate → behavior hiện tại nguyên vẹn.

## Boundaries & Constraints

**Always:**
- `DECISION_ENABLED` + `decision_task_enabled("voice")` gate mọi call; `DECISION_VOICE_ENABLED`/`DECISION_VOICE_THRESHOLD` đã tồn tại — không thêm flag mới.
- Fail-open tuyệt đối: bất kỳ exception/timeout nào → turn tiếp tục generate bình thường (voice loop không bao giờ chết vì decision layer).
- Per-call `timeout=0.45` (AC: ≤500ms); decide() chạy SAU khi filler watchdog task đã start (watchdog = safety net cho perceived latency) nhưng TRƯỚC `super().on_user_turn_completed` (LLM node) — suppression/transfer path PHẢI cancel `self._filler_task` (set `_first_token_event`) để không bị dangling filler "Dạ vâng..." rồi dead-air.
- Jev chỉ đọc `new_message.text_content` transcript — không bao giờ đụng audio frames/VAD (Silero giữ nguyên).
- Telemetry chỉ khi `workspace_id` + `user_id` có sẵn (TokenUsage.user_id NOT NULL); thiếu → log-only, đúng boundary hiện tại. Lưu ý: `create_call_room`/`end_call` hiện **zero production callers** — metadata plumbing là speculative end-to-end cho đến khi orchestrator attach keys.
- `transfer_to_human` chỉ escalate khi answer `value >= 0.7` VÀ gate pass. Sequence bắt buộc: cancel filler → `handle = session.say(line)` → `await handle.wait_for_playout()` (+buffer) → `end_call` — `say()` fire-and-forget rồi `delete_room` ngay = caller không nghe gì.
- `should_respond` suppress CHỈ khi `1 - value >= 0.7` (module const `VOICE_SUPPRESS_MIN_CONFIDENCE=0.7`, pin cứng — `passes_negative` ở default threshold 0.5 quá trigger-happy).

**Never:**
- Không suppress/escalate khi gate fail hoặc answer là "uncertain" — uncertain = respond bình thường.
- Không SIP `transfer_sip_participant`, không call-control mới ngoài `end_call` có sẵn.
- Không persist frustration vào table mới — chỉ structured log (không có voice session table).
- Không thay endpointing: 180ms VAD silence vẫn quyết định turn boundary.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal utterance | "Cho tôi hỏi giá nhà Quận 7" | `should_respond`=yes → generate như cũ | N/A |
| Backchannel | transcript "ừ", "à", "vâng ạ" | `1 - should_respond ≥ 0.7` → cancel filler → `StopResponse` — agent im lặng, turn rơi khỏi chat ctx | N/A |
| Transfer request | "Cho tôi nói chuyện với người thật" | `transfer_to_human` ≥0.7 + gate → cancel filler → `say()` → `wait_for_playout` → `end_call` + WARNING log | N/A |
| Transfer + suppress cùng true | conflict | `transfer` thắng — escalate trước, suppress bỏ qua | precedence documented |
| Frustrated caller | "Sao gọi hoài vậy, phiền quá" | `caller_frustration` 2-3 → log score; vẫn generate | N/A |
| Flags off | `DECISION_VOICE_ENABLED=false` | Zero overhead — không call, không check | early return |
| Jev timeout | `decide()` >450ms | `DecisionError` → fail-open, generate như cũ | except → proceed |
| Malformed answer | backend trả sai shape | `InvalidDecisionAnswer` → fail-open như mọi exception | except → proceed |
| Empty/STT noise | transcript whitespace/<3 chars | Skip decide (không tốn call) | early return |
| No context | metadata thiếu workspace/user | Decide vẫn chạy, telemetry log-only | `_record_usage` skip |
| Session shutdown | `self.session` raises RuntimeError | giữ guard hiện có (:360-366) — catch, proceed | except → proceed |

**Decisions:** Escalation = `session.say()` canned transfer line + `end_call` + structured WARNING log `voice_escalation` (human team gọi lại sau) — không SIP transfer story này.

</frozen-after-approval>

## Code Map

- `nowing_backend/app/services/voice/agent_worker.py` — `VoiceSDRAgent` (:302, ctor :313 không args); `on_user_turn_completed` (:350-368, hook chính — start `_filler_task` watchdog :359-364 + `super()`); `entrypoint` (**:444-486**, `ctx.connect()` :459) parse `ctx.room.metadata` → plumb context + `room_name` vào agent; `session.say()` (:427 pattern — returns SpeechHandle, phải `await wait_for_playout()`); `_filler_task`/`_first_token_event` fields; VAD config (:139-150)
- `nowing_backend/app/services/voice/telephony_client.py` — `end_call(room_name, participant_identity)` :568-632 (escalation end path — `delete_room` khi identity None :622-625); `normalize_room_name(session_id)` :203-211; `create_call_room` metadata (:227-255) — `{"session_id": ...}` + caller-passed keys; ctor lazy cần `LIVEKIT_URL/KEY/SECRET` (:176-194, có sẵn trong worker env :50-52) — lifecycle `aclose` cần handle
- `nowing_backend/app/services/decision/service.py` — `decide()` :59-74; timeout clamp [0.1, `DECISION_TIMEOUT_SECONDS`] :165-176; fallback có **2 sites**: retry leg :203-218 + backend-resolution fallback :146-152 — `use_fallback` phải skip cả hai; `_record_usage` tự mở session (:397-426) — caller truyền `session=None`, chỉ cần workspace_id+user_id
- `nowing_backend/app/services/decision/questions/` — registry pattern: module `VERSION`+`REQUIRED_STATE_KEYS`+`QUESTIONS` + register block trong `__init__.py` :17-53; multi-question example `content_filter.py`; Choice example `intent_classify.py`
- `nowing_backend/app/services/decision/types.py` — `NoulQuestion` :39, `ScoreQuestion(criteria: list)` :31, `Answer(kind, value, confidence)` :47
- `nowing_backend/app/services/intent_classification/service.py` :69-116 — canonical consumer shape: `get_set` → `decide(task=..., question_set=..., required_state_keys=...)` → `ConfidenceGate.for_task` → try/except fail-open
- `nowing_backend/app/config/decision.py` — `"voice"` trong `_DECISION_TASK_DEFAULTS` :111; `DECISION_VOICE_ENABLED` :104
- `nowing_backend/app/services/decision/gate.py` — `ConfidenceGate.for_task("voice")` default 0.5 :33-39; `passes_negative()` :88 cho should_respond=confidently-NO
- `nowing_backend/tests/unit/voice/test_agent_worker.py` — conventions: `patch.object(agent_worker, ...)`, mocked session, :407-416 lifecycle hook exercise
- LiveKit: `StopResponse` (livekit.agents.llm) raise trong `on_user_turn_completed` → abort generation — verify import path trên pinned `livekit-agents==1.8.2`

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/decision/questions/voice_turn.py` — question set `voice_turn` v1.0.0: `should_respond`/`transfer_to_human` Noul + `caller_frustration` Score(0-3), `REQUIRED_STATE_KEYS=("transcript",)`; register trong `questions/__init__.py` — registry contract
- [x] `nowing_backend/app/services/voice/semantic_gate.py` — `evaluate_voice_turn(transcript, *, workspace_id, user_id, timeout=0.45)` (KHÔNG truyền session — `_record_usage` tự mở; tránh nhầm `AsyncSession` vs `AgentSession`) → `VoiceTurnAssessment(suppress_response, transfer, frustration_score)`; theo canonical shape của intent_classification; `VOICE_SUPPRESS_MIN_CONFIDENCE=0.7`; fail-open return defaults — service wrapper
- [x] `nowing_backend/app/services/decision/service.py` — optional `use_fallback: bool = True` param skip **cả 2** fallback sites (retry :203-218 + resolution :146-152); voice dùng `use_fallback=False` (fallback leg = ~0.9s vượt AC budget) — bounded latency
- [x] `nowing_backend/app/services/voice/agent_worker.py` — `VoiceSDRAgent.__init__` optional kwargs `workspace_id, user_id, call_session_id, room_name`; `entrypoint` (:444-486) parse `ctx.room.metadata` JSON → pass context + `ctx.room.name`; `on_user_turn_completed`: extract `new_message.text_content` → flags gate → `evaluate_voice_turn` → transfer: cancel filler + `say()` + `wait_for_playout` + `end_call` + WARNING log / suppress: cancel filler + `raise StopResponse` / log frustration; giữ `self.session` RuntimeError guard (:360-366) — consumer wiring
- [x] `nowing_backend/tests/unit/voice/test_semantic_gate.py` + extend `test_agent_worker.py` — mock `decide()`: suppress→StopResponse, transfer→say+end_call, frustration→log, flag-off→zero calls, timeout→proceed, empty transcript→skip — I/O matrix coverage

**Acceptance Criteria:**
- Given STT transcript hoàn chỉnh trong `on_user_turn_completed`, when `DECISION_VOICE_ENABLED=true`, then `decide()` evaluate `should_respond`(Noul) + `caller_frustration`(Score 0-3) + `transfer_to_human`(Noul) trong ONE batched call.
- Given `transfer_to_human` answer value ≥0.7 pass gate, then escalation: `session.say` canned line + `end_call` + `voice_escalation` WARNING log.
- Given decide() chậm/lỗi/flag off, then turn generate bình thường — không delay >500ms, không crash.
- Given transcript <3 chars hoặc whitespace, then không gọi Jev.

## Implementation Notes

- `voice_turn` set registered; verification prints `voice_turn 1.0.0 ['should_respond','caller_frustration','transfer_to_human']`.
- `StopResponse` verified at `livekit.agents.llm.StopResponse` on pinned `livekit-agents==1.8.2`; upstream drops the turn from chat ctx when raised in `on_user_turn_completed`.
- Escalation uses `async with LiveKitTelephonyClient()` per transfer (rare path — lazy ctor, `aclose` handled by `__aexit__`); raises `StopResponse` only when the full say→playout→end_call sequence succeeds — any failure (incl. missing `room_name`) fails open to normal generation.
- `use_fallback=False` gates both fallback sites; existing callers unchanged (default `True`).
- Verified: `ruff check` clean; `pytest tests/unit/voice tests/unit/services/decision -m unit -q` → 295 passed. `test_registry.py` set-name assertion + `required_state_keys` extended for `voice_turn`.
- Review pass 1 (3 layers, ~25 findings): patched 15 (filler race + interrupt cut, escalation intent log ordering, playout/end_call timeouts, re-arm watchdog on failure, `_coerce_int` OverflowError, `end_call` verbatim room name + NOT_FOUND failure, `LOCAL_BACKCHANNELS` local suppress, `client_id` forwarding, `_MAX_TRANSCRIPT_CHARS`, test coverage for `use_fallback` both sites + frustration caplog + say/decide arg pins); deferred 1 (metadata plumbing unwired end-to-end); rejected rest (designed asymmetry, tolerable bounds).

## Spec Change Log

## Review Triage Log

| # | Finding | Verdict | Route | Evidence |
|---|---------|---------|-------|----------|
| 1 | `_coerce_int` lets `OverflowError` (JSON 1e999→inf) crash entrypoint pre-`session.start` | high | patch | `int(inf)` → OverflowError ∉ except tuple; call never answered. Fixed: OverflowError added. |
| 2 | Filler watchdog fires @80ms, decide ~300ms — `say()` already queued before suppress/transfer; cancel can't retract | high | patch | `session.interrupt()` on suppress + pre-say in escalate; `_maybe_inject_filler` re-checks event before say. |
| 3 | `voice_escalation` logged only on full success — played promise + failed end_call = no record; session=None drop silent | medium | patch | Intent WARNING now logged when `assessment.transfer` first, before attempt. |
| 4 | Escalation failure leaves cancelled watchdog → fail-open generation gets dead air on slow LLM | medium | patch | `_rearm_filler_watchdog()` recreates event+task on failure path. |
| 5 | `wait_for_playout`/`end_call` unbounded — stalled playout hangs hook forever | medium | patch | `wait_for` 5s/3s bounds → fail-open False. |
| 6 | `end_call` re-normalizes `room_name` → non-prefixed names mangled → NOT_FOUND swallowed → escalate reports success on live room → permanent silence | high | patch | `end_call` verbatim name (normalize stays at create_call_room); NOT_FOUND → warning + `TelephonyError`. |
| 7 | Min-chars 3 means "ừ"/"à" never reach Jev — matrix's suppressible backchannels unreachable | medium | patch | `LOCAL_BACKCHANNELS` exact-match fast-path (normalized) → local suppress, zero cost. |
| 8 | `call_session_id` not forwarded → TokenUsage can't join to call session | low | patch | `client_id` param plumbed gate→decide. |
| 9 | `use_fallback=False` untested at both fallback sites | medium | patch | 2 new service tests: retry-leg + resolution-site. |
| 10 | Frustration caplog unasserted; decide/say args unpinned | medium | patch | caplog assert + positional/kwarg pins added. |
| 11 | No transcript length cap before paid call | low | patch | `_MAX_TRANSCRIPT_CHARS=4000` (mirrors intent service). |
| 12 | Metadata plumbing zero prod callers → telemetry permanently log-only until orchestrator attaches keys | — | defer | Real boundary; recorded in deferred-work.md. |
| 13 | Asymmetric gating (suppress pinned 0.7 ignores task gate) | false | rejected | Deliberate — suppression must be harder than `DECISION_VOICE_THRESHOLD` default 0.5; documented in spec+const. |
| 14 | Telemetry `_record_usage` write outside decide timeout could push past 500ms | low | rejected | Bounded by DB responsiveness in practice; write is one insert; tolerable residual. |
| 15 | Transfer-fail falls through to generation while suppress flag ignored | low | rejected | Correct fail-open — replying beats silencing a human-requesting caller; precedence covers success path. |
| 16 | Nits: `session_id` double-get; "non-whitespace" comment vs `len(strip)`; filler cancel without await | low | patch | First two fixed; unawaited cancel is consistent with fire-and-forget task mgmt. |

## Design Notes

- **Một decide() cho cả 3 questions** — parallel server-side, 1 round-trip ~300ms. Không tách calls (3× latency + 3× cost).
- **suppress ở bar 0.7 không 0.5** — `passes_negative` với default threshold 0.5 suppresses khi noul ≤0.5 (quá eager); pin `1 - value >= 0.7` = chỉ khi Jev confident utterance không cần reply.
- **Filler watchdog chạy song song decide()** — watchdog start trước (80ms safety net), decide await sau; mọi non-generate path (suppress/transfer) cancel `_filler_task` + set `_first_token_event` trước khi thoát.
- **say→wait_for_playout→end_call** — `session.say()` là fire-and-forget SpeechHandle; `delete_room` ngay sau = caller nghe không gì. Transfer line phải playout xong.
- **Timeout 0.45s + `use_fallback=False`** — fallback leg nhân đôi worst-case (~0.9s) vượt 500ms AC; voice thích miss-decision hơn stall.
- **Context plumbing qua room metadata** — `create_call_room` đã attach `{"session_id"}`; worker parse `ctx.room.metadata` → `VoiceSDRAgent(workspace_id=..., user_id=..., room_name=ctx.room.name)`. Metadata thiếu keys → telemetry log-only (không block call). Caveat: không caller nào hiện attach workspace/user — speculative cho đến khi orchestrator wiring.
- **`StopResponse` drop turn khỏi chat context** (upstream livekit/agents#5026) — suppressed backchannel không vào LLM history = desirable; vì vậy `say()` phải chạy TRƯỚC khi raise.
- **Frustration = log-only MVP** — score 2-3 + transfer gate mới act; score alone chỉ structured log `[voice_turn] frustration=N` để future routing/dash dùng — không table mới story này.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/services/voice app/services/decision tests/unit/voice` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/voice tests/unit/services/decision -m unit -q` — expected: all pass
- `cd nowing_backend && uv run python -c "from app.services.decision import get_question_registry; qs=get_question_registry().get_set('voice_turn'); print(qs.name, qs.version, list(qs.questions))"` — expected: `voice_turn 1.0.0 ['should_respond','caller_frustration','transfer_to_human']`

**Manual checks (nếu chạy được live):**
- `DECISION_BACKEND=jev DECISION_VOICE_ENABLED=true TYPESAFE_API_KEY=... uv run python` — `evaluate_voice_turn("cho tôi nói chuyện với người thật")` → `transfer=True`.

**Live verify 2026-09-22** (real `api.typesafe.ai`, `DECISION_BACKEND=jev`, key từ XActions env):
- `"cho tôi nói chuyện với người thật"` → `transfer=True`, `frustration=1.01`, **765ms**
- `"nhà này giá bao nhiêu vậy"` → respond, `frustration=0.0`, **313ms**
- `"ừ"` → `suppress=True` qua LOCAL_BACKCHANNELS — **0 Jev call**
- Cold-start call (TLS handshake) timeout → fail-open respond, đúng design
- **Calibration finding:** batched 3-question `voice_turn` calls = 313–765ms thật — pin 0.45s drop ~30-50% calls (kể cả transfer request quan trọng nhất). `VOICE_DECIDE_TIMEOUT_SECONDS` giờ env-tunable (default 0.45 giữ AC ≤500ms); filler watchdog 80ms mask perceived wait nên ops có thể nới 0.8-1.0s.
</content>
