# Epic 38 Context: Autonomous Voice AI SDR & Telephony Workstation

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Thiết lập trạm thoại AI tự hành đa kênh (Autonomous Voice SDR) chuẩn hóa cho thị trường B2B Việt Nam, tuân thủ pháp lý viễn thông (Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP PDPD) và đạt độ trễ nhận thức sub-800ms (300ms–550ms perceived latency). Hệ thống đóng vai trò Action Executor trong Sequencer, tự động thực hiện cuộc gọi outbound sàng lọc và đặt lịch hẹn B2B theo tín hiệu tương tác thời gian thực (Speed-to-Lead < 5 phút khi prospect xem Mini-Pitch portal hoặc khi Intent Radar phát hiện đợt tuyển dụng), hỗ trợ cướp lời tự nhiên, phát hiện hộp thư thoại, và đo lường cước viễn thông minh bạch.

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

- **Tuân thủ Pháp lý Viễn thông & DNC Quốc gia**:
  - Khóa cứng khung giờ gọi ra: chỉ cho phép quay số từ 09:00–11:30 và 13:30–17:00 ICT, Thứ Hai đến Thứ Sáu. Chặn tuyệt đối cuộc gọi vào Thứ Bảy, Chủ Nhật, ngày lễ và giờ nghỉ trưa.
  - Áp dụng giới hạn tần suất nghiêm ngặt tối đa 1 cuộc gọi / 24 giờ / 1 số điện thoại E.164 trên toàn bộ workspace qua distributed lock.
  - Bắt buộc đối soát danh sách Không quảng cáo Quốc gia (DNC 5656) trước khi cấp phép quay số; số thuộc DNC bị chặn pre-flight và không tác động đến số dư ví.
  - Bắt buộc phát âm thông báo ghi âm cuộc gọi trong 3 giây đầu tiên khi khách bắt máy.
  - Xử lý từ chối tức thì: Người nghe nói "đừng gọi nữa", "không có nhu cầu" hoặc bấm phím 0/9 kích hoạt cúp máy trong dưới 2 giây và tự động ghi nhận vĩnh viễn vào danh sách DNC của workspace.
  - Vòng đời và quyền xóa dữ liệu giọng nói (PDPD): File ghi âm cuộc gọi chuyển sang lưu trữ lạnh sau 30 ngày và xóa vĩnh viễn sau 90 ngày. Khi có yêu cầu hủy thông tin hoặc opt-out, toàn bộ file âm thanh, văn bản bóc băng và vector embeddings phải được xóa vĩnh viễn trong vòng 24 giờ kèm audit log.
- **Độ trễ & Chất lượng Âm thanh**:
  - Hạ tầng truyền dẫn: Độ trễ định tuyến nội bộ giữa Kamailio SBC, LiveKit SIP Gateway và Media Server SFU phải đạt $P99 < 3$ms với chuyển đổi codec chuẩn G.711a (8kHz) sang WebRTC Opus (48kHz) không gây méo tiếng.
  - Độ trễ đàm thoại nhận thức: Silero VAD phát hiện ngắt câu trong 180ms–220ms; Micro-clause token streaming cắt câu theo dấu câu tiếng Việt hoặc 3–5 tokens; tiêm câu đệm âm thanh cục bộ (Local Filler Audio) từ RAM trong vòng 80ms nếu token đầu của LLM chưa sẵn sàng.
- **Bảo vệ Kinh tế Đơn vị & Cước Viễn thông**:
  - Tính cước theo block viễn thông chuẩn 6s + 1s với đơn giá 2.500 VNĐ/phút (2.5 credits/phút).
  - Ký quỹ trước cuộc gọi: Tạm giữ (soft-lock) 7.500 VNĐ (7.500.000 micros) trong ví trước khi bấm số; từ chối cuộc gọi nếu số dư không đủ.
  - Chính sách Hang-up Protection: Miễn phí 100% cước cho cuộc gọi dập máy dưới 10 giây trong hạn ngạch tối đa 15% tổng số cuộc gọi của chiến dịch.
  - Hard Ceiling Watchdog: Tự động ngắt cuộc gọi dứt khoát tại 175s–180s.
- **Độ tin cậy & Rào chắn Chống Spam**:
  - Answering Machine Detection (AMD) nhận diện hộp thư thoại và chuông chờ tổng đài trong 3 giây đầu, phát SIP BYE ngắt cuộc gọi trong $\le 4$ giây với độ chính xác $\ge 96\%$.
  - Dead-air Watchdog: Phát âm thăm dò nếu khách im lặng 3 giây; cúp máy trước 8 giây nếu tiếp tục im lặng 3 giây tiếp theo.
  - In-flight Anti-Spam Circuit Breaker tự động tạm dừng chiến dịch nếu tỷ lệ cuộc gọi ngắn (< 5s) vượt 40% hoặc tỷ lệ khiếu nại spam vượt 6%.
  - Rào chắn Day-1 DID: Đầu số cố định (024/028-7xxx) cấp trong ngày chỉ được phép gọi các Lead có Verified Inbound Consent Token (xem pitch > 45s); vô hiệu hóa cuộc gọi danh bạ lạnh ngoại lai cho đến khi Voice Brandname chính danh được phê duyệt.

## Technical Decisions

- **Kế thừa và Ranh giới Chống Trùng lặp (Zero Reinvention)**:
  - Voice AI SDR hoạt động như một Action Executor trong Sequencer (`SequenceStep.channel = "voice"`, bảo vệ bởi cờ `SEQUENCER_VOICE_ENABLED`), tuyệt đối không tạo scheduler hay dispatcher độc lập.
  - Logic khung giờ gọi viễn thông (Curfew) được mở rộng trực tiếp trong hàm `calculate_step_eta` tại `app/services/sequencer/scheduling.py`, không tạo module curfew riêng.
  - Trích xuất logic ghi nhận Opt-out thành hàm dùng chung `register_contact_opt_out()` trong `app/lead_intelligence/dnc/service.py` cho cả Inbound Sequencer và Voice Worker.
  - Thông tin cấu hình SIP Trunk đa người thuê (BYO-SIP) được mã hóa AES-256-GCM thông qua `TokenEncryption` trong PII Vault.
  - Dữ liệu nhật ký cuộc gọi và phân tích sau cuộc gọi được đồng bộ trực tiếp vào thực thể `LeadActivityLog` (`activity_type="voice_call"`), không tạo bảng timeline mới.
- **Kiến trúc Hạ tầng & Xử lý Đồng thời**:
  - Kamailio Edge SBC: Cấu hình Active-Passive với Keepalived VRRP chia sẻ VIP, lọc IP allowlist từ nhà mạng viễn thông, kiểm tra sức khỏe gateway bằng SIP OPTIONS mỗi 2 giây.
  - LiveKit SIP Gateway: Tối thiểu 2 instance dự phòng, chuyển đổi định dạng G.711a và Opus qua bộ lọc đa pha (Polyphase Filter Resampler).
  - Multi-Process Worker Pool: 8 tiến trình worker độc lập (mỗi tiến trình gánh tối đa 12–15 cuộc gọi đồng thời) nhằm cô lập GIL và bảo vệ độ trễ Event Loop không trượt quá 80ms.
  - Silero VAD v5 chạy trên ONNX Runtime CPU với các cặp state tensor `(state_h, state_c)` cô lập tuyệt đối theo từng session cuộc gọi.
  - SIP-Ringing Pre-Warming: Mở sẵn WebSocket TLS kết nối tới STT và TTS ngay khi nhận tín hiệu `180 Ringing`, loại bỏ hoàn toàn độ trễ bắt tay 200ms–400ms khi khách nhấc máy.
- **Cơ chế Cướp lời & Kiểm soát Gián đoạn (Barge-in Engine)**:
  - Áp dụng 400ms Echo Lockout ngay khi bot bắt đầu nói để triệt tiêu hiện tượng dội âm.
  - Audio Ducking: Giảm âm lượng bot xuống -14dB trong vòng 30ms khi phát hiện xác suất tiếng nói khách hàng $P \ge 0.88$.
  - In-process Keyword Spotting (KWS): Đánh giá âm thanh $< 280$ms; nếu là từ đệm hội thoại ("ừ", "dạ", "vâng"), tự động nâng âm lượng về 0dB và tiếp tục mạch nói; nếu là cướp lời thật, phát 40ms SIP silence packet và hủy các tác vụ LLM/TTS đang xử lý trong $< 50$ms.

## UX & Interaction Patterns

- **Thiết kế Âm thái Học Hội thoại (Sonic Ergonomics)**:
  - EQ điều chỉnh dải 1.2kHz–2.4kHz thêm +2dB trên G.711a giúp rõ phụ âm tiếng Việt; tốc độ nói chuẩn hóa 150–165 từ/phút cho giọng đọc Bắc và Nam.
  - Chèn nhịp thở sinh học (Micro-breath) 50ms–70ms ở mức -24dB trước các câu dài trên 8 từ để giảm phản xạ phòng vệ của người nghe.
  - Kịch bản mở đầu tuân theo nguyên tắc "Ngữ cảnh trước, Danh tính sau", kích hoạt cuộc gọi dựa trên hành động cụ thể của khách để tăng tỷ lệ giữ máy.
- **Trạm Điều phối Telephony Dashboard**:
  - Trình phát âm thanh đồng bộ 2 kênh (Dual-Track Waveform): Kênh trên màu xanh ngọc lục bảo (Emerald) cho khách hàng, kênh dưới màu tím thẫm (Indigo) cho Voice SDR.
  - Smart Markers trực quan: Vạch đỏ cam (Phản đối - Objection), vạch xanh lá (Chốt hẹn - Booking), vạch vàng (Hỏi giá - Pricing).
  - Transcript dạng Karaoke cuộn theo nhịp nói; nhấp đúp câu thoại để chuyển ngay đến vị trí âm thanh tương ứng.
  - Thẻ Lead hiển thị điểm BANT tròn (1–100) kèm 4 trạng thái con (Budget, Authority, Need, Timeline) và nút "1-Click Zalo Hand-off" để gửi tin nhắn kèm tài liệu trao đổi trong cuộc gọi.
  - WebRTC Sandbox tương tác: Môi trường thử nghiệm trực tiếp trên trình duyệt qua microphone, đo lường trực quan độ trễ và kiểm tra độ nhạy cướp lời trước khi khởi chạy chiến dịch thật.

## Cross-Story Dependencies

- **Wave 1 (Tuần 1–2: Core Loop & Sandbox - P0 Blocker)**:
  - Story 38.1 (Hạ tầng Kamailio SBC & LiveKit SIP Gateway) và Story 38.2 (Worker Runtime, Silero VAD, Micro-clause Streaming) xây dựng nền tảng kết nối thoại thời gian thực.
  - Story 38.8 (Hệ thống tính cước, tạm giữ tiền ký quỹ và Hang-up Protection) bắt buộc hoàn tất để quản lý giao dịch trước khi thực hiện bất kỳ cuộc gọi nào.
- **Wave 2 (Tuần 3–4: Compliant Outbound Pilot - P0/P1)**:
  - Story 38.4 (Compliance Gate, DNC 5656, Curfew trong `scheduling.py`) là rào chắn điều kiện tiên quyết trước khi quay số sản xuất.
  - Story 38.5 (Telecom Classifier, AMD & Dead-air Watchdog) bảo vệ ngân sách cước trước hộp thư thoại và đường truyền chết.
  - Story 38.7 (Speed-to-Lead & Hiring Radar Trigger) kết nối bộ điều phối Sequencer với tín hiệu tuyển dụng (Epic 37.1) và tương tác Mini-Pitch (Epic 37.6).
- **Wave 3 (Tuần 5–6: Enterprise Scale & Perfection - P2)**:
  - Story 38.3 (Barge-in mượt mà & Audio Ducking -14dB) tối ưu hóa trải nghiệm tự nhiên của đàm thoại.
  - Story 38.6 (Đăng ký Voice Brandname & Quản lý BYO-SIP đa người thuê) hoàn thiện giải pháp định danh doanh nghiệp.
- **Ranh giới Phụ thuộc Ngoại vi**:
  - Đầu vào (Upstream): Epic 21 (DNC, PII Vault), Epic 24 (Sequencer dispatch & scheduling), Epic 37.1 (SignalEvent Intent Radar), Epic 37.6 (Redis stream `stream:prospect:engagement`).
  - Đầu ra (Downstream): Story 37.4 (Zalo Co-pilot / ZNS post-call summary delivery), Epic 34 (CRM `LeadActivityLog` deal timeline synchronization).
