# Epic 38 Context: Autonomous Voice AI SDR & Telephony Workstation

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Thiết lập trạm thoại AI tự hành đa kênh (Autonomous Voice SDR) cho thị trường B2B Việt Nam, tuân thủ pháp lý viễn thông (Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP PDPD) và đạt độ trễ nhận thức sub-800ms (300ms–550ms perceived latency). Hệ thống đóng vai trò Action Executor trong Sequencer, tự động thực hiện cuộc gọi outbound sàng lọc và đặt hẹn theo tín hiệu thời gian thực (Speed-to-Lead < 5 phút khi prospect xem pitch > 45s hoặc Intent Radar phát hiện đợt tuyển dụng), hỗ trợ cướp lời tự nhiên, phát hiện hộp thư thoại/chuông chờ, và đo lường cước viễn thông minh bạch.

## Stories

- Story 38.1: LiveKit SIP Gateway & Kamailio Media Infrastructure
- Story 38.2: Voice Agent Worker Runtime với Silero VAD & Micro-clause Streaming
- Story 38.3: Anti-False-Interruption & Multi-tier Barge-in Engine
- Story 38.4: Telephony Compliance Gate, National DNC 5656 & Curfew Scheduler
- Story 38.5: Telecom Signal Classifier, AMD & Dead-air Watchdog Engine
- Story 38.6: Dynamic DID & Voice Brandname Multi-tenant BYO-SIP Architecture
- Story 38.7: Outbound Trigger Engine: Speed-to-Lead & Hiring Radar Integration
- Story 38.8: Voice Billing, Realtime Metering & QA Scorecard

## Requirements & Constraints

- **Tuân thủ Viễn thông & Pháp lý (Decree 91/2020 & 13/2023)**:
  - Khung giờ gọi: Chỉ cho phép gọi 09:00–11:30 và 13:30–17:00 ICT, Thứ 2 đến Thứ 6. Cấm gọi Thứ 7, Chủ Nhật, ngày lễ và giờ nghỉ trưa.
  - Tần suất: Tối đa 1 cuộc gọi / 24 giờ / 1 số điện thoại E.164 trên toàn workspace qua Redis lock.
  - Đối soát DNC 5656: Kiểm tra danh sách DNC Quốc gia trước khi quay số; số bị chặn không tác động số dư ví.
  - Thông báo ghi âm: Bắt buộc phát thông báo ghi âm trong 3 giây đầu tiên khi khách nhấc máy.
  - Opt-out tức thì: Cúp máy < 2 giây khi khách từ chối ("đừng gọi nữa", "không có nhu cầu") hoặc bấm phím 0/9; tự động ghi nhận vĩnh viễn vào danh sách DNC của workspace.
  - Vòng đời dữ liệu giọng nói (AD-130): File ghi âm chuyển sang cold storage sau 30 ngày, xóa vĩnh viễn sau 90 ngày. Yêu cầu xóa/opt-out phải xóa sạch file âm thanh, bóc băng và vector embeddings trong vòng 24 giờ kèm audit log trong `pii_access_audit_logs`.
- **Độ trễ & Chất lượng Đàm thoại**:
  - Routing nội bộ: Kamailio SBC, LiveKit SIP Gateway và Media Server SFU đạt P99 < 3ms. Transcoding G.711a (8kHz) <-> Opus (48kHz) không méo tiếng qua polyphase filter resampler.
  - Độ trễ nhận thức: Silero VAD dứt câu 180ms–220ms; streaming STT phát câu hoàn chỉnh < 40ms; Micro-clause ngắt theo dấu câu hoặc 3–5 tokens; tiêm Local Filler Audio từ RAM trong 80ms nếu token đầu của LLM chưa sẵn sàng (giữ perceived latency 300ms–550ms).
- **Kinh tế Đơn vị & Bảo vệ Cước**:
  - Tính cước theo block 6s + 1s, đơn giá 2.500 VNĐ/phút (2.5 credits/phút).
  - Ký quỹ trước cuộc gọi: Soft-lock 7.500 VNĐ (7.500.000 micros = đệm 3 phút) trong ví; từ chối gọi (mã 402) nếu không đủ số dư.
  - Hang-up Protection: Miễn phí 100% cước cho cuộc gọi dập máy < 10 giây (áp dụng tối đa 15% tổng số cuộc gọi của campaign).
  - Hard Ceiling: Ngắt cuộc gọi dứt khoát tại 175s–180s.
- **Rào chắn Chống Spam & Độ tin cậy**:
  - AMD & Dead-air: AMD nhận diện IVR/voicemail và cúp máy trong <= 4 giây (độ chính xác >= 96%); Dead-air thăm dò ở 3s im lặng, cúp máy trước 8s nếu tiếp tục im lặng.
  - Circuit Breaker: Tạm dừng campaign nếu tỷ lệ dập máy < 5s vượt 40% hoặc tỷ lệ khiếu nại spam vượt 6% (sau tối thiểu 30 cuộc).
  - Day-1 DID: Đầu số cố định (024/028-7xxx) cấp mới chỉ được gọi Lead có Inbound Consent Token (> 45s xem pitch); vô hiệu hóa cold list ngoại lai cho đến khi Voice Brandname được duyệt.

## Technical Decisions

- **Ranh giới Kiến trúc & Chống Trùng lặp (Zero-Reinvention Boundaries)**:
  - **Sequencer Action Executor (Story 38.7)**: Voice SDR là Action Executor trong Sequencer (`SequenceStep.channel = "voice"`, cờ `SEQUENCER_VOICE_ENABLED`, khai báo trong `ALLOWED_OUTBOUND_CHANNELS` tại `app/services/sequencer/constants.py`). Nối vào `_send_voice_dispatch()` trong `app/services/sequencer/dispatch.py` và task Celery `app/tasks/celery_tasks/voice_tasks.py`. **Cấm tạo scheduler hay dispatcher độc lập**.
  - **Khung giờ Curfew (Story 38.4)**: **Cấm tạo `voice/curfew.py`**. Logic khung giờ gọi Nghị định 91 mở rộng trực tiếp trong hàm `calculate_step_eta(delay_seconds, from_dt, channel="email")` tại `app/services/sequencer/scheduling.py`.
  - **DNC & Opt-out Dùng chung (Story 38.4)**: Dùng hàm `register_contact_opt_out()` trong `app/lead_intelligence/dnc/service.py` cho cả Inbound Sequencer và Voice Worker, ghi vào `WorkspaceDncRecord` và xóa Redis cache.
  - **Barge-in In-Process trên PCM Buffer (Story 38.3)**: **Cấm tạo audio microservice riêng**. Toàn bộ logic Barge-in (Echo Lockout 400ms, Ducking -14dB trong 30ms, KWS lọc từ đệm "ừ/dạ" < 280ms, 40ms silence packet) phải nhúng trực tiếp in-process trong Voice Agent Worker (`app/services/voice/worker.py`) xử lý trên buffer PCM thô.
  - **Hạ tầng Mạng Viễn thông (Story 38.1)**: Đặt tại `docker/kamailio/` và `docker/livekit/sip.yaml`. Luồng RTP chạy trực tiếp qua host network tránh NAT traversal; không can thiệp Traefik của Web API. Kamailio SBC Active-Passive qua Keepalived VRRP chia sẻ VIP, ping SIP OPTIONS mỗi 2s tới LiveKit SIP Gateway.
  - **Multi-Process Worker Pool (Story 38.2)**: 8 tiến trình worker độc lập (tối đa 12–15 cuộc/process) cô lập GIL, giữ Event Loop latency < 80ms. Dùng `run_async_celery_task` từ `app/tasks/celery_tasks/__init__.py`. Silero VAD v5 trên ONNX Runtime CPU với cặp state tensor `(state_h, state_c)` cô lập theo CallSession.
  - **SIP-Ringing Pre-Warming (Story 38.2)**: Mở sẵn WebSocket TLS tới STT/TTS ngay khi nhận `SIP 180 Ringing`, triệt tiêu 200ms–400ms độ trễ bắt tay khi nhận `SIP 200 OK`.
  - **Mã hóa SIP Trunk BYO-SIP (Story 38.6)**: Router `app/routes/voice_agent.py`. Mật khẩu SIP Trunk mã hóa AES-256-GCM qua `TokenEncryption` (`app/utils/oauth_security.py`) dùng khóa PII Vault; **cấm tự viết module crypto mới**.
  - **Giám sát Viễn thông & Watchdog (Story 38.5)**: Module phân loại tín hiệu tại `app/services/voice/telecom_classifier.py`. Tái sử dụng Redis client có sẵn (`app/redis.py`) duy trì heartbeat 1 giây; **không tạo Redis pool riêng**.
  - **Ví tiền & CRM Timeline (Story 38.8)**: Dùng 3 nguyên thủy của `app/services/wallet_credit.py`: `reserve_credit`, `commit_reserved_credit`, `release_credit`. Task hậu cuộc gọi `process_post_call_qa_task` ghi nhận kết quả và điểm BANT vào model `LeadActivityLog` (`app/models/leads/main.py`) với `activity_type="voice_call"`; **cấm tạo bảng `LeadActivityTimeline`**.

## UX & Interaction Patterns

- **Thiết kế Âm thái học (Sonic Ergonomics)**:
  - EQ dải 1.2kHz–2.4kHz (+2dB) trên codec G.711a giúp rõ phụ âm tiếng Việt; tốc độ nói 150–165 từ/phút cho giọng Bắc ("Thu Trang") và Nam ("Minh Triết").
  - Micro-breath synthesis: Chèn nhịp thở sinh học 50ms–70ms (-24dB) trước câu dài > 8 từ để giảm phản xạ cúp máy phòng vệ.
  - Kịch bản mở đầu "Ngữ cảnh trước, Danh tính sau": Dẫn dắt bằng hành vi thực tế của khách (xem pitch portal / tin tuyển dụng) thay vì telesales truyền thống.
- **Trạm Điều phối Telephony Dashboard**:
  - Dual-Track Waveform Player: Track ngọc lục bảo (Emerald) cho Prospect, track tím thẫm (Indigo) cho Voice SDR; Smart Markers màu trực quan (Đỏ: Phản đối, Xanh lá: Chốt hẹn, Vàng: Hỏi giá).
  - Transcript cuộn dạng Karaoke, nhấp đúp câu thoại để chuyển ngay đến đoạn audio tương ứng.
  - Thẻ Lead Kanban hiển thị micro-gauge điểm BANT (1–100), 4 pills con (Budget, Authority, Need, Timeline), và nút "1-Click Zalo Hand-off".
  - WebRTC Interactive Sandbox: Thử nghiệm kịch bản trực tiếp trên trình duyệt qua microphone, đo độ trễ thực tế (~320ms counter) và kiểm thử độ nhạy cướp lời/từ chối.

## Cross-Story Dependencies

- **Phân kỳ Triển khai 3 Waves**:
  - **Wave 1 (Tuần 1–2: Core Loop & Sandbox - P0 Blocker)**: Story 38.1 (Hạ tầng SBC & SIP Gateway), Story 38.2 (Worker Runtime, VAD, Micro-clause Streaming), Story 38.8 (Voice Billing, Soft-lock & Hang-up Protection).
  - **Wave 2 (Tuần 3–4: Compliant Outbound Pilot - P0/P1)**: Story 38.4 (Compliance Gate, DNC 5656, Curfew trong `scheduling.py`), Story 38.5 (Telecom Classifier, AMD & Watchdog), Story 38.7 (Speed-to-Lead & Hiring Radar Trigger).
  - **Wave 3 (Tuần 5–6: Enterprise Scale & Perfection - P2)**: Story 38.3 (Multi-tier Barge-in, KWS & Audio Ducking -14dB), Story 38.6 (Voice Brandname & BYO-SIP đa người thuê).
- **Phụ thuộc Ngoại vi (External Dependencies)**:
  - Đầu vào (Upstream): Epic 21 (DNC 5656, PII Vault `TokenEncryption`), Epic 24 (Sequencer dispatch & `scheduling.py`), Epic 37.1 (SignalEvent Intent Radar), Epic 37.6 (Redis stream `stream:prospect:engagement`).
  - Đầu ra (Downstream): Story 37.4 (Zalo Co-pilot / ZNS post-call summary delivery), Epic 34 (CRM `LeadActivityLog` đồng bộ timeline).
