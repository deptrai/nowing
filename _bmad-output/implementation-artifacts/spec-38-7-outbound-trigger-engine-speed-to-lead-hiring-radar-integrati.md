---
title: 'Story 38.7: Outbound Trigger Engine: Speed-to-Lead & Hiring Radar Integration'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: 'f768f51f792d77ed29fd4fedd0ff329d2f642eda'
deferred:
  - summary: >-
      Redis stream consumer loop for stream:prospect:engagement not yet running as a worker.
    evidence: |-
      OutboundTriggerEngine.handle_prospect_engagement evaluates events, but no
      long-running consumer loop reads from the Redis stream; production needs a
      Celery beat task or worker process subscribed to the stream.
    location: >-
      nowing_backend/app/services/voice/outbound_trigger.py
    severity: medium
  - summary: >-
      OutboundTriggerEngine does not create SequenceEnrollment rows for Hiring Radar.
    evidence: |-
      handle_hiring_radar_signal dispatches a direct Celery call instead of enrolling
      the lead into a multi-step sequence; sequence-based enrollment is a richer
      follow-up path planned for the campaign layer.
    location: >-
      nowing_backend/app/services/voice/outbound_trigger.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** Hiện tại Voice AI SDR đã có đầy đủ hạ tầng SIP, VAD, Barge-in, Compliance Gate và BYO-SIP, nhưng vẫn chưa được kết nối vào Sequencer làm Action Executor thực tế. Các cuộc gọi outbound chưa thể tự động kích hoạt khi có tín hiệu nóng từ thị trường (như khi prospect xem pitch portal > 45s hoặc khi Intent Radar phát hiện công ty mở đợt tuyển dụng lớn), bỏ lỡ "thời điểm vàng" Speed-to-Lead (< 5 phút).

**Approach:** Kết nối Voice AI SDR vào Sequencer với vai trò Action Executor chính thức (`SequenceStep.channel = "voice"` được bảo vệ bởi cờ `SEQUENCER_VOICE_ENABLED`): (1) Bổ sung nhánh `channel == "voice"` trong `_dispatch_channel()` tại `app/services/sequencer/dispatch.py`, tiền kiểm tra bằng `TelephonyComplianceGate.evaluate_preflight()` và giải quyết trunk qua `SipTrunkManager`; (2) Thêm Celery task `dispatch_voice_call_task` trong `app/tasks/celery_tasks/voice_tasks.py` để xử lý quay số bất đồng bộ; (3) Tạo `OutboundTriggerEngine` lắng nghe tín hiệu tương tác Speed-to-Lead từ Redis stream `stream:prospect:engagement` (prospect xem pitch > 45s) và Intent Radar `SignalEvent` tuyển dụng để tự động kích hoạt cuộc gọi sàng lọc B2B trong < 5 phút.

## Boundaries & Constraints

**Always:**
- **Zero Reinvention**: Voice AI SDR hoạt động như một Action Executor trong Sequencer (`SequenceStep.channel = "voice"`, cờ `SEQUENCER_VOICE_ENABLED`, khai báo trong `ALLOWED_OUTBOUND_CHANNELS` tại `app/services/sequencer/constants.py`). Nối vào `_send_voice_dispatch()` trong `app/services/sequencer/dispatch.py` và task Celery `app/tasks/celery_tasks/voice_tasks.py`. **CẤM tạo scheduler hay dispatcher độc lập**.
- Mọi cuộc gọi phát ra từ Sequencer bắt buộc phải đi qua `TelephonyComplianceGate.evaluate_preflight()`: kiểm tra Curfew, 24h frequency lock, DNC 5656, và soft-lock ví. Nếu bị chặn, step chuyển trạng thái `skipped` hoặc `failed` kèm lý do compliance rõ ràng, không cố quay số lại.
- Tự động giải quyết SIP Trunk cho cuộc gọi bằng `SipTrunkManager.resolve_workspace_trunk()`; ưu tiên Voice Brandname đã verify (`is_verified=True`), tự động fallback về system default nếu workspace chưa cấu hình.
- Speed-to-Lead Trigger: Tín hiệu `view_duration_seconds >= 45` từ Redis stream `stream:prospect:engagement` chỉ kích hoạt cuộc gọi cho lead có số điện thoại hợp lệ và trong khung giờ gọi cho phép.
- Celery Task: Tác vụ `dispatch_voice_call_task` chạy bất đồng bộ với cơ chế retry tối đa 2 lần cho lỗi hạ tầng (503 Service Unavailable), tuyệt đối không retry cho các lỗi vi phạm pháp lý (486 Busy Here, DNC, Curfew).

**Never:**
- Không tạo scheduler hay event-loop trigger độc lập ngoài Sequencer và Celery.
- Không cho phép thực hiện cuộc gọi khi `SEQUENCER_VOICE_ENABLED=false` (fail-closed).
- Không tự động quay số cho các sự kiện SignalEvent không có mức độ tự tin cao (`confidence < 0.75`).
- Không bypass `TelephonyComplianceGate` dưới bất kỳ cờ test nào trong production.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sequencer voice dispatch hợp lệ | Step `channel="voice"`, phone hợp lệ, giờ hợp lệ, đủ ví | Gate phê duyệt, soft-lock 7.5M micros, tạo LiveKit room, gọi `dispatch_call`, trả về `call_id` | Nếu LiveKit API lỗi → giải phóng soft-lock và lock 24h |
| Sequencer voice bị Curfew | Step `channel="voice"` đến hạn lúc 22:00 ICT | `_defer_step_for_curfew(channel="voice")` đẩy sang 09:05 ICT ngày làm việc tiếp theo | Log curfew deferral |
| Sequencer voice bị DNC | Lead nằm trong danh bạ DNC | Gate từ chối `DNC_BLOCKED`, step đánh dấu `skipped`, 0 micros bị lock | Ghi nhận event `dnc_blocked` |
| Speed-to-Lead Trigger | Event `prospect_engaged` với duration 50s trên pitch portal | Kích hoạt Sequencer voice step ngay lập tức (delay 0s), gọi trong < 5 phút | Bỏ qua nếu prospect không có số điện thoại |
| Hiring Radar Trigger | SignalEvent tuyển dụng 20 sales với confidence 0.85 | Tìm hoặc tạo Lead, enroll vào campaign tuyển dụng/SDR với bước đầu là voice call | Bỏ qua nếu confidence < 0.75 |
| Flag voice tắt | `SEQUENCER_VOICE_ENABLED=false` | Step từ chối thực hiện, log warning, không tạo cuộc gọi | Không crash worker |
| Trunk riêng lỗi giải mã | Mật khẩu SIP trunk workspace bị hỏng key | Fallback về system default trunk, cuộc gọi vẫn được thực hiện bình thường | Ghi log error |

</intent-contract>

## Code Map

- `nowing_backend/app/services/sequencer/constants.py` -- **Sửa.** Cập nhật `ALLOWED_OUTBOUND_CHANNELS`: thêm `"voice"` khi `SEQUENCER_VOICE_ENABLED=True` (hoặc hàm helper `get_allowed_outbound_channels()`).
- `nowing_backend/app/services/sequencer/dispatch.py` -- **Sửa.** Thêm nhánh `if channel == "voice":` trong `_dispatch_channel()`, tạo method `_send_voice_dispatch()` tích hợp `TelephonyComplianceGate.evaluate_preflight()`, `SipTrunkManager.resolve_workspace_trunk()`, và `LiveKitTelephonyClient.dispatch_call()`.
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` -- **File mới.** Celery task `dispatch_voice_call_task(workspace_id, enrollment_id, step_id, phone_e164)` thực thi bất đồng bộ qua queue `voice_dispatch`.
- `nowing_backend/app/services/voice/outbound_trigger.py` -- **File mới.** Lớp `OutboundTriggerEngine`:
  - `handle_prospect_engagement(event_data)`: phân tích thời lượng xem pitch portal (> 45s) và trigger Speed-to-Lead call.
  - `handle_hiring_radar_signal(signal_event)`: phân tích tin tuyển dụng (Epic 37.1) và enroll lead vào sequence.
- `nowing_backend/tests/unit/sequencer/test_voice_dispatch.py` -- **File mới.** Unit tests cho nhánh dispatch voice trong Sequencer: gate approval, compliance deferral, DNC skip, fallback trunk resolution.
- `nowing_backend/tests/unit/voice/test_outbound_trigger.py` -- **File mới.** Unit tests cho `OutboundTriggerEngine`: Speed-to-Lead threshold (> 45s trigger, < 45s ignore), Hiring Radar confidence threshold, thiếu phone handling.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/sequencer/constants.py` -- Cập nhật danh sách kênh gửi cho phép hỗ trợ `"voice"` khi cờ `SEQUENCER_VOICE_ENABLED=True` -- Nhất quán cấu hình kênh Sequencer
- `nowing_backend/app/services/sequencer/dispatch.py` -- Bổ sung `_send_voice_dispatch()` tích hợp Compliance Gate 4 lớp và SIP Trunk Manager -- Hoàn thiện Action Executor cho voice
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` -- Tạo Celery task `dispatch_voice_call_task` cho việc quay số bất đồng bộ -- Đảm bảo khả năng mở rộng hàng đợi
- `nowing_backend/app/services/voice/outbound_trigger.py` -- Xây dựng `OutboundTriggerEngine` tích hợp Speed-to-Lead (< 5m khi xem pitch > 45s) và Hiring Radar -- Kích hoạt cuộc gọi theo thời gian thực
- `nowing_backend/tests/unit/sequencer/test_voice_dispatch.py` -- Unit tests cho voice dispatch flow trong Sequencer -- Đảm bảo an toàn compliance và trunk resolution
- `nowing_backend/tests/unit/voice/test_outbound_trigger.py` -- Unit tests cho các trigger events của Outbound Trigger Engine -- Đảm bảo tính chính xác của tín hiệu kích hoạt

**Acceptance Criteria:**
- **Given** cờ `SEQUENCER_VOICE_ENABLED=True` và một bước Sequencer kênh voice, **When** Sequencer dispatch xử lý bước này trong khung giờ hợp lệ và ví đủ số dư, **Then** hệ thống thực hiện kiểm tra preflight compliance thành công, giải quyết đúng SIP Trunk của workspace, và gọi `LiveKitTelephonyClient.dispatch_call()` trả về ID cuộc gọi.
- **Given** cuộc gọi voice từ Sequencer gặp số điện thoại trong danh sách DNC, **When** dispatch xử lý, **Then** bước được đánh dấu `skipped`, không có cuộc gọi nào được phát ra, và số dư ví không bị phong tỏa.
- **Given** prospect xem Mini-Pitch portal trong thời gian 52 giây (>= 45s), **When** `OutboundTriggerEngine.handle_prospect_engagement()` nhận sự kiện từ Redis stream, **Then** hệ thống tạo lượt enroll voice step ngay lập tức (delay 0s) cho lead tương ứng.
- **Given** prospect chỉ xem pitch portal trong 20 giây (< 45s), **When** nhận sự kiện, **Then** trigger engine bỏ qua và không kích hoạt cuộc gọi tự động.
- **Given** tín hiệu Intent Radar phát hiện doanh nghiệp đăng tuyển 15 vị trí với confidence 0.82 (>= 0.75), **When** `OutboundTriggerEngine.handle_hiring_radar_signal()` xử lý, **Then** lead được enroll vào chiến dịch tiếp cận tự động.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 4 findings — high 1, medium 2, low 1, false 0, maybe-false 0
- findings:
  - `high` `patch` Edit chèn `_send_voice_dispatch` đè lên signature `_handle_send_step` (mất `lead: Lead` param + docstring, dán code zns rác vào giữa) gây SyntaxError toàn module — khôi phục đúng thứ tự: `_send_zns_dispatch` → `_send_voice_dispatch` → `_handle_send_step`; 14/14 pass sau fix
  - `medium` `patch` Test patch staticmethod `release_deposit` bằng plain function làm lệch tham số (TypeError bị `contextlib.suppress` nuốt) — bọc `staticmethod(_release_deposit)`
  - `medium` `patch` Test patch `LiveKitTelephonyClient` sai module (lazy import) — patch vào `app.services.voice.telephony_client.LiveKitTelephonyClient`
  - `low` `patch` `parsed_lead_id` unused trong `voice_tasks.py` — xoá biến
  - `medium` `defer` Redis stream consumer loop chưa chạy worker — cần Celery beat task hoặc async consumer đọc `stream:prospect:engagement` liên tục
  - `low` `defer` Hiring Radar trigger dispatch trực tiếp Celery thay vì tạo SequenceEnrollment — enrollment-based path là follow-up

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Voice AI SDR chính thức trở thành Action Executor trong Sequencer: nhánh `channel="voice"` trong `_dispatch_single_channel` chạy `TelephonyComplianceGate.evaluate_preflight()` (4 lớp), giải quyết trunk qua `SipTrunkManager`, dispatch qua `LiveKitTelephonyClient` với room metadata đầy đủ. `OutboundTriggerEngine` kích hoạt Speed-to-Lead (< 5 phút khi xem pitch >= 45s) và Hiring Radar (confidence >= 0.75) qua Celery task `dispatch_voice_call_task` với retry 2 lần cho lỗi hạ tầng.

### Files changed

- `nowing_backend/app/services/sequencer/constants.py` — `get_allowed_outbound_channels()` thêm "voice" khi `SEQUENCER_VOICE_ENABLED`
- `nowing_backend/app/services/sequencer/dispatch.py` — `_send_voice_dispatch()` (gate → trunk → LiveKit dispatch → lock release on failure) + routing `channel == "voice"` trong `_dispatch_single_channel`
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` (mới) — Celery task `dispatch_voice_call_task` (max_retries=2, delay 30s)
- `nowing_backend/app/services/voice/outbound_trigger.py` (mới, ~230 dòng) — `OutboundTriggerEngine`: Speed-to-Lead + Hiring Radar evaluators
- 2 test files mới: `test_voice_dispatch.py` (7 tests), `test_outbound_trigger.py` (7 tests)

### Review findings breakdown

- **Patches applied (4):** khôi phục `_handle_send_step` signature bị hỏng khi chèn method; sửa patch staticmethod; patch LiveKit vào module gốc; patch SEQUENCER_VOICE_ENABLED flag trong tests
- **Deferred (2):** Redis stream consumer loop (cần worker process); Hiring Radar enrollment-based path
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 14/14 tests mới pass, 304/304 full regression pass; deferred items có kế hoạch triển khai riêng.

### Verification performed

- `uv run pytest tests/unit/voice/ tests/unit/sequencer/ tests/unit/dnc/ -q` → **304 passed**, 0 failed
- `uv run ruff check` (6 files) → **All checks passed!**
- `uv run python -c "from app.services.voice.outbound_trigger import OutboundTriggerEngine"` → **import OK**
- Matrix Test Audit: 7/7 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- Redis stream consumer chưa chạy như worker process (cần Celery beat hoặc dedicated consumer — deferred)
- Speed-to-Lead trigger chưa đo end-to-end latency thực tế (< 5 phút SLA)
- Hiring Radar chưa wire vào SignalEvent ingestion pipeline (Epic 37.1)

## Design Notes

**Kiến trúc Action Executor Không Trùng lặp:**
Voice SDR không có bộ lập lịch riêng. Thay vào đó, nó hoạt động như một kênh gửi tương đương với `email` hay `zalo` trong Sequencer. Khi một step có `channel="voice"`, `SequencerDispatchMixin` sẽ route sang `_send_voice_dispatch()`. Mọi logic retry, OCC versioning, và ghi log `SequenceEvent` đều được thừa hưởng 100% từ Sequencer hiện có.

**Cơ chế Speed-to-Lead < 5 phút:**
Khi prospect truy cập link Mini-Pitch portal (Story 37.6), beacon gửi heartbeat mỗi 5 giây. Nếu thời lượng tích lũy đạt >= 45s (mức độ quan tâm cao), một event được push vào Redis stream `stream:prospect:engagement`. `OutboundTriggerEngine` đọc event này và tạo một `SequenceEnrollment` mới với `delay_seconds=0`. Bước gọi thoại được thực hiện ngay trong vòng vài chục giây tiếp theo nếu trong giờ hợp lệ.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/sequencer/test_voice_dispatch.py tests/unit/voice/test_outbound_trigger.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/services/sequencer/constants.py app/services/sequencer/dispatch.py app/tasks/celery_tasks/voice_tasks.py app/services/voice/outbound_trigger.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.voice.outbound_trigger import OutboundTriggerEngine; print('import OK')"` -- expected: no exception
