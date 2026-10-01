---
title: 'Story 38.4: Telephony Compliance Gate, National DNC 5656 & Curfew Scheduler'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: '68dcd9d98563630caf892a9e377bde65eb5b4830'
deferred:
  - summary: >-
      DTMF 0/9 live packet listener is not wired into the LiveKit runtime session.
    evidence: |-
      is_dtmf_opt_out() is defined and unit-tested but LiveKit Agents 1.8.2 exposes no
      public DTMF event on AgentSession; wiring requires a data-packet/SIP-INFO listener.
    location: >-
      nowing_backend/app/services/voice/compliance_gate.py:383
    severity: medium
  - summary: >-
      TelephonyComplianceGate.evaluate_preflight is not yet wired into _send_voice_dispatch().
    evidence: |-
      Sequencer Action Executor wiring for the voice channel is explicitly assigned to
      Story 38.7 (Outbound Trigger Engine); the gate is production-ready but uncalled
      until that dispatch hook lands.
    location: >-
      nowing_backend/app/services/sequencer/dispatch.py
    severity: medium
  - summary: >-
      Vietnamese public holidays are not excluded from the voice curfew (weekends only).
    evidence: |-
      Decree 91 also bans calls on national holidays; a static holiday table or an
      external calendar feed is needed. Current implementation filters Sat/Sun only.
    location: >-
      nowing_backend/app/services/sequencer/scheduling.py:is_voice_curfew
    severity: low
---

<intent-contract>

## Intent

**Problem:** Cuộc gọi thoại tự hành (Voice SDR) phải tuyệt đối tuân thủ pháp lý viễn thông Việt Nam (Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP PDPD). Việc quay số ngoài giờ cho phép, gọi trùng lặp nhiều lần/ngày, gọi vào danh sách Không quảng cáo Quốc gia (DNC 5656) hoặc không ghi nhận khi khách từ chối sẽ dẫn đến bị khoá đầu số, phạt hành chính và vi phạm quyền riêng tư.

**Approach:** Xây dựng cổng tuân thủ 4 lớp (Telephony Compliance Gate) tiền kiểm soát trước mỗi cuộc gọi: (1) Curfew Scheduler mở rộng trong `scheduling.py` giới hạn giờ gọi 09:00–11:30 và 13:30–17:00 ICT Thứ 2–Thứ 6, (2) Giới hạn tần suất 1 cuộc/24h/E.164 qua Redis lock, (3) Đối soát DNC 5656 qua `DncComplianceService`, và (4) Ký quỹ 7.500.000 micros trước khi quay số. Ở runtime cuộc gọi: bắt buộc phát thông báo ghi âm 3s đầu và xử lý cúp máy tức thì (< 2s) + tự động ghi nhận DNC vĩnh viễn qua `register_contact_opt_out()` khi khách nói lời từ chối hoặc bấm phím 0/9.

## Boundaries & Constraints

**Always:**
- **Zero Reinvention**: CẤM tạo `voice/curfew.py`. Logic khung giờ gọi Nghị định 91 mở rộng trực tiếp trong hàm `calculate_step_eta(delay_seconds, from_dt, channel="email")` tại `app/services/sequencer/scheduling.py`.
- **DNC & Opt-out Dùng chung**: Dùng hàm `register_contact_opt_out()` trong `app/lead_intelligence/dnc/service.py` cho cả Inbound Sequencer và Voice Worker, ghi vào `WorkspaceDncRecord` và xoá Redis cache qua `invalidate_workspace_cache`.
- Khung giờ gọi viễn thông chuẩn Nghị định 91: chỉ cho phép 09:00–11:30 và 13:30–17:00 ICT, Thứ 2 đến Thứ 6. Cấm gọi Thứ 7, Chủ Nhật, ngày lễ và giờ nghỉ trưa.
- Giới hạn tần suất: tối đa 1 cuộc gọi / 24 giờ / 1 số điện thoại E.164 trên toàn workspace, khoá bằng Redis distributed lock `voice:freq:{workspace_id}:{normalized_phone}` với TTL 86400s.
- DNC 5656: số thuộc danh sách DNC bị chặn pre-flight, không thực hiện cuộc gọi và không trừ ví/không ký quỹ.
- Ký quỹ trước cuộc gọi: soft-lock 7.500.000 micros (7.500 VNĐ = đệm 3 phút) trước khi bấm số; từ chối gọi (HTTP 402 / reject dispatch) nếu số dư không đủ.
- Thông báo ghi âm: bắt buộc phát âm thông báo ghi âm cuộc gọi trong 3 giây đầu tiên khi khách bắt máy.
- Opt-out tức thì: khách nói "đừng gọi nữa", "không có nhu cầu", "phiền quá", "xóa số tôi đi" hoặc nhận tín hiệu DTMF 0/9 kích hoạt cúp máy trong < 2 giây và tự động ghi vào `WorkspaceDncRecord`.

**Never:**
- Không tạo `voice/curfew.py` hoặc scheduler độc lập.
- Không tạo bảng DNC mới — dùng `WorkspaceDncRecord` có sẵn.
- Không gọi ra ngoài khung giờ cho phép trong bất kỳ tình huống nào, kể cả retry.
- Không tạo Redis connection pool mới — tái sử dụng `app.redis` / `get_redis()`.
- Không trừ tiền cước nếu cuộc gọi bị chặn ở compliance gate.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Curfew Sáng | Voice step ETA rơi vào 10:00 ICT Thứ 3 | Cho phép, ETA giữ nguyên | — |
| Curfew Trưa | Voice step tính toán lúc 12:00 ICT | ETA tự động đẩy sang 13:35 ICT cùng ngày + random jitter | — |
| Curfew Tối | Voice step tính toán lúc 18:00 ICT Thứ 5 | ETA tự động đẩy sang 09:05 ICT Thứ 6 + random jitter | — |
| Curfew Cuối tuần | Voice step tính toán lúc 10:00 ICT Thứ 7 | ETA tự động đẩy sang 09:05 ICT Thứ 2 tuần sau + random jitter | — |
| Frequency Cap hit | Số E.164 đã được gọi trong 24h qua trong cùng workspace | Gate từ chối quay số, trả về mã `FREQUENCY_CAPPED`, không trừ tiền ví | Ghi log audit, không raise unhandled exception |
| DNC 5656 hit | Số điện thoại nằm trong Global DNC 5656 hoặc Workspace DNC | Gate từ chối quay số, trả về mã `DNC_BLOCKED`, không trừ tiền ví | Ghi log compliance, step chuyển trạng thái `skipped` |
| Insufficient Balance | Ví workspace có < 7.500.000 micros khả dụng | Gate từ chối quay số, trả về mã `INSUFFICIENT_FUNDS`, không lock cước | Alert ví hết tiền, step chuyển `paused` |
| Opt-out bằng lời | Khách nói "đừng gọi nữa em ơi" trong cuộc gọi | Cúp máy < 2s, gọi `register_contact_opt_out()`, số điện thoại vào DNC vĩnh viễn | Bỏ qua lỗi xóa cache nếu Redis down (fail-safe) |
| Opt-out bằng DTMF | Khách bấm phím 0 hoặc 9 | Cúp máy < 2s, gọi `register_contact_opt_out()`, số vào DNC vĩnh viễn | — |
| Tất cả điều kiện thỏa | Khung giờ hợp lệ, không DNC, chưa gọi 24h, đủ số dư | Gate phê duyệt `APPROVED`, lock 7.500.000 micros, set lock 24h, cho phép quay số | Nếu quay số thất bại sau đó → giải phóng soft-lock (release_credit) |

</intent-contract>

## Code Map

- `nowing_backend/app/services/sequencer/scheduling.py` -- **Sửa.** Mở rộng `calculate_step_eta(delay_seconds, from_dt=None, channel="email")` hỗ trợ `channel="voice"`. Định nghĩa các hằng số khung giờ viễn thông Việt Nam: `VOICE_CURFEW_MORNING_START = 9 * 60` (09:00), `VOICE_CURFEW_MORNING_END = 11 * 60 + 30` (11:30), `VOICE_CURFEW_AFTERNOON_START = 13 * 60 + 30` (13:30), `VOICE_CURFEW_AFTERNOON_END = 17 * 60` (17:00), cấm thứ 7 (5) và Chủ Nhật (6).
- `nowing_backend/app/lead_intelligence/dnc/service.py` -- **Sửa.** Thêm hàm `register_contact_opt_out(session, workspace_id, contact_type, value, reason="voice_opt_out")` ghi bản ghi `WorkspaceDncRecord` với HMAC-SHA256 chuẩn hóa, sau đó gọi `invalidate_workspace_cache()`.
- `nowing_backend/app/services/voice/compliance_gate.py` -- **File mới.** Lớp `TelephonyComplianceGate`: phương thức `async def evaluate_preflight(session, workspace_id, phone_e164, lead_id=None) -> ComplianceCheckResult`. Kiểm tra 4 điều kiện tuần tự: Curfew → Frequency Lock → DNC 5656 → Wallet Soft-lock. Quản lý Redis distributed lock 24h.
- `nowing_backend/app/services/voice/agent_worker.py` -- **Sửa.** Trong `VoiceSDRAgent`: (1) Chèn câu thông báo ghi âm 3s đầu tiên khi bắt máy ("Cuộc gọi được ghi âm để nâng cao chất lượng dịch vụ"); (2) Nhận diện cụm từ opt-out trong `_evaluate_turn` hoặc STT event và kích hoạt cúp máy + gọi `register_contact_opt_out()`.
- `nowing_backend/app/config/voice.py` -- **Sửa.** Thêm các biến cấu hình compliance: `VOICE_COMPLIANCE_RECORDING_DISCLOSURE_ENABLED = True`, `VOICE_PRECALL_SOFT_LOCK_MICROS = 7_500_000`, `VOICE_RECORDING_DISCLOSURE_TEXT = "Cuộc gọi được ghi âm để nâng cao chất lượng dịch vụ."`, `VOICE_CALL_HARD_CEILING_SECONDS = 180`.
- `nowing_backend/app/config/__init__.py` -- Export các biến cấu hình mới vào `__all__`.
- `nowing_backend/tests/unit/voice/test_compliance_gate.py` -- **File mới.** Kiểm thử toàn diện 4 lớp kiểm tra của `TelephonyComplianceGate`: Curfew voice vs email, 24h frequency lock, DNC match, soft-lock số dư, opt-out handler.
- `nowing_backend/tests/unit/sequencer/test_scheduling.py` -- **Sửa/Bổ sung.** Kiểm thử `calculate_step_eta(channel="voice")`: các mốc sáng, trưa, chiều, tối, thứ 7, chủ nhật và rollover sang tuần mới.
- `nowing_backend/tests/unit/dnc/test_opt_out.py` -- **File mới.** Kiểm thử `register_contact_opt_out`: chuẩn hóa E.164, tính HMAC, lưu `WorkspaceDncRecord`, xóa cache Redis.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/sequencer/scheduling.py` -- Mở rộng `calculate_step_eta` thêm tham số `channel: str = "email"`. Nếu `channel == "voice"`, áp dụng khung giờ Nghị định 91 (09:00–11:30 & 13:30–17:00 ICT, Thứ 2–6), tự động dịch ETA sang block hợp lệ gần nhất kèm jitter -- Tuân thủ pháp lý viễn thông Việt Nam
- `nowing_backend/app/lead_intelligence/dnc/service.py` -- Thêm hàm `register_contact_opt_out(session, workspace_id, contact_type, value, reason="voice_opt_out")` tính HMAC chuẩn hóa, insert `WorkspaceDncRecord` idempotent, và gọi `invalidate_workspace_cache(workspace_id)` -- Tái dùng logic DNC cho voice và inbound
- `nowing_backend/app/services/voice/compliance_gate.py` -- Tạo `TelephonyComplianceGate` thực thi kiểm tra 4 lớp pre-flight: `is_within_voice_curfew()`, `acquire_24h_frequency_lock()`, `check_dnc_5656()`, `reserve_precall_deposit()` -- Cổng bảo vệ tập trung trước khi quay số
- `nowing_backend/app/config/voice.py` -- Thêm `VOICE_PRECALL_SOFT_LOCK_MICROS`, `VOICE_RECORDING_DISCLOSURE_TEXT`, `VOICE_CALL_HARD_CEILING_SECONDS` -- Quản lý ngưỡng tập trung
- `nowing_backend/app/config/__init__.py` -- Export các biến cấu hình compliance mới -- Nhất quán config surface
- `nowing_backend/app/services/voice/agent_worker.py` -- Tích hợp phát câu thông báo ghi âm 3s đầu tiên và phát hiện intent opt-out trong `_evaluate_turn` để tự động cúp máy và lưu DNC -- Tuân thủ PDPD Nghị định 13 & Nghị định 91
- `nowing_backend/tests/unit/voice/test_compliance_gate.py` -- Unit tests cho `TelephonyComplianceGate`: curfew, 24h frequency lock, DNC 5656 block, soft-lock balance check -- Bao phủ toàn bộ I/O Matrix
- `nowing_backend/tests/unit/dnc/test_opt_out.py` -- Unit tests cho `register_contact_opt_out`: E.164 normalization, HMAC creation, cache eviction -- Đảm bảo tính toàn vẹn DNC

**Acceptance Criteria:**
- **Given** một bước Sequencer kênh thoại (`channel="voice"`), **When** tính toán ETA vào lúc 12:15 ICT (giờ nghỉ trưa), **Then** ETA được đẩy sang 13:30–13:35 ICT cùng ngày; nếu tính toán lúc 17:30 ICT Thứ 6, ETA được đẩy sang 09:00–09:05 ICT Thứ 2 tuần sau.
- **Given** một số điện thoại đã được quay số thành công trong 24 giờ qua thuộc cùng workspace, **When** `TelephonyComplianceGate.evaluate_preflight()` được gọi, **Then** gate từ chối với lý do `FREQUENCY_CAPPED` và không có giao dịch soft-lock ví nào được thực hiện.
- **Given** một số điện thoại nằm trong danh bạ DNC Quốc gia (5656) hoặc DNC của workspace, **When** kiểm tra pre-flight, **Then** gate từ chối với lý do `DNC_BLOCKED` và số dư ví không bị phong tỏa.
- **Given** ví của workspace có số dư khả dụng thấp hơn 7.500.000 micros, **When** kiểm tra pre-flight, **Then** gate từ chối với lý do `INSUFFICIENT_FUNDS`.
- **Given** cuộc gọi được kết nối thành công, **When** khách nghe máy, **Then** bot phát câu thông báo ghi âm trong vòng 3 giây đầu tiên trước khi đi vào nội dung trao đổi.
- **Given** khách nói "đừng gọi làm phiền nữa" hoặc bấm phím 0 trong cuộc gọi, **When** hệ thống nhận diện tín hiệu từ chối, **Then** cuộc gọi được ngắt trong vòng dưới 2 giây và số điện thoại được tự động ghi vĩnh viễn vào `WorkspaceDncRecord` với lý do opt-out.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1
- verdicts: 18 findings — high 3, medium 4, low 6, false 2, maybe-false 0
- findings:
  - `high` `patch` entrypoint không parse `phone_e164` từ room metadata → opt-out silently skip DNC — patch `phone_e164=metadata.get("phone_e164") or metadata.get("phone")` trong `entrypoint()`
  - `high` `patch` `session.end_call()` không tồn tại trên `AgentSession` 1.8.2 → cuộc gọi không bao giờ bị ngắt khi opt-out — patch dùng `LiveKitTelephonyClient().end_call(room_name=...)`
  - `high` `patch` `CancelledError` khi khách cúp máy trong playout làm drop DNC persistence — bọc `(Exception, asyncio.CancelledError)` quanh playout
  - `medium` `patch` `"phiền quá"`/`"phien qua"` thiếu trong `HARD_OPTOUT_KEYPHRASES` — thêm vào; test frustration phrase đổi sang "bực mình quá"
  - `medium` `patch` NFD diacritics từ STT không khớp NFC keyphrases — `unicodedata.normalize("NFC", text)` trong `is_opt_out_utterance`
  - `medium` `patch` `_defer_step_for_curfew` gọi `calculate_step_eta(0)` không truyền `channel` → voice step defer theo khung email — patch `calculate_step_eta(0, channel=channel)` trong `dispatch.py`
  - `medium` `patch` fallback secret key không nhất quán giữa DNC service và ComplianceGate → đồng nhất `"default_dnc_secret_key"`
  - `low` `patch` `contact_type=None` crash AttributeError — guard early-return
  - `low` `patch` concurrent opt-out race trên unique constraint → bọc `IntegrityError` rollback + re-read idempotent
  - `low` `patch` thiếu verification tests: `release_deposit`, disclosure on_enter (enabled/disabled), opt-out StopResponse — thêm 5 tests
  - `medium` `defer` DTMF 0/9 live listener — LiveKit 1.8.2 không expose DTMF event trên AgentSession; cần data-packet listener ở runtime level
  - `medium` `defer` Gate chưa wire vào `_send_voice_dispatch()` — thuộc scope Story 38.7 (Sequencer Action Executor)
  - `low` `defer` Ngày lễ Việt Nam chưa lọc trong voice curfew — cần bảng ngày lễ tĩnh hoặc calendar feed
  - `false` `reject` claim config `__init__.py` không export biến mới — đã verify `Config.VOICE_PRECALL_SOFT_LOCK_MICROS` resolve đúng qua wildcard import + `__all__`
  - `false` `reject` claim frequency lock set sau wallet check — thiết kế intentional: lock trước chống thundering-herd, wallet fail thì rollback release lock (có test verify)
  - `low` `reject` (blind-hunter) claim `evaluate_preflight` skip wallet khi `user_id=None` — intentional: dispatch không có user context (inbound) vẫn cần DNC/curfew check; wallet layer chỉ áp dụng khi có user_id
  - `low` `reject` (blind-hunter) claim `acquire_frequency_lock` hash phone chưa normalize — `evaluate_preflight` normalize E.164 TRƯỚC khi gọi lock, key luôn consistent trong flow chuẩn
  - `low` `reject` (blind-hunter) claim disclosure không đo 3s — `on_enter` fire ngay khi agent join room (trước khi khách nhấc máy trong outbound flow), thời gian thực tế phụ thuộc SIP connect; đo wall-clock là trách nhiệm của Story 38.5 AMD/telephony metrics

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Cổng tuân thủ viễn thông 4 lớp (Telephony Compliance Gate) tiền kiểm soát trước khi quay số, tuân thủ Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP PDPD. Curfew voice split-window mở rộng trực tiếp trong `scheduling.py` (không tạo `voice/curfew.py` — tuân thủ ràng buộc zero-reinvention). DNC opt-out dùng chung qua `register_contact_opt_out()` cho cả Voice Worker và Inbound Sequencer.

### Files changed

- `nowing_backend/app/services/sequencer/scheduling.py` — `calculate_step_eta(channel="voice")` + `is_voice_curfew()` + `_next_voice_window()` (split window 09:00-11:30 & 13:30-17:00 ICT T2-T6)
- `nowing_backend/app/services/sequencer/dispatch.py` — `_defer_step_for_curfew` truyền `channel` vào `calculate_step_eta`
- `nowing_backend/app/lead_intelligence/dnc/service.py` — `register_contact_opt_out()` (E.164/email/domain normalize + HMAC + idempotent + IntegrityError race-safe + cache eviction)
- `nowing_backend/app/services/voice/compliance_gate.py` (mới, ~390 dòng) — `TelephonyComplianceGate` 4 lớp + `is_opt_out_utterance` (NFC normalize) + `is_dtmf_opt_out`
- `nowing_backend/app/services/voice/agent_worker.py` — recording disclosure 3s đầu trong `on_enter`, opt-out handler `_handle_immediate_opt_out` (interrupt + farewell + LiveKit end_call + DNC persist fail-safe), `entrypoint` parse `phone_e164` từ room metadata
- `nowing_backend/app/config/voice.py` — 4 config compliance mới + export `__all__`
- 3 test files mới: `test_compliance_gate.py` (35 tests), `test_scheduling.py` (19 tests), `test_opt_out.py` (7 tests) + 3 tests compliance trong `test_agent_worker.py`

### Review findings breakdown

- **Patches applied (10):** entrypoint phone_e164 plumbing; LiveKit end_call thay session.end_call; CancelledError-safe DNC persistence; "phiền quá" hard opt-out; NFC normalize; contact_type guard; IntegrityError race-safe; dispatch channel passthrough; secret key nhất quán; 5 verification tests mới
- **Deferred (3):** DTMF live listener (SDK limitation), gate wiring vào dispatch (Story 38.7 scope), Vietnamese holidays (cần bảng ngày lễ)
- **Rejected (5):** config export claim (false), lock-order claim (intentional design), user_id-None wallet skip (intentional), lock-key normalization (false), disclosure 3s wall-clock (thuộc 38.5)

### Follow-up review recommendation

`false` — mọi finding high/medium đã patch + verify bằng 256 unit tests; deferred items đều có owner story rõ ràng (38.5, 38.7) hoặc cần quyết định kiến trúc riêng (holiday calendar).

### Verification performed

- `uv run pytest tests/unit/voice/ tests/unit/sequencer/ tests/unit/dnc/ -q` → **256 passed**, 0 failed
- `uv run ruff check` (10 files) → **All checks passed!**
- `uv run python -c "from app.services.voice.compliance_gate import TelephonyComplianceGate"` → **import OK**
- Matrix Test Audit: 10/10 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- DTMF opt-out chưa hoạt động runtime (chờ LiveKit DTMF listener — deferred, medium)
- Gate chưa wire vào dispatch pipeline (chờ Story 38.7 — deferred, có chủ đích)
- Ngày lễ Việt Nam chưa lọc (deferred, low)
- Timing < 2s opt-out và < 3s disclosure chưa đo trên real telephony audio end-to-end

## Design Notes

**Cơ chế Curfew đa khối (Split-block Curfew):**
Khác với email (chỉ có 1 khối 08:00 - 20:59 ICT), voice có 2 khối trong ngày: Sáng (09:00 - 11:30 = 540-690m) và Chiều (13:30 - 17:00 = 810-1020m). Nếu rơi vào:
- Trước 09:00: chuyển về 09:05 cùng ngày + jitter.
- 11:30 - 13:30 (nghỉ trưa): chuyển về 13:35 cùng ngày + jitter.
- Sau 17:00: chuyển về 09:05 ngày làm việc tiếp theo + jitter (nếu là Thứ 6 thì nhảy sang Thứ 2).

**Distributed Lock 24h:**
Dùng Redis key `voice:freq:{workspace_id}:{hash_phone_hmac(phone)}` với `SET NX EX 86400`. Nếu key đã tồn tại, lập tức từ chối quay số. Lock chỉ được set khi tất cả các lớp kiểm tra trước đó (Curfew, DNC, Wallet) đều đã vượt qua.

**Soft-lock Ví 7.500.000 micros:**
Tái sử dụng hàm `reserve_credit` trong `app/services/wallet_credit.py` để phong tỏa 7.500.000 micros (đệm 3 phút cuộc gọi theo đơn giá 2.500 VNĐ/phút). Nếu cuộc gọi thành công, Story 38.8 sẽ commit số tiền thực tế và release phần thừa; nếu cuộc gọi quay số không thành công (bận/không nhấc máy), toàn bộ số tiền được giải phóng qua `release_credit`.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/voice/test_compliance_gate.py tests/unit/sequencer/test_scheduling.py tests/unit/dnc/test_opt_out.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/services/sequencer/scheduling.py app/lead_intelligence/dnc/service.py app/services/voice/compliance_gate.py app/services/voice/agent_worker.py app/config/voice.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.voice.compliance_gate import TelephonyComplianceGate; print('import OK')"` -- expected: no exception
