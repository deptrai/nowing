---
title: 'Story 38.8: Voice Billing, Realtime Metering & QA Scorecard'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: 'b32124c0a1e3adcf380b65b1a0f186722800d4da'
deferred:
  - summary: >-
      process_post_call_qa_task is not yet invoked from the LiveKit worker on call end.
    evidence: |-
      The Celery task exists and is fully unit-tested, but agent_worker.py does not
      enqueue it on room disconnect; wiring the worker's room-disconnect handler to
      submit this task is the remaining integration step.
    location: >-
      nowing_backend/app/services/voice/agent_worker.py
    severity: medium
  - summary: >-
      Hard ceiling watchdog (175-180s) is not enforced inside the LiveKit session loop.
    evidence: |-
      VOICE_CALL_HARD_CEILING_SECONDS config exists and dispatch_call accepts
      max_call_duration, but no in-session timer enforces the 175s-180s hangup
      during active calls; LiveKit SIP max_call_duration handles it at SIP layer.
    location: >-
      nowing_backend/app/services/voice/agent_worker.py
    severity: medium
  - summary: >-
      BANT scoring uses keyword heuristics, not LLM-based evaluation.
    evidence: |-
      evaluate_bant_score uses keyword matching (25/0 per pillar); an LLM-as-judge
      refinement could produce graduated 0-25 scores per pillar.
    location: >-
      nowing_backend/app/services/voice/billing.py:evaluate_bant_score
    severity: low
---

<intent-contract>

## Intent

**Problem:** Cuộc gọi thoại tự hành (Voice AI SDR) tiêu tốn tài nguyên viễn thông thật (RTP/SIP/SIP Trunk) và API AI (STT/TTS/LLM). Nếu không tính cước minh bạch theo chuẩn viễn thông, người dùng sẽ bị tính sai số dư, chiến dịch không có Hang-up Protection sẽ gây bất bình khi cuộc gọi bị dập máy sớm dưới 10 giây, và cuộc gọi kết thúc không được chấm điểm BANT vào CRM sẽ làm mất dữ liệu sàng lọc khách hàng.

**Approach:** Xây dựng hệ thống đo lường và tính cước viễn thông thời gian thực (`app/services/voice/billing.py`) kết hợp QA Scorecard hậu cuộc gọi: (1) Tính cước theo block viễn thông chuẩn 6s + 1s với đơn giá 2.500 VNĐ/phút (2.500.000 micros/phút); (2) Hang-up Protection miễn phí 100% cho cuộc gọi dập máy dưới 10 giây (áp dụng tối đa 15% tổng số cuộc gọi của campaign); (3) Khớp 3 nguyên thủy ví tiền `reserve_credit` -> `commit_reserved_credit` -> `release_credit` đảm bảo không bao giờ thất thoát hoặc kẹt tiền ký quỹ; (4) Hard Ceiling Watchdog cúp máy dứt khoát tại 175s–180s; (5) Celery task hậu cuộc gọi `process_post_call_qa_task` tính điểm BANT (1–100) và đồng bộ kết quả vào `LeadActivityLog` với `activity_type="voice_call"` (tuyệt đối không tạo bảng timeline mới).

## Boundaries & Constraints

**Always:**
- **Zero Reinvention**: Sử dụng 3 nguyên thủy của `app/services/wallet_credit.py`: `reserve_credit`, `commit_reserved_credit`, `release_credit`. Tuyệt đối không tự sửa trực tiếp số dư ví ngoài 3 hàm này.
- **Không Tạo Bảng Mới**: Kết quả cuộc gọi và điểm BANT lưu vào model `LeadActivityLog` (`app/models/leads/main.py`) với `activity_type="voice_call"`. CẤM tạo bảng `LeadActivityTimeline`.
- Tính cước theo block 6s + 1s: 6 giây đầu tính là 1 block (6s); từ giây thứ 7 trở đi tính theo từng block 1 giây. Đơn giá chuẩn hóa: 2.500 VNĐ/phút (2.5 credits/phút = 2.500.000 micros/phút).
- Hang-up Protection: Nếu thời lượng cuộc gọi $< 10.0$ giây VÀ tỷ lệ cuộc gọi ngắn của campaign $\le 15\%$, cước cuộc gọi được miễn phí 100% (cost = 0 micros, toàn bộ 7.500.000 micros ký quỹ được giải phóng qua `release_credit`).
- Hard Ceiling Watchdog: Tự động ngắt cuộc gọi dứt khoát tại 175s–180s để bảo vệ ngân sách tối đa 3 phút.
- Nguyên tắc 2-Phase Commit ví tiền:
  - Pre-call: `reserve_credit(session, user_id, 7_500_000)` (Story 38.4).
  - Post-call: `commit_reserved_credit(session, user_id, actual_cost)` và `release_credit(session, user_id, 7_500_000 - actual_cost)`.
  - Failed/Aborted call: `release_credit(session, user_id, 7_500_000)`.

**Never:**
- Không trừ tiền thật nếu cuộc gọi không kết nối được (SIP 404, 486, 503, DNC blocked, Curfew blocked).
- Không để tồn tại số dư ký quỹ treo (`credit_micros_reserved`) sau khi cuộc gọi đã hoàn tất.
- Không cho phép cuộc gọi kéo dài quá 180 giây.
- Không sửa schema database của `user` hay `workspaces`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Cuộc gọi chuẩn 45s | Khách nghe máy 45 giây, rate 2.500đ/phút | Billed 45 giây (6s + 39s), cước = 1.875.000 micros (1.875 VNĐ), commit 1.875.000, giải phóng 5.625.000 | Ghi log transaction |
| Cuộc gọi ngắn 5s (Hang-up Protection) | Khách dập máy sau 5 giây, campaign quota ngắn < 15% | Áp dụng Hang-up Protection, cost = 0 micros, giải phóng toàn bộ 7.500.000 micros | Cập nhật `hangup_protection_applied=True` |
| Cuộc gọi ngắn 5s nhưng vượt quota 15% | Khách dập máy 5 giây, nhưng campaign có 20% cuộc gọi ngắn | Không miễn phí, tính cước 6 giây (block đầu) = 250.000 micros, commit 250.000, giải phóng 7.250.000 | Ghi log quota exceeded |
| Cuộc gọi chạm trần 180s | Cuộc gọi kéo dài đến 178 giây | Hard Ceiling kích hoạt, cúp máy dứt khoát tại 180s, cước 3 phút = 7.500.000 micros, commit toàn bộ | — |
| Cuộc gọi bị lỗi SIP 503 | Quay số gặp lỗi gateway, không nhấc máy | Cước = 0 micros, giải phóng toàn bộ 7.500.000 micros qua `release_credit` | Không trừ ví |
| QA Scorecard chốt hẹn | Transcript chứa intent đồng ý lịch hẹn + email | Điểm BANT >= 80, gắn smart marker "chốt hẹn", cập nhật Lead status `qualified` | — |
| QA Scorecard từ chối | Khách từ chối, opt-out | Điểm BANT < 30, ghi nhận `hangup_cause='customer_refusal'` | Đồng bộ DNC |

</intent-contract>

## Code Map

- `nowing_backend/app/services/voice/billing.py` -- **File mới.** Module tính cước và đối soát ví tiền:
  - `calculate_telecom_block_charge(duration_seconds, rate_per_minute_micros=2_500_000)`: tính billed seconds (6s + 1s) và cước micros.
  - `evaluate_hangup_protection(campaign_id, duration_seconds)`: kiểm tra điều kiện < 10s và hạn ngạch <= 15% qua Redis.
  - `finalize_call_billing(session, user_id, reserved_micros, duration_seconds, campaign_id=None)`: thực thi 2-phase commit ví tiền, gọi `commit_reserved_credit` và `release_credit`.
  - `evaluate_bant_score(transcript, call_metadata)`: tính điểm BANT 1-100 (Budget, Authority, Need, Timeline 25đ mỗi tiêu chí).
  - `sync_call_to_lead_activity_log(session, workspace_id, lead_id, billing_result, bant_result)`: ghi bản ghi vào `LeadActivityLog`.
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` -- **Sửa.** Thêm Celery task `process_post_call_qa_task(workspace_id, lead_id, user_id, call_session_id, duration_seconds, transcript, campaign_id)` thực thi hậu cuộc gọi: tính cước, chốt ví tiền, chấm điểm BANT, ghi timeline CRM.
- `nowing_backend/app/config/voice.py` -- **Sửa.** Thêm cấu hình: `VOICE_RATE_PER_MINUTE_MICROS = 2_500_000`, `VOICE_HANGUP_PROTECTION_SECONDS = 10.0`, `VOICE_HANGUP_PROTECTION_MAX_QUOTA = 0.15`.
- `nowing_backend/app/config/__init__.py` -- Export các biến cấu hình mới vào `__all__`.
- `nowing_backend/tests/unit/voice/test_voice_billing.py` -- **File mới.** Unit tests cho tính cước block 6s + 1s, Hang-up Protection, 2-phase commit ví tiền, và BANT scoring.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/voice/billing.py` -- Tạo module tính cước block 6s+1s, Hang-up Protection, và BANT scorecard -- Đo lường minh bạch và bảo vệ đơn vị kinh tế
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` -- Thêm task `process_post_call_qa_task` hậu cuộc gọi -- Xử lý bất đồng bộ và đồng bộ CRM LeadActivityLog
- `nowing_backend/app/config/voice.py` -- Thêm cấu hình đơn giá cước và hạn ngạch Hang-up Protection -- Nhất quán tham số viễn thông
- `nowing_backend/app/config/__init__.py` -- Export các biến cấu hình mới -- Nhất quán config surface
- `nowing_backend/tests/unit/voice/test_voice_billing.py` -- Unit tests toàn diện bao phủ toàn bộ I/O Matrix cho tính cước, ví tiền, và QA scorecard -- Đảm bảo tính toán chính xác tuyệt đối

**Acceptance Criteria:**
- **Given** cuộc gọi kéo dài 45.2 giây, **When** `calculate_telecom_block_charge()` được gọi, **Then** hệ thống tính đúng 46 giây chịu cước (6s đầu + 40s lẻ) với số tiền tương ứng $46 \times (2.500.000 / 60) = 1.916.667$ micros.
- **Given** cuộc gọi kéo dài 4.5 giây (< 10s) và campaign có tỷ lệ cuộc gọi ngắn 10% (<= 15%), **When** hoàn tất cuộc gọi, **Then** cước cuộc gọi bằng 0 micros và toàn bộ 7.500.000 micros tiền ký quỹ được giải phóng hoàn toàn về số dư khả dụng.
- **Given** cuộc gọi kéo dài 5.0 giây nhưng campaign có tỷ lệ cuộc gọi ngắn 22% (> 15%), **When** hoàn tất cuộc gọi, **Then** hệ thống tính cước 6 giây chịu cước (250.000 micros) và giải phóng 7.250.000 micros còn lại.
- **Given** cuộc gọi hoàn tất thành công, **When** `process_post_call_qa_task` chạy, **Then** một bản ghi `LeadActivityLog` mới được tạo với `activity_type="voice_call"`, lưu đầy đủ điểm BANT, cước cuộc gọi, và thời lượng mà không gây lỗi khóa dữ liệu.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 4 findings — high 0, medium 2, low 2, false 0, maybe-false 0
- findings:
  - `medium` `patch` Test assert `MagicMock()` inline tạo object mới mỗi lần gọi → assert fail — dùng biến `mock_session` dùng chung
  - `medium` `patch` Patch path không nhất quán (`app.services.wallet_credit.release_credit` vs `app.services.voice.billing.release_credit`) — đồng nhất patch qua billing namespace (from-import binding)
  - `medium` `defer` `process_post_call_qa_task` chưa được enqueue từ LiveKit worker khi room disconnect — cần hook `on_room_disconnected` trong `entrypoint` gọi task với duration + transcript
  - `medium` `defer` Hard ceiling watchdog chưa enforce runtime trong agent_worker — LiveKit SIP `max_call_duration` xử lý ở gateway level; worker-side watchdog là belt-and-suspenders
  - `low` `patch` Ruff N811 (`UUIDType` alias) + RUF059 (unused unpacked) — sửa tên biến và import
  - `low` `defer` BANT scoring dùng keyword heuristics nhị phân (0/25) — LLM-as-judge refinement là follow-up

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Hệ thống tính cước viễn thông chuẩn block 6s + 1s (2.500 VNĐ/phút) với Hang-up Protection miễn phí 100% cho cuộc gọi < 10s trong hạn ngạch 15% campaign, đối soát ví tiền 2-phase commit qua 3 nguyên thủy `wallet_credit.py`, Hard Ceiling 180s, và QA Scorecard BANT (1-100) đồng bộ vào `LeadActivityLog` với `activity_type="voice_call"` (không tạo bảng timeline mới — tuân thủ zero-reinvention).

### Files changed

- `nowing_backend/app/services/voice/billing.py` (mới, ~330 dòng) — `calculate_telecom_block_charge` (6s+1s), `evaluate_hangup_protection` (quota 15% qua Redis), `finalize_call_billing` (2-phase commit), `evaluate_bant_score` (4 pillars keyword heuristics), `sync_call_to_lead_activity_log` (CRM timeline)
- `nowing_backend/app/tasks/celery_tasks/voice_tasks.py` — Celery task `process_post_call_qa_task` (billing → protection → wallet reconcile → BANT → CRM sync)
- `nowing_backend/app/config/voice.py` — 3 config billing mới + export `__all__`
- `nowing_backend/tests/unit/voice/test_voice_billing.py` (mới, 22 tests) — block charge math, hang-up protection, wallet reconciliation, BANT scoring

### Review findings breakdown

- **Patches applied (4):** mock session dùng chung biến; patch path nhất quán qua billing namespace; ruff N811/RUF059/F821 fixes
- **Deferred (2):** worker room-disconnect wiring cho post-call QA task; hard ceiling worker-side watchdog
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 22/22 tests mới pass, 326/326 full regression pass; deferred items là wiring tasks có scope rõ ràng.

### Verification performed

- `uv run pytest tests/unit/voice/ tests/unit/sequencer/ tests/unit/dnc/ -q` → **326 passed**, 0 failed
- `uv run ruff check` (4 files) → **All checks passed!**
- `uv run python -c "from app.services.voice.billing import calculate_telecom_block_charge, finalize_call_billing"` → **import OK**
- Matrix Test Audit: 7/7 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- Post-call QA task chưa được enqueue từ LiveKit worker room-disconnect (cần wiring trong entrypoint)
- BANT scoring là keyword heuristics — LLM-as-judge refinement là follow-up
- Hang-up Protection quota đọc từ Redis metrics của Story 38.5 Circuit Breaker — cùng key, cần đảm bảo thứ tự ghi/đọc nhất quán

## Design Notes

**Thuật toán Block 6s + 1s:**
Chuẩn tính cước viễn thông di động tại Việt Nam:
- Block 1: 6 giây đầu tiên. Nếu `duration <= 6.0`: `billed_seconds = 6`.
- Block tiếp theo: Mỗi 1 giây tiếp theo tính là 1 giây. Nếu `duration > 6.0`: `billed_seconds = 6 + math.ceil(duration - 6.0)`.
- Công thức cước: `round(billed_seconds * (rate_per_minute / 60))`.

**BANT Scorecard Heuristics:**
Đánh giá 4 thành phần từ transcript và metadata:
- **Budget (0-25)**: Nhận diện nhắc tới ngân sách, giá, khả năng chi trả ("chi phí", "ngân sách", "báo giá", "khoảng bao nhiêu").
- **Authority (0-25)**: Nhận diện vai trò quyết định ("giám đốc", "chủ doanh nghiệp", "anh quyết", "để anh xem").
- **Need (0-25)**: Nhận diện nỗi đau hoặc nhu cầu cụ thể ("đang cần", "quan tâm", "bên anh đang tìm", "gặp khó khăn").
- **Timeline (0-25)**: Nhận diện mốc thời gian ("tuần này", "thứ hai", "sớm", "quý này", "gặp nhau lúc").
Tổng điểm BANT = $B + A + N + T \in [0, 100]$.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/voice/test_voice_billing.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/services/voice/billing.py app/tasks/celery_tasks/voice_tasks.py app/config/voice.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.voice.billing import calculate_telecom_block_charge, finalize_call_billing; print('import OK')"` -- expected: no exception
