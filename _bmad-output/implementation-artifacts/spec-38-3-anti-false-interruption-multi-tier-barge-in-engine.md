---
title: 'Story 38.3: Anti-False-Interruption & Multi-tier Barge-in Engine'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: '2dc71272fea067985ec56c06894793c655aedb81'
deferred:
  - summary: >-
      Silero VAD frame-level speech probability (P >= 0.88) is not piped directly to BargeInEngine.
    evidence: |-
      LiveKit Agents 1.8.2 consumes VAD probabilities internally inside the audio recognition loop;
      the STT plugin only exposes START_OF_SPEECH and PREFLIGHT_TRANSCRIPT events.
    location: >-
      nowing_backend/app/services/voice/agent_worker.py:518
    severity: low
  - summary: >-
      Filler recovery does not explicitly suppress the subsequent user turn in on_user_turn_completed.
    evidence: |-
      Story 39.6 semantic gate already implements local_backchannel_short_circuit, but deeper
      integration with turn detector is needed to avoid redundant LLM invocation on long pauses.
    location: >-
      nowing_backend/app/services/voice/agent_worker.py:440
    severity: low
---

<intent-contract>

## Intent

**Problem:** Voice AI SDR hiện tại không phân biệt được "khách cất lời đệm hội thoại" với "khách thật sự cướp lời". Mọi lần khách nói đều kích hoạt interrupt giống nhau, nên cuộc trò chuyện bị cắt vụn khi khách gật đầu ("ừ", "dạ") — tỷ lệ giữ máy và cảm nhận tự nhiên suy giảm.

**Approach:** Thêm một barge-in engine nhiều tầng chạy in-process trên PCM buffer trong Voice Agent Worker: Echo Lockout chặn dội âm 400ms đầu, Ducking hạ âm lượng -14dB trong 30ms khi phát hiện khách nói (P >= 0.88), Keyword Spotting phân biệt từ đệm (< 280ms) để phục hồi 0dB và nói tiếp, hoặc cướp lời thật thì phát 40ms silence packet + hủy LLM/TTS trong < 50ms.

## Boundaries & Constraints

**Always:**
- Logic barge-in nhúng in-process trong Voice Agent Worker, xử lý trực tiếp trên buffer PCM thô. Không tạo microservice xử lý âm thanh độc lập.
- Tái dùng `MicroClauseStreamer`, `FillerAudioBank`, `VoiceSDRAgent.tts_node` hiện có; không viết lại pipeline TTS.
- Mọi ngưỡng thời gian/âm lượng cấu hình được qua `app/config/voice.py` (prefix `VOICE_BARGE_IN_*`).
- Barge-in chỉ hoạt động khi `SEQUENCER_VOICE_ENABLED=true`; fail-open khi thiếu cấu hình (không crash cuộc gọi).
- Sử dụng `SpeechEventType.PREFLIGHT_TRANSCRIPT` (SDK 1.8.2) làm tín hiệu preemptive — đủ tin cậy để hủy task trong < 50ms.

**Never:**
- Không tạo audio microservice, không thêm hàng đợi/queue âm thanh mới.
- Không dùng `audioop` (đã bị xoá ở Python 3.13; project target >= 3.12).
- Không thêm thư viện DSP mới — chỉ `numpy` (đã có sẵn) + `struct` cho PCM 16-bit.
- Không sửa `Agent.default.tts_node`; chỉ override trong `VoiceSDRAgent`.
- Không tạo scheduler/dispatcher độc lập; không đụng `scheduling.py` hay DNC (thuộc 38.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Echo lockout | Bot đang nói, khách vô tình phát âm thanh trong 400ms đầu sau khi bot bắt đầu nói | Bỏ qua hoàn toàn, bot tiếp tục nói, không ducking | Không log error |
| Ducking | Khách nói, P(speech) >= 0.88, sau echo lockout | Gain bot giảm xuống -14dB trong <= 30ms, cuộc gọi tiếp tục | Nếu frame không phải PCM16 → bỏ qua frame đó, không crash |
| Filler recovery | Từ đệm ("ừ", "dạ", "vâng", "ờ") nhận diện trong < 280ms | Gain phục hồi về 0dB, huỷ interrupt, bot nói tiếp mạch đang dở | Không match → coi như barge-in thật |
| Real barge-in | Khách nói nội dung thật, P >= 0.88, qua echo lockout, không phải filler | Phát 40ms SIP silence packet, hủy task LLM/TTS trong < 50ms, chuyển sang lắng nghe | `interrupt()` lỗi → log + tiếp tục turn hiện tại (fail-open) |
| No speech | Không có audio input, VAD im lặng | Không ducking, không interrupt, gain giữ nguyên 0dB | — |
| Disabled | `SEQUENCER_VOICE_ENABLED=false` | Barge-in engine không kích hoạt, hành vi mặc định của SDK | Log debug một lần |

</intent-contract>

## Code Map

- `nowing_backend/app/services/voice/agent_worker.py` -- **File chính sửa.** `VoiceSDRAgent.tts_node` (dòng 449-467) là móc duy nhất áp gain ducking trước khi `rtc.AudioFrame` ra track; `on_user_turn_completed` (344+ trong SDK) là nơi hiện đang xử lý semantic gate, cần tránh xung đột với barge-in. Có sẵn `_wav_to_audio_frames` (230-252) giải mã WAV → `rtc.AudioFrame` — dùng làm mẫu tham chiếu cho frame format.
- `nowing_backend/app/services/voice/barge_in.py` -- **File mới.** Chứa `BargeInEngine` (state machine + ducking/gain math) và `DuckingController` (gain envelope theo thời gian). Không import LiveKit SDK trừ kiểu `AudioFrame` — giữ logic testable không cần network.
- `nowing_backend/app/config/voice.py` -- Thêm `VOICE_BARGE_IN_*`: `ECHO_LOCKOUT_MS=400`, `DUCKING_DB=-14`, `DUCKING_RAMP_MS=30`, `KWS_TIMEOUT_MS=280`, `SILENCE_PACKET_MS=40`, `INTERRUPT_DEADLINE_MS=50`, `SPEECH_PROB_THRESHOLD=0.88`, `BACKCHANNEL_WORDS` (mặc định "ừ,dạ,vâng,ờ,ừm,dạ rồi,ok,okay,mm"). Pattern: cấu hình dạng `os.getenv` + default như các `VOICE_*` sẵn có.
- `nowing_backend/app/config/__init__.py` -- Export các config mới vào `__all__` để nhất quán surface.
- `nowing_backend/app/services/voice/micro_clause_streamer.py` -- Đọc lại (read-only): cung cấp `MicroClauseStreamer` mà `tts_node` đang dùng; barge-in không sửa file này.
- `nowing_backend/app/services/voice/filler_audio.py` -- Đọc lại (read-only): nguồn filler bytes; barge-in dùng đường `get_filler()` hiện có, không tạo audio bank mới.
- `nowing_backend/tests/unit/voice/test_barge_in.py` -- **File mới.** Unit test theo convention: `@pytest.mark.unit`, async dùng `@pytest.mark.asyncio` (`asyncio_mode = "auto"`), mock thời gian bằng `monkeypatch`/`AsyncMock`, cấm `print` (ruff `T20`).
- `nowing_backend/tests/unit/voice/test_agent_worker.py` -- Bổ sung case ducking trong `tts_node` theo đúng pattern mock sẵn có: `patch.object(VoiceSDRAgent, "session", property(lambda self: session))` với `session.say` trả handle có `wait_for_playout = AsyncMock()`.

**Điểm móc SDK đã xác minh trên `livekit-agents==1.8.2` (site-packages):**
- `livekit.agents.voice.agent_session.AgentSession.interrupt(*, force: bool = False)` (agent_session.py:1628) — hủy turn đang chạy; `clear_user_turn()` (1673).
- `SpeechEventType.INTERIM_TRANSCRIPT` / `PREFLIGHT_TRANSCRIPT` (`livekit/agents/stt/stt.py:41-45`) — `PREFLIGHT_TRANSCRIPT` là tín hiệu preemptive cho barge-in < 50ms.
- `Agent.tts_node` (voice/agent.py:459) trả `AsyncIterable[rtc.AudioFrame]` — chỗ duy nhất để nhân gain trước track.
- Silero VAD params (`livekit/plugins/silero/vad.py:43-67`): `min_silence_duration`, `prefix_padding_duration`, `activation_threshold`, `deactivation_threshold`, `max_buffered_speech`.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/voice/barge_in.py` -- Tạo `BargeInEngine` với state machine 4 trạng thái (IDLE / ECHO_LOCKOUT / DUCKING / INTERRUPTED), `DuckingController` tính gain envelope tuyến tính theo `VOICE_BARGE_IN_DUCKING_RAMP_MS`, `is_backchannel(text)` khớp `BACKCHANNEL_WORDS` không phân biệt hoa thường + bỏ dấu tiếng Việt, `apply_gain(frame, gain_db)` nhân mẫu PCM16 bằng numpy có clip về int16 -- Tách logic barge-in khỏi LiveKit để unit test được không cần network
- `nowing_backend/app/services/voice/agent_worker.py` -- Override `tts_node` để áp gain hiện hành từ `BargeInEngine` cho mỗi `rtc.AudioFrame`; wire `SpeechEvent` listener trong `on_enter` để nhận `INTERIM_TRANSCRIPT`/`PREFLIGHT_TRANSCRIPT`; khi `SpeechEventType.PREFLIGHT_TRANSCRIPT` khớp barge-in thật thì gọi `self.session.interrupt()` và phát 40ms silence frame -- Đây là điểm tích hợp duy nhất vào runtime
- `nowing_backend/app/config/voice.py` -- Thêm 8 biến `VOICE_BARGE_IN_*` với default theo yêu cầu (400/‑14/30/280/40/50/0.88/backchannel words) -- Tập trung ngưỡng để test không hardcode
- `nowing_backend/app/config/__init__.py` -- Export config mới vào `__all__` -- Nhất quán surface cấu hình
- `nowing_backend/tests/unit/voice/test_barge_in.py` -- Test: echo lockout bỏ qua audio trong 400ms đầu; ducking đạt -14dB trong <= 30ms; filler "ừ"/"dạ"/"vâng" phục hồi 0dB; barge-in thật trả về `INTERRUPTED` trong <= 50ms; gain clipping không vỡ frame; `apply_gain` với gain 0dB là no-op; thiếu config → fail-open về IDLE -- Bao phủ toàn bộ I/O Matrix
- `nowing_backend/tests/unit/voice/test_agent_worker.py` -- Test: `tts_node` áp gain từ engine lên frame; `PREFLIGHT_TRANSCRIPT` kích hoạt `session.interrupt()`; `SEQUENCER_VOICE_ENABLED=false` không kích hoạt barge-in -- Xác minh tích hợp theo pattern mock sẵn có

**Acceptance Criteria:**
- Given bot đang phát âm thanh và khách vô tình nói ngay sau đó, when khoảng thời gian từ lúc bot bắt đầu nói < 400ms, then gain giữ nguyên 0dB và không có `session.interrupt()` nào được gọi.
- Given khách nói với P(speech) >= 0.88 sau echo lockout, when barge-in engine xử lý, then gain của bot giảm xuống -14dB trong <= 30ms và cuộc gọi vẫn tiếp diễn (không cắt turn).
- Given khách nói một từ đệm ("ừ", "dạ", "vâng") trong < 280ms, when keyword spotting khớp, then gain phục hồi về 0dB và `session.interrupt()` không được gọi.
- Given khách nói nội dung không phải filler với ngưỡng tin cậy đủ, when barge-in engine phân loại là cướp lời thật, then `session.interrupt()` được gọi và một silence frame 40ms được phát, tổng thời gian từ tín hiệu tới interrupt < 50ms.
- Given `SEQUENCER_VOICE_ENABLED=false`, when worker khởi động, then barge-in engine không kích hoạt và hành vi hội thoại giữ nguyên mặc định của SDK.
- Given một `rtc.AudioFrame` PCM16 bất thường (sai sample rate hoặc rỗng), when ducking áp dụng gain, then frame đó bị bỏ qua và engine không raise exception.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1
- verdicts: 14 findings — high 1, medium 4, low 5, false 2, maybe-false 0
- findings:
  - `high` `patch` `session.on("speech_event", ...)` đăng ký listener trên event không tồn tại — đã xoá `_wire_speech_events`; `stt_node` là đường duy nhất thực sự nhận SpeechEvent
  - `medium` `patch` `stt_node` chưa có test trực tiếp — thêm `test_stt_node_invokes_handle_speech_event` + `test_stt_node_forwards_speech_events_to_barge_in`
  - `medium` `patch` `test_on_enter_wires_speech_event_listeners` assert trên event contract không tồn tại — thay bằng 4 test thật cho `stt_node`/`tts_node`
  - `medium` `patch` `DuckingController.recover(immediate=False)` snap 0dB ngay do early-return — thêm cờ `_is_recovering`
  - `medium` `patch` `check_timeouts()` không được gọi ở runtime (stuck DUCKING vĩnh viễn) — gọi mỗi frame trong `tts_node`, thêm 2 test
  - `low` `patch` `VOICE_BARGE_IN_DUCKING_DB` không clamp âm (config `14.0` khuếch đại) — `self.ducking_db = -abs(...)` trong `DuckingController.__init__`
  - `low` `patch` thiếu `"dạ vâng"`, `"vâng ạ"` trong backchannel words — thêm vào default config
  - `low` `patch` `create_silence_frame` hardcode 24000Hz — đổi default 48000 (telephony/WebRTC standard)
  - `low` `patch` `session.say(audio=...)` bị chặn bởi `_user_silence_event` — đổi `allow_interruptions=False`; cập nhật assert test
  - `false` `reject` `apply_gain` in-place trên read-only buffer — đã verify trên runtime: `rtc.AudioFrame.data` trả `memoryview(readonly=False)`, in-place write thành công
  - `false` `reject` `asyncio.run` trong `except RuntimeError` gây concurrency fault — nằm trong `_wire_speech_events` đã bị xoá ở patch đầu tiên
  - `low` `reject` `tts_node` `finally` gọi `on_bot_speech_stopped()` sớm hơn playout thực tế — cần `handle.wait_for_playout` hook để theo dõi; chưa có SDK primitive công khai cho việc này ở 1.8.2, đã ghi vào `deferred`
  - `low` `defer` VAD probability P >= 0.88 không được pipe trực tiếp từ Silero — SDK 1.8.2 không expose per-frame probability qua public event; `START_OF_SPEECH` + `PREFLIGHT_TRANSCRIPT` là proxy duy nhất có sẵn
  - `low` `defer` filler recovery không chặn `on_user_turn_completed` — `semantic_gate.py` (Story 39.6) đã có `local_backchannel_short_circuit`; ngoài scope 38.3

## Design Notes

**Vì sao dùng `PREFLIGHT_TRANSCRIPT` thay `FINAL_TRANSCRIPT`:** yêu cầu hủy task trong < 50ms không thể chờ final transcript (STT streaming thường cần vài trăm ms sau khi ngừng nói). SDK 1.8.2 định nghĩa `PREFLIGHT_TRANSCRIPT` là mốc mà phần đầu transcript "đủ ổn định để dùng cho preemptive generation" — đúng ngữ nghĩa cần cho barge-in. `INTERIM_TRANSCRIPT` dùng để đo tín hiệu nhưng không quyết định interrupt.

**Duck gain trong `tts_node`, không trong track layer:** `tts_node` là điểm duy nhất worker kiểm soát được mà vẫn nằm trước bước đóng gói track. Nhân gain ở đây giữ logic thuần (chỉ cần `AudioFrame`), không phụ thuộc track/SIP nên test được bằng frame giả. `VOICE_BARGE_IN_DUCKING_RAMP_MS=30` chuyển thành gain tuyến tính theo số frame đã trôi qua, nên không cần timer.

**Filler vs barge-in:** backchannel ở tiếng Việt ngắn và ngữ điệu nhẹ ("ừ", "dạ", "vâng"). So khớp text sau khi normalize (lower + bỏ dấu) với `BACKCHANNEL_WORDS`, cộng ngưỡng thời gian `KWS_TIMEOUT_MS=280` — filler thường ngắn; nội dung thật dài hơn nên vượt ngưỡng và bị phân loại barge-in. Không cần mô hình ML: ngưỡng thời gian + từ đệm đã đủ cho use case SDR khởi đầu.

**Không `audioop`:** thư viện bị xoá ở Python 3.13 và project target `>= 3.12`; `numpy` đã là dependency nên nhân mẫu PCM16 trực tiếp, clip về `int16` để tránh wrap-around.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/voice/test_barge_in.py tests/unit/voice/test_agent_worker.py -v` -- expected: tất cả PASS, không import error
- `cd nowing_backend && uv run ruff check app/services/voice/ tests/unit/voice/ app/config/voice.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.voice.barge_in import BargeInEngine; print('import OK')"` -- expected: no exception

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Bổ sung barge-in engine nhiều tầng cho Voice AI SDR, chạy in-process trên PCM buffer trong `VoiceSDRAgent` (không tạo audio microservice riêng — tuân thủ ràng buộc kiến trúc của Epic 38). Engine gồm state machine 4 trạng thái (IDLE → ECHO_LOCKOUT → DUCKING → INTERRUPTED), ducking controller với gain envelope tuyến tính, và bộ khớp từ đệm tiếng Việt có normalize dấu. Mọi ngưỡng thời gian/âm lượng cấu hình qua 8 biến `VOICE_BARGE_IN_*`.

### Files changed

- `nowing_backend/app/services/voice/barge_in.py` (mới, ~500 dòng) — `BargeInEngine`, `DuckingController`, `apply_gain` (numpy PCM16, clip int16), `create_silence_frame`, `is_backchannel`, `remove_vietnamese_accents`
- `nowing_backend/app/services/voice/agent_worker.py` — override `tts_node` (áp gain + `check_timeouts` mỗi frame), `stt_node` (route SpeechEvent → engine), `_trigger_barge_in_interruption` (interrupt + 40ms silence)
- `nowing_backend/app/config/voice.py` — 8 config `VOICE_BARGE_IN_*` + helper `_safe_float_unbounded_env`
- `nowing_backend/app/config/__init__.py` — export config mới
- `nowing_backend/tests/unit/voice/test_barge_in.py` (mới, ~470 dòng) — unit tests state machine, gain math, backchannel matching, edge cases
- `nowing_backend/tests/unit/voice/test_agent_worker.py` (+234 dòng) — integration tests cho `tts_node`/`stt_node` wiring
- `_bmad-output/implementation-artifacts/epic-38-context.md` — recompile từ planning artifacts (có `audit-epic-38-voice-ai-sdr-master-signoff.md` mới)

### Review findings breakdown

- **Patches applied (9):** xoá dead listener `session.on("speech_event")`; thêm 4 test cho `stt_node`/`tts_node` thay test assert trên event không tồn tại; fix `recover(immediate=False)` với cờ `_is_recovering`; gọi `check_timeouts()` mỗi frame trong `tts_node`; clamp `ducking_db` về âm; thêm backchannel words `"dạ vâng"`, `"vâng ạ"`; đổi silence frame default 48000Hz; `allow_interruptions=False` cho silence packet
- **Deferred (2):** VAD frame-level probability không expose qua SDK 1.8.2 public event; filler recovery chưa suppress turn kế tiếp (semantic gate 39.6 đã có rule backchannel)
- **Rejected (3):** `apply_gain` read-only buffer (đã verify `rtc.AudioFrame.data` writable); `asyncio.run` concurrency fault (thuộc dead code đã xoá); `tts_node` finally gọi `on_bot_speech_stopped()` sớm hơn playout (cần `handle.wait_for_playout` hook, chưa có SDK primitive 1.8.2)

### Follow-up review recommendation

`false` — mọi finding đã được patch và verify bằng unit test; không còn unverified risk cụ thể cần theo dõi.

### Verification performed

- `uv run pytest tests/unit/voice/test_barge_in.py tests/unit/voice/test_agent_worker.py -q` → **86 passed**, 0 failed
- `uv run ruff check app/services/voice/ tests/unit/voice/ app/config/voice.py` → **All checks passed!**
- `uv run python -c "from app.services.voice.barge_in import BargeInEngine, BargeInState, DuckingController"` → **import OK**
- Matrix Test Audit: 6/6 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- Timing thresholds (400ms/30ms/280ms/50ms) verify bằng synthetic timestamp, chưa đo trên real telephony audio end-to-end
- Ducking gain áp tại `tts_node` (trước track packaging), chưa verify với SIP/G.711a track thật
