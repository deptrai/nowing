# BÁO CÁO TOÀN DIỆN CHIẾN LƯỢC & KIẾN TRÚC CHO EPIC 38: AUTONOMOUS VOICE AI SDR CHO NOWING

**Hội đồng xây dựng và phản biện:**
- Winston (System Architect)
- Mary (Business Analyst)
- John (Lead Product Manager)
- Murat (Master Test Architect - Technical Reviewer)

**Trạng thái tài liệu:** Final Approved Architectural Blueprint  
**Cơ sở dữ liệu hệ thống:**
- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/lead_intelligence/dnc/service.py`
- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/voice_agent.py`
- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/voice/worker.py`
- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/tasks/voice_tasks.py`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/audit-artifacts/docs/lead-gen-compliance-audit-2026-08-29.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md`

---

## PHẦN 1: TỔNG QUAN ĐỊNH VỊ (EXECUTIVE SUMMARY & POSITIONING)

### 1.1. Bối cảnh thị trường và Khoảng trống chiến lược (The White Space)
Thị trường tương tác thoại tự động tại Việt Nam đang bị chia cắt thành 3 phân khúc không đáp ứng được bài toán B2B Outbound SDR:
1. **Các giải pháp Voicebot Call Center nội địa (FPT.AI, EM&AI, Vbee):** Kiến trúc hướng tới Contact Center truyền thống (CSKH Inbound, nhắc nợ, khảo sát hài lòng). Sử dụng luồng kịch bản cứng (IVR/Dialogflow-style), độ trễ cao (1.200ms - 2.500ms), giọng đọc mang tính thông báo một chiều, thiếu khả năng xử lý linh hoạt và hoàn toàn tách rời dữ liệu kinh doanh B2B.
2. **Các giải pháp Voice AI toàn cầu (11x.ai, Bland.ai, Retell AI, Vapi):** Sở hữu kiến trúc Real-time LLM tiên tiến nhưng không tương thích với hạ tầng viễn thông Việt Nam: không hỗ trợ kết nối SIP Trunking nội địa theo chuẩn G.711a, không có cơ chế Voice Brandname theo Nghị định 91/2020/NĐ-CP, trễ mạng xuyên biên giới (RTT > 1.400ms do máy chủ ở US/EU), chi phí quá cao (1.500 - 3.000 USD/tháng) và không hiểu sắc thái xưng hô B2B tiếng Việt (anh/chị/em).
3. **Các phần mềm Autodialer rác (Simbox, VoIP lậu):** Quay số hàng loạt bằng sim rác hoặc đầu số ảo, tỷ lệ bắt máy dưới 15%, vi phạm nghiêm trọng quy định pháp luật và bị nhà mạng chặn cước liên tục.

### 1.2. "Điểm ngọt" định vị của Nowing Voice AI SDR (The Sweet Spot)
Nowing định vị Epic 38 không phải là một công cụ quay số tự động (Mass Autodialer), mà là:
**"Kênh tương tác thoại B2B thông minh dựa trên tín hiệu thời gian thực (Signal-driven Contextual Calling Engine)"**.

Điểm ngọt của Nowing được xác lập tại giao điểm của 4 trụ cột độc quyền:
- **Ngữ cảnh hóa tối đa nhờ Lead Intelligence:** Không gọi lạnh mù quáng (blind cold call). Cuộc gọi chỉ được kích hoạt khi có tín hiệu kinh doanh xác thực từ Epic 21 và Epic 37 (doanh nghiệp vừa đăng tuyển dụng trên TopCV, người đại diện vừa tương tác với Mini-Pitch Portal trong vòng 5 phút).
- **Hội thoại tự nhiên độ trễ thấp (Sub-800ms Perceived Latency):** Nhờ kỹ thuật kết hợp Local Filler Audio Injection, Semantic Endpointing và Micro-clause Streaming, đưa độ trễ nhận thức của người nghe về ngưỡng 300ms - 600ms, xóa bỏ hoàn toàn cảm giác "nói chuyện với robot".
- **Tuân thủ pháp lý viễn thông tuyệt đối (Compliant by Design):** Tích hợp sẵn bộ lọc DNC Quốc gia (5656), kiểm soát khung giờ hành chính (Curfew), giới hạn 1 cuộc/24h và hỗ trợ hiển thị Voice Brandname chính danh.
- **Hệ sinh thái chốt hạ đa kênh hậu cuộc gọi:** Tự động điều hướng kết quả cuộc gọi sang Zalo Co-pilot (Epic 37.4), tạo lịch hẹn Google/Lark (Epic 37.3) và cập nhật trực tiếp dòng thời gian CRM.

---

## PHẦN 2: KIẾN TRÚC KỸ THUẬT CHUẨN ĐỀ XUẤT (RECOMMENDED ARCHITECTURE & ADs)

### 2.1. Sơ đồ Luồng Audio Streaming & WebRTC/SIP Gateway

```
 [ VN Telcos: Viettel / VNPT / FPT / CMC ]
                    |
                    | SIP Trunking (UDP, G.711 A-law 8kHz, E.164)
                    v
       +-------------------------+
       |   Kamailio Edge SBC     | <--- Anti-Fraud, DNC 5656 Pre-check, LCR
       +-------------------------+
                    | SIP / RTP (Internal LAN 10Gbps, < 1ms)
                    v
       +-------------------------+
       |   LiveKit SIP Gateway   | <--- PJSIP Engine, G.711a <-> WebRTC Bridge
       +-------------------------+
                    | WebRTC Audio Tracks (Opus 48kHz, DTLS-SRTP, < 2ms)
                    v
       +-------------------------+
       |     LiveKit Media SFU   | <--- WebRTC Room Router (call_<session_uuid>)
       +-------------------------+
              ^             ^
     Audio In |             | Audio Out
              v             v
 +-------------------------------------------------------------------------+
 |             Voice Agent Worker Runtime (Python Asyncio)                 |
 |                                                                         |
 |  +--------------------+     +-------------------+     +--------------+  |
 |  | Polyphase Resampler| --> | Silero VAD v5     | --> | Audio Buffer |  |
 |  |  (8kHz -> 16kHz)   |     | (ONNX C++ Runtime)|     | Ring Buffer  |  |
 |  +--------------------+     +-------------------+     +--------------+  |
 |                                       |                       |         |
 |                Speech Start / End     v                       v Audio   |
 |                             +-------------------+     +--------------+  |
 |                             | Semantic Arbiter  |     | VN Streaming |  |
 |                             | & Ducking (-14dB) |     | STT Engine   |  |
 |                             +-------------------+     +--------------+  |
 |                                       |                       | Text    |
 |         Interruption Confirmed        v                       v Stream  |
 |       +------------------------------------+          +--------------+  |
 |       |  Abort Signal Dispatch             |          | Speculative  |  |
 |       |  (Flush Playout, Jitter & Cancel)  |          | LLM Engine   |  |
 |       +------------------------------------+          +--------------+  |
 |                         ^                                     | Micro-  |
 |                         |                                     v Clauses |
 |       +------------------------------------+          +--------------+  |
 |       | Local Filler Injection (< 80ms)    |          | Streaming    |  |
 |       | ("Dạ em kiểm tra...", "Vâng anh..")|          | TTS Engine   |  |
 |       +------------------------------------+          +--------------+  |
 |                         |                                     | PCM     |
 |                         v                                     v Chunks  |
 |       +--------------------------------------------------------------+  |
 |       | Resampler (24kHz/16kHz -> 8kHz) & Audio Track Playout Buffer |  |
 |       +--------------------------------------------------------------+  |
 +-------------------------------------------------------------------------+
                    |                     ^                 ^
      Telemetry Pub |                     | State Sync      | Task Dispatch
                    v                     v                 |
       +-----------------------+   +---------------+         |
       | Redis Streams Cluster |   | Redis Cluster |         |
       | (Waveforms, Telemetry)|   | (FSM Sessions)|         |
       +-----------------------+   +---------------+         |
                    |                                       |
                    v                                       v
       +----------------------------------------------------------------+
       |                    Nowing Backend Platform                     |
       |                                                                |
       |  +------------------------+        +------------------------+  |
       |  | FastAPI Control Plane  |        | Celery Worker Cluster  |  |
       |  | (Dispatch & Webhooks)  |        | (Post-Call Processing) |  |
       |  +------------------------+        +------------------------+  |
       |               |                                 |              |
       |               +----------------+----------------+              |
       |                                |                               |
       |                                v                               |
       |                     +--------------------+                     |
       |                     | PostgreSQL Database|                     |
       |                     | (Sessions, Turns)  |                     |
       |                     +--------------------+                     |
       +----------------------------------------------------------------+
```

### 2.2. Chi tiết Lựa chọn Stack Công nghệ

1. **Media Ingress & SIP Bridge:**
   - **Kamailio Edge SBC:** Đặt tại Datacenter FPT/Viettel. Thực hiện cân bằng tải, kiểm tra ACL bạch hóa IP, lọc tấn công SIP flood, chuẩn hóa E.164 và định tuyến đầu số.
   - **LiveKit SIP Gateway (livekit-sip):** Chuyển đổi hai chiều giữa SIP/RTP (G.711a 8kHz) và WebRTC (Opus 48kHz). Tạo buồng đàm thoại ảo biệt lập cho mỗi cuộc gọi.
2. **Voice Activity Detection (VAD) & Barge-in:**
   - **Silero VAD v5 (ONNX Runtime):** Cấu hình frame 30ms.
   - **Dual-threshold State:** Khi bot im lặng, đặt ngưỡng xác suất nói $P \ge 0.70$ (cửa sổ 150ms). Khi bot đang nói, tự động nâng ngưỡng $P \ge 0.88$ (cửa sổ 280ms) để triệt tiêu tiếng ồn giao thông và hơi thở.
   - **Audio Ducking (-14dB):** Khi phát hiện âm thanh khả nghi, hạ âm lượng bot thay vì ngắt đột ngột. Kết hợp bộ phân tích Keyword Spotting (KWS) cục bộ: nếu là hư từ đệm ("ừ", "dạ", "vâng"), khôi phục âm lượng; nếu là câu nói thực sự ($> 280ms$), kích hoạt cúp luồng phát (Hard Interruption).
3. **Speech-to-Text (STT) Engine:**
   - **Primary:** **FPT.AI STT Telephony 8kHz** (kết nối WebSocket Full-Duplex, cụm máy chủ đặt tại Hà Nội/TP.HCM). Nạp sẵn từ điển tùy chỉnh (Custom Vocabulary / Keyword Boosting) chứa tên riêng doanh nghiệp, thuật ngữ B2B và mã số thuế.
   - **Secondary / Fallback:** **Deepgram Nova-2 Vietnamese** (WebSocket Streaming, `endpointing=250ms`).
4. **Reasoning LLM Router:**
   - **Primary Model:** **Claude 3.5 Haiku** hoặc **GPT-4o-mini** chạy streaming.
   - **Tối ưu hóa Context:** Rolling Context Window (chỉ giữ 2 turns gần nhất + 1 state summary 150 tokens), kích hoạt System Prompt Caching.
   - **Speculative Execution:** Khi STT streaming đạt 80% câu với độ tin cậy $> 0.85$, gửi trước speculative prompt để chuẩn bị token.
5. **Text-to-Speech (TTS) Engine:**
   - **Primary:** **Cartesia Sonic Vietnamese** qua WebSocket (TTFB 90ms - 120ms, xuất trực tiếp PCM 8kHz/16kHz) kết hợp bộ tiền xử lý Text Normalizer tiếng Việt (chuyển đổi tiền tệ, ngày tháng, chữ viết tắt).
   - **Secondary:** **Vbee Voice Studio / FPT.AI TTS** (giọng Ban Mai miền Bắc, Mỹ An miền Nam) cho các chiến dịch yêu cầu phương ngữ tự nhiên chuẩn bản địa.

### 2.3. Bộ chỉ số Ngân sách Độ trễ (Latency Budget) Cam kết

Để đảm bảo cuộc đàm thoại không bị rơi vào trạng thái ngượng ngùng (awkward silence), hệ thống chia ngân sách theo 2 cấp độ: **Độ trễ Nhận thức (Perceived Latency)** và **Độ trễ Kỹ thuật (Technical RTT)**.

| Chặng xử lý | Thời gian Mục tiêu (Target) | P95 Thực tế | Trần Ngân sách (Ceiling) | Biện pháp Kỹ thuật Kiểm soát |
| :--- | :--- | :--- | :--- | :--- |
| **1. Audio Network Ingress (Telco -> Media)** | 20ms | 35ms | 50ms | DSCP Expedited Forwarding, mạng LAN 10Gbps nội bộ IDC |
| **2. Silence Detection (Endpointing)** | 180ms | 260ms | 350ms | Semantic End-of-Turn Prediction (FastText phân loại hư từ) |
| **3. STT Finalization Delivery** | 120ms | 180ms | 250ms | Streaming WebSocket, nén frame 100ms, server tại VN |
| **4. LLM Time to First Token (TTFT)** | 120ms | 190ms | 280ms | Prompt caching, Speculative generation, token streaming |
| **5. Micro-clause Accumulator** | 15ms | 30ms | 50ms | Ngắt ngay từ thứ 3 hoặc dấu phẩy đầu tiên |
| **6. TTS Time to First Byte (TTFB)** | 90ms | 140ms | 200ms | Cartesia SSM architecture hoặc FPT WebSocket chunking |
| **7. Egress Network & Telco Playout** | 20ms | 35ms | 50ms | Bypass re-encoding, nạp thẳng PCM 8kHz G.711a |
| **TỔNG KỸ THUẬT ROUND-TRIP TIME (RTT)** | **565ms** | **870ms** | **1.230ms** | **Toàn bộ hạ tầng mạng đặt tại Việt Nam** |
| **ĐỘ TRỄ NHẬN THỨC (PERCEIVED LATENCY)** | **< 200ms** | **< 350ms** | **< 500ms** | **Nhờ tiêm Local Filler Audio ("Dạ vâng anh...") trong 80ms** |

### 2.4. Các Quyết định Kiến trúc Trọng yếu (Architecture Decisions - ADs)
- **AD-125: Kiến trúc Media Gateway Phân tầng (Kamailio SBC + LiveKit SIP).** Không dùng FreeSWITCH độc lập do nguy cơ nghẽn dialplan lock khi mở rộng quy mô lớn. Kamailio chịu tải biên viễn thông, LiveKit tối ưu hóa việc truyền nhận audio WebRTC với Voice Worker.
- **AD-126: Cơ chế Multi-tier Barge-in với Audio Ducking (-14dB).** Tuyệt đối không ngắt luồng âm thanh lập tức khi VAD kích hoạt. Áp dụng hạ âm lượng kết hợp Keyword Spotting kiểm tra hư từ đệm (backchanneling) để tránh hiện tượng tự ngắt lời do tiếng còi xe hoặc tiếng thở.
- **AD-127: Khóa Chống Cướp Lời Đầu Câu (Barge-in Lockout Guard 400ms).** Vô hiệu hóa ngắt lời trong 400ms đầu tiên của lượt nói để triệt tiêu toàn bộ rủi ro vòng lặp tự ngắt (Echo Leakage qua loa ngoài).
- **AD-128: Tiêm Âm thanh Lấp chỗ trống Cục bộ (Local Filler Audio Injection).** Chuẩn bị sẵn các đoạn âm thanh PCM 8kHz ("Dạ...", "Vâng anh...", "Dạ em kiểm tra ngay ạ") nạp sẵn trên RAM của Worker. Tự động phát trong vòng 80ms nếu LLM cần xử lý RAG hoặc truy vấn CRM, khống chế Perceived Latency dưới 350ms.
- **AD-129: Hệ thống Giám sát Đa tầng Chống Treo Kênh (3-Layer Telecom Watchdog).**
  - Layer 1: Worker gửi heartbeat mỗi 1.000ms vào Redis.
  - Layer 2: RTPEngine tự động gửi SIP `BYE` nếu luồng RTP im lặng quá 5 giây.
  - Layer 3: Kamailio SBC áp đặt thời lượng trần cứng 180 giây (3 phút) cho toàn bộ cuộc gọi SDR.

---

## PHẦN 3: PHÁP LÝ & CHIẾN LƯỢC ONBOARDING BRANDNAME (COMPLIANCE & BRANDNAME STRATEGY)

### 3.1. Rào cản Pháp lý Cốt lõi tại Việt Nam
Căn cứ **Nghị định 91/2020/NĐ-CP** (chống tin nhắn rác, cuộc gọi rác), **Nghị định 13/2023/NĐ-CP** (PDPD), và **Nghị định 14/2021/NĐ-CP**:
- **Tính chính chủ của Brandname:** Tên định danh gắn liền với Giấy phép kinh doanh của từng doanh nghiệp. Nowing tuyệt đối không được dùng Brandname của mình để gọi thay cho các Tenant, cũng không được cho thuê Brandname trái phép.
- **Khung giờ gọi hợp pháp:** Điều 13 Khoản 4 NĐ 91/2020 quy định cuộc gọi quảng cáo **CHỈ ĐƯỢC PHÉP TỪ 09:00 ĐẾN 17:00**. Gọi từ 08:00 đến 09:00 hoặc sau 17:00 là vi phạm pháp luật (khác với SMS được gửi đến 22:00).
- **Giới hạn tần suất gọi:** Điều 13 Khoản 3 NĐ 91/2020 quy định **TỐI ĐA 01 CUỘC GỌI / 24 GIỜ** tới một số điện thoại.
- **Chế tài xử phạt:** Phạt tiền 20 - 30 triệu VNĐ nếu gọi ngoài giờ hoặc không có Brandname; phạt 80 - 100 triệu VNĐ nếu gọi vào danh sách DNC 5656; thu hồi đầu số và Brandname nếu vi phạm nhiều lần.

### 3.2. Giải pháp Bài toán "Day-1 Onboarding" (Sẵn sàng gọi trong 24 giờ)
Thủ tục cấp Giấy chứng nhận Tên định danh tại Cục An toàn thông tin mất 1 - 3 ngày, nhưng quy trình khai báo định tuyến tại 4 nhà mạng lớn (Viettel, VNPT, MobiFone, Vietnamobile) kéo dài **15 đến 30 ngày làm việc**. Để không làm đứt gãy chỉ số Time-to-Value (TTV) của khách hàng, Nowing thiết lập mô hình **Tiếp cận Đa tầng (Tiered Onboarding)**:

```
[Khách hàng Doanh nghiệp Onboard Epic 38]
                   |
         +---------+-----------------------------------------+
         |                                                   |
         v                                                   v
 [DAY-1 TỨC THÌ (TRONG 24 GIỜ)]              [WEEK 2-4 (CHÍNH THỨC TOÀN DIỆN)]
 - Cấp SIP Trunk Đầu số Cố định              - Nộp hồ sơ Cục ATTT qua Nowing Portal
   Doanh nghiệp (024/028-7xxx / 024-9xxx)    - Hợp tác khai báo viễn thông với Aggregator
 - Kích hoạt WebRTC Sandbox nội bộ           - Khi hoàn tất: Tự động chuyển đổi sang
 - Giới hạn: Chỉ chạy "Warm Lead Calling"      Voice Brandname cho toàn bộ chiến dịch
   (Post Mini-Pitch, RSVP, Đăng ký Form)
```

1. **Cơ chế Day-1: Cấp nhanh SIP Trunk Đầu số Cố định Doanh nghiệp (DID 024/028-7xxx):**
   - Hợp tác với FPT Telecom / CMC Telecom cấp dải đầu số cố định định danh doanh nghiệp trong vòng 4 - 8 giờ làm việc (chỉ yêu cầu bản scan GPKD).
   - Đầu số cố định có độ tín nhiệm cao, không bị các nhà mạng quét như sim di động 09x.
   - **Ràng buộc an toàn:** Khóa cứng phạm vi kịch bản ở dạng **Warm Lead Outbound** (người vừa xem Mini-Pitch Portal, khách đăng ký webinar, khách tải tài liệu). Do khách hàng đã có hành vi tương tác từ trước, cuộc gọi không bị quy kết là "quảng cáo mù không có sự đồng ý", giảm thiểu 99% rủi ro khiếu nại spam.
2. **Môi trường Sandbox WebRTC Không rủi ro:**
   - Cung cấp tính năng gọi thử nghiệm qua WebRTC trên trình duyệt cho tối đa 30 cuộc gọi nội bộ (tới số điện thoại của chính nhân viên Tenant) để tinh chỉnh prompt, kiểm tra chất lượng giọng đọc và kiểm tra kịch bản trước khi gọi khách thật.
3. **Quy trình Ủy quyền Đăng ký Brandname Chính thức (Tuần 2 - 4):**
   - Tenant tải hồ sơ pháp lý (Mẫu số 01 NĐ 91, GPKD, Giấy chứng nhận sở hữu nhãn hiệu) qua giao diện Settings của Nowing.
   - Đối tác Aggregator (FPT/Stringee) đại diện xử lý nộp hồ sơ và nghiệm thu liên mạng. Khi Brandname được kích hoạt, hệ thống tự động chuyển đổi phương thức quay số sang Brandname mà không làm gián đoạn chiến dịch.

### 3.3. Cơ chế Tuân thủ Kỹ thuật (Compliance Engine)

1. **Pre-call Safety Gate (Cổng kiểm soát 4 lớp trước khi quay số):**
   - **Curfew Enforcement:** Kiểm tra thời gian hệ thống. Chỉ cho phép gọi từ **09:00 - 11:30** và **13:30 - 17:00** từ Thứ Hai đến Thứ Sáu. Tự động đưa vào hàng đợi trễ nếu ngoài khung giờ hoặc ngày lễ/Tết.
   - **Frequency Cap Check:** Truy vấn Redis/Postgres xác thực số điện thoại E.164 chưa nhận bất kỳ cuộc gọi nào từ Workspace trong vòng 24 giờ qua.
   - **National DNC 5656 Integration:** Gọi `DncComplianceService` tại `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/lead_intelligence/dnc/service.py` đối chiếu hàm băm `hash_phone_hmac(e164)` với `GlobalDncRecord`. Nếu trùng khớp, hủy lệnh gọi ngay lập tức, hoàn trả credit.
   - **Workspace DNC & Suppress List:** Kiểm tra danh sách khách hàng đã từng từ chối qua các kênh khác (Zalo, Email, SMS).
2. **In-call Dual Realtime Opt-out (Cơ chế từ chối tức thì):**
   - **DTMF Tone 9/0:** Trong lời chào mở đầu hoặc kết thúc, bot luôn thông báo: *"Để từ chối nhận cuộc gọi tương tự, quý khách vui lòng bấm phím 9"*. Media Gateway bắt mã DTMF RFC 2833 -> Bot xin lỗi ngắn gọn -> Cúp máy trong 2 giây.
   - **Voice Rejection Intent:** STT + NLU nhận diện các câu từ chối tiếng Việt ("không có nhu cầu", "đừng gọi nữa", "làm phiền quá", "xóa số tôi đi") với độ tin cậy $\ge 0.75$ -> Bot lịch sự xin lỗi và cúp máy ngay lập tức.
   - **Post-call Sync:** Tự động ghi số điện thoại vào `WorkspaceDncRecord`, đánh dấu `VerifiedContact.consent_status = 'opt_out'` trong CRM và lưu log vào `pii_access_audit_logs`.
3. **In-flight Anti-Spam Circuit Breaker (Cầu dao ngắt khẩn cấp):**
   - Áp dụng nguyên tắc Canary Batch: Chiến dịch mới chỉ được gọi thử 30 - 50 cuộc đầu tiên.
   - **Tự động ngắt khẩn cấp chiến dịch** nếu vi phạm một trong các ngưỡng:
     - Tỷ lệ ngắt máy dưới 5 giây (Instant Drop Rate) $> 40\%$.
     - Tỷ lệ khách chửi bới / phản ứng tiêu cực (Hostile Intent Score) $> 6\%$.
     - Tỷ lệ bấm phím 9 hoặc yêu cầu dừng cuộc gọi $> 10\%$.
     - Tỷ lệ trùng DNC Quốc gia trong tệp tải lên $> 2.5\%$.
   - Khi cầu dao kích hoạt, chiến dịch lập tức dừng lại, hoàn trả credit chưa gọi và yêu cầu Tenant giải trình nguồn gốc danh bạ.

---

## PHẦN 4: BÀI TOÁN KINH TẾ & MÔ HÌNH ĐỊNH GIÁ (UNIT ECONOMICS & PRICING)

### 4.1. Bảng Chi phí Cấu thành (COGS Breakdown) trên 1 Phút Gọi

| Thành phần chi phí | Đơn vị cung cấp | Chi phí / Phút (VNĐ) | Tỷ trọng COGS (%) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- | :--- |
| **Cước viễn thông SIP Trunk** | Viettel / VNPT / FPT | 820 VNĐ | 78.8% | Blended: 60% Viettel, 30% VNPT, 10% Mobi; Block 6s+1s |
| **Speech-to-Text (STT)** | FPT.AI / Deepgram | 110 VNĐ | 10.6% | WebSocket streaming thời gian thực |
| **LLM Reasoning (Haiku)** | Anthropic Claude 3.5 Haiku | 35 VNĐ | 3.4% | Prompt caching, rolling 2-turn window (~1.200 tokens) |
| **Text-to-Speech (TTS)** | Cartesia Sonic / Vbee | 30 VNĐ | 2.9% | PCM streaming, trung bình bot nói 50% thời lượng cuộc gọi |
| **Media Gateway & VAD Server** | Cụm Cloud LiveKit/SBC | 45 VNĐ | 4.3% | Phân bổ hạ tầng máy chủ trên 100 kênh đồng thời |
| **TỔNG COGS / 1 PHÚT GỌI** | | **1.040 VNĐ** | **100%** | **Tương đương ~0.041 USD / phút kết nối** |

### 4.2. Hàng rào Bảo vệ Biên lợi nhuận (Anti-Bleeding Safeguards)
Để loại trừ các lỗ hổng tài chính đã được chỉ ra trong đợt phản biện độc lập:
1. **Khống chế Chính sách Bảo vệ Dập máy dưới 10 giây (Hang-up Protection Cap):**
   - Miễn phí 100% cho các cuộc gọi dập máy dưới 10 giây, nhưng **áp dụng tỷ lệ trần tối đa 15% tổng số cuộc gọi của chiến dịch**.
   - Mọi cuộc gọi dập máy dưới 10 giây vượt quá hạn mức 15% sẽ bị tính phí tối thiểu 0,5 phút (1.250 VNĐ) để bù đắp chi phí viễn thông thực tế mà Nowing phải trả cho nhà mạng.
2. **Answering Machine Detection (AMD) & Telecom Classifier:**
   - Phân tích tín hiệu âm thanh trong 3 giây đầu. Nếu nhận diện tiếng chuông nhà mạng, nhạc chờ hoặc giọng đọc tổng đài ("Thuê bao quý khách..."), thực hiện lệnh SIP `BYE` ngắt cuộc gọi ngay trong **dưới 4 giây**, tiết kiệm 100% chi phí LLM và TTS.
3. **Dead-air Silence Timeout (3s + 5s):**
   - Sau câu chào của bot, nếu khách hàng nhấc máy nhưng im lặng trong 3 giây -> Bot phát câu nhắc: *"Alo, anh/chị có nghe rõ em nói không ạ?"*. Nếu tiếp tục im lặng trong 3 giây tiếp theo -> Bot tự động cúp máy. Thời lượng kiểm soát dưới 8 giây.
4. **Hard Call Ceiling 180s:**
   - Chặn cứng thời lượng tối đa 3 phút (180 giây) cho mọi cuộc gọi SDR. Tại giây 150, bot tự động chào kết thúc và hướng dẫn kết nối qua Zalo, sau đó cúp máy tại giây 180.

### 4.3. Đề xuất Mô hình Gói cước (Hybrid Value-Tier Pricing)

Tích hợp trực tiếp vào hệ thống thanh toán và cổng quản lý gói cước của Nowing (kế thừa Epic 37.7):

```
+--------------------------------------------------------------------------------------------------+
| GÓI VOICE AI STARTER: 1.490.000 VNĐ / tháng                                                      |
| - Phù hợp: Doanh nghiệp SME bắt đầu thử nghiệm Outbound.                                         |
| - Bao gồm: 1 Voice Agent, 400 phút đàm thoại tiêu chuẩn, kết nối 1 đầu số SIP Trunk cố định.     |
| - Cước vượt gói: 2.800 VNĐ / phút.                                                               |
+--------------------------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------------------------+
| GÓI VOICE AI GROWTH: 3.490.000 VNĐ / tháng                                                        |
| - Phù hợp: Đội ngũ B2B Sales chuyên nghiệp cần mở rộng quy mô.                                   |
| - Bao gồm: 3 Voice Agents song song, 1.200 phút đàm thoại, hỗ trợ Voice Brandname chính danh,    |
|   kích hoạt Speed-to-Lead từ Mini-Pitch Portal, đồng bộ Zalo Co-pilot & CRM.                     |
| - Cước vượt gói: 2.400 VNĐ / phút.                                                               |
+--------------------------------------------------------------------------------------------------+
```

- **Biên lợi nhuận gộp (Gross Margin):** Đạt **58.4%** trên mỗi phút đàm thoại tiêu thụ (Doanh thu 2.500 VNĐ, COGS 1.040 VNĐ).

### 4.4. Cơ chế Trừ Credit trong Nowing Wallet
1. **Pre-call Soft Lock:** Khi khởi tạo cuộc gọi, hệ thống tạm giữ (soft-lock) số dư tương đương **3 phút gọi tối đa (7.500 VNĐ)** trong ví tín dụng của Workspace. Nếu số dư khả dụng không đủ 7.500 VNĐ, cuộc gọi không được phép khởi tạo.
2. **Real-time Stream Metering:** LiveKit SIP Gateway gửi bản tin ghi nhận cước mỗi 10 giây vào Redis key `voice:session:<call_id>:metering`.
3. **Post-call Final Settlement (Celery Task):**
   - Khi nhận SIP `BYE`, tính toán thời lượng đàm thoại thực tế theo block 6s + 1s.
   - Nếu cuộc gọi dưới 10 giây (và nằm trong hạn mức 15% của chiến dịch): Giải phóng 100% số tiền tạm giữ, ghi nhận 0 VNĐ.
   - Nếu cuộc gọi hợp lệ: Khấu trừ số tiền thực tế (Thời lượng làm tròn x Đơn giá phút), hoàn trả phần tiền tạm giữ còn lại vào ví.

---

## PHẦN 5: DANH MỤC STORIES ĐỀ XUẤT CHO EPIC 38 (PROPOSED EPIC 38 STORY BREAKDOWN)

Hệ thống được chia thành **3 Làn sóng triển khai (Waves)** với 8 Stories chi tiết:

```
[ WAVE 1: NỀN TẢNG MEDIA & INBOUND CONFIRMATION (Tuần 1 - 2) ]
  ├── Story 38.1: LiveKit SIP Gateway & Kamailio Media Infrastructure
  ├── Story 38.2: Voice Agent Worker Runtime với Silero VAD & Micro-clause Streaming
  └── Story 38.8: Voice Billing, Nowing Wallet Realtime Metering & QA Scorecard

[ WAVE 2: WARM OUTBOUND & SPEED-TO-LEAD ENGINE (Tuần 3 - 4) ]
  ├── Story 38.4: Telephony Compliance Gate, National DNC 5656 & Curfew Scheduler
  ├── Story 38.5: Telecom Signal Classifier, AMD & Dead-air Watchdog Engine
  └── Story 38.7: Outbound Trigger Engine: Speed-to-Lead & Hiring Radar Integration

[ WAVE 3: ADVANCED BARGE-IN & BRANDNAME GATEWAY (Tuần 5 - 6) ]
  ├── Story 38.3: Anti-False-Interruption & Multi-tier Barge-in Engine (Ducking + KWS)
  └── Story 38.6: Dynamic DID & Voice Brandname Multi-tenant BYO-SIP Architecture
```

---

### WAVE 1: NỀN TẢNG MEDIA & INBOUND CONFIRMATION (TUẦN 1 - 2)

#### Story 38.1: LiveKit SIP Gateway & Kamailio Media Infrastructure
- **User Story:** Là System Architect, tôi muốn thiết lập cụm máy chủ Kamailio SBC và LiveKit SIP Gateway kết nối WebRTC SFU, để hệ thống có thể chuyển đổi giao thức thoại SIP viễn thông sang WebRTC thời gian thực với độ trễ nội bộ dưới 5ms.
- **Tóm tắt Acceptance Criteria:**
  - Cụm Kamailio SBC triển khai thành công tại Datacenter Việt Nam, hỗ trợ nhận SIP UDP G.711a (PCMA 8kHz) từ Telco và đẩy sang LiveKit SIP Gateway qua mạng nội bộ.
  - LiveKit SIP Gateway tự động khởi tạo LiveKit Room `call_<session_uuid>` ngay khi nhận SIP `INVITE`.
  - Hỗ trợ chuyển đổi Codec hai chiều: G.711a 8kHz sang WebRTC Audio Track (Opus 48kHz) và ngược lại không gây méo tiếng.
  - Độ trễ truyền dẫn nội bộ giữa SBC, SIP Gateway và Media Server SFU kiểm soát $P99 < 3ms$.

#### Story 38.2: Voice Agent Worker Runtime với Silero VAD & Micro-clause Streaming
- **User Story:** Là Backend Engineer, tôi muốn phát triển tiến trình Voice Agent Worker bằng Python Asyncio kết nối LiveKit Room, để thực thi vòng lặp đàm thoại AI kết hợp STT, LLM và TTS dạng streaming.
- **Tóm tắt Acceptance Criteria:**
  - Worker kết nối LiveKit Room như một participant thông thường, đọc ghi âm thanh qua `livekit-agents` SDK.
  - Tích hợp Silero VAD v5 chạy qua ONNX C++ Runtime với frame size 30ms trên CPU.
  - Thiết lập kênh WebSocket kết nối tới FPT.AI / Deepgram STT và Cartesia / Vbee TTS.
  - Hiện thực hóa bộ đệm Micro-clause Token Accumulator: đẩy text sang TTS ngay khi gặp dấu câu hoặc từ thứ 3 - 5 của câu.
  - Kích hoạt Local Filler Audio ("Dạ vâng anh...") trong vòng 80ms từ khi khách dứt câu nếu LLM chưa trả first token.

#### Story 38.8: Voice Billing, Nowing Wallet Realtime Metering & QA Scorecard
- **User Story:** Là Product Manager, tôi muốn hệ thống quản lý số dư tín dụng cuộc gọi trong Nowing Wallet và tự động đánh giá chất lượng cuộc gọi bằng LLM sau khi cúp máy, để đảm bảo minh bạch tài chính và kiểm soát chất lượng SDR.
- **Tóm tắt Acceptance Criteria:**
  - Thực hiện soft-lock 7.500 VNĐ (tương đương 3 phút) trước khi quay số; từ chối gọi nếu ví không đủ số dư.
  - Áp dụng chính sách Hang-up Protection: miễn phí cuộc gọi dập máy dưới 10 giây trong hạn mức tối đa 15% số cuộc của chiến dịch.
  - Tự động quyết toán cước theo block 6s + 1s qua Celery task `process_post_call_analytics`.
  - LLM tự động trích xuất Call Summary, BANT qualification status và chấm điểm tuân thủ kịch bản (QA Score 1 - 100).

---

### WAVE 2: WARM OUTBOUND & SPEED-TO-LEAD ENGINE (TUẦN 3 - 4)

#### Story 38.4: Telephony Compliance Gate, National DNC 5656 & Curfew Scheduler
- **User Story:** Là Compliance Officer, tôi muốn một cổng kiểm soát an toàn trước và trong cuộc gọi, để đảm bảo 100% cuộc gọi tuân thủ Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP.
- **Tóm tắt Acceptance Criteria:**
  - Curfew Scheduler chặn tuyệt đối lệnh gọi ngoài khung giờ 09:00 - 11:30 và 13:30 - 17:00 (ICT), tự động chặn vào Thứ Bảy, Chủ Nhật và ngày nghỉ lễ.
  - Frequency Cap kiểm tra không gọi quá 1 cuộc/24 giờ tới cùng một số thuê bao E.164.
  - Tích hợp `DncComplianceService` (kế thừa `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/lead_intelligence/dnc/service.py`) đối chiếu hàm băm SĐT với Danh sách DNC 5656 của Cục An toàn thông tin; lập tức hủy lệnh gọi nếu nằm trong DNC.
  - Bắt buộc phát câu thông báo ghi âm cuộc gọi trong 3 giây đầu tiên.
  - Hỗ trợ phím số DTMF 9/0 và nhận diện giọng nói từ chối ("không có nhu cầu", "đừng gọi nữa") để cúp máy trong 2 giây và tự động ghi vào `WorkspaceDncRecord`.

#### Story 38.5: Telecom Signal Classifier, AMD & Dead-air Watchdog Engine
- **User Story:** Là System Architect, tôi muốn hệ thống phát hiện chính xác tiếng chuông nhà mạng, hộp thư thoại và trạng thái im lặng sau nhấc máy, để cúp máy sớm và ngăn chặn rò rỉ ngân sách viễn thông.
- **Tóm tắt Acceptance Criteria:**
  - Module Answering Machine Detection (AMD) phân tích âm thanh trong 3 giây đầu, nhận diện tiếng chuông viễn thông hoặc lời chào tổng đài ("Thuê bao quý khách...") và gửi SIP `BYE` trong $< 4$ giây.
  - Cơ chế Dead-air Watchdog: Nếu người dùng bắt máy nhưng im lặng 3 giây, bot phát câu nhắc "Alo, anh/chị nghe rõ không ạ?"; nếu tiếp tục im lặng thêm 3 giây, tự động cúp máy trước 8 giây.
  - Áp đặt thời lượng trần cứng 180 giây (3 phút) cho toàn bộ cuộc gọi outbound.
  - Khởi tạo Redis heartbeat 1s trên Worker; RTPEngine tự động ngắt kết nối SIP nếu luồng RTP ngắt quãng quá 5 giây.

#### Story 38.7: Outbound Trigger Engine: Speed-to-Lead & Hiring Radar Integration
- **User Story:** Là B2B Sales Rep, tôi muốn các cuộc gọi Voice SDR tự động kích hoạt khi có tín hiệu tuyển dụng hoặc khi khách hàng đang xem tài liệu Mini-Pitch Portal, để tiếp cận khách hàng đúng thời điểm có nhu cầu cao nhất.
- **Tóm tắt Acceptance Criteria:**
  - Tích hợp với Sequencer và Intent Radar: kích hoạt cuộc gọi khi phát hiện doanh nghiệp đăng tin tuyển dụng vị trí mục tiêu trong vòng 48 giờ.
  - Tích hợp Speed-to-Lead: tự động kích hoạt cuộc gọi thoại trong vòng 5 phút sau khi prospect mở xem tài liệu Mini-Pitch Portal trên 45 giây (Epic 37.5 & 37.6).
  - Tự động nạp ngữ cảnh (tên công ty, tên người liên hệ, vị trí tuyển dụng, nội dung tài liệu đã xem) vào System Prompt của Agent trước khi quay số.
  - Sau cuộc gọi, tự động kích hoạt gửi tài liệu tóm tắt qua Zalo ZNS / Zalo Co-pilot cá nhân (Epic 37.4).

---

### WAVE 3: ADVANCED BARGE-IN & BRANDNAME GATEWAY (TUẦN 5 - 6)

#### Story 38.3: Anti-False-Interruption & Multi-tier Barge-in Engine (Ducking + KWS)
- **User Story:** Là người nghe cuộc gọi, tôi muốn có thể ngắt lời bot một cách tự nhiên và bot không bị dừng nói ngớ ngẩn khi có tiếng ồn xe máy hoặc khi tôi nói tiếng đệm ("ừ", "dạ"), để cuộc hội thoại diễn ra mượt mà như người thật.
- **Tóm tắt Acceptance Criteria:**
  - Kích hoạt Barge-in Lockout Guard trong 400ms đầu tiên của mỗi lượt bot nói để loại bỏ triệt để âm vọng Echo dội từ loa ngoài.
  - Khi phát hiện âm thanh có xác suất tiếng nói $P \ge 0.88$, tự động giảm âm lượng bot xuống -14dB (Audio Ducking) thay vì ngắt đột ngột.
  - Tích hợp bộ Keyword Spotting (KWS) cục bộ: Nếu âm thanh ngắn $< 280ms$ hoặc là hư từ đệm ("ừ", "dạ", "vâng", "nghe đây"), khôi phục âm lượng bot về 0dB tiếp tục phát.
  - Nếu xác nhận khách hàng cướp lời thực sự: Gửi SIP Silence Packet (40ms), hủy toàn bộ task Asyncio LLM/TTS đang chạy, trích xuất chính xác từ bot đã nói dở để nạp vào prompt ngữ cảnh lượt sau (`[Interrupted by user]`).

#### Story 38.6: Dynamic DID & Voice Brandname Multi-tenant BYO-SIP Architecture
- **User Story:** Là Quản trị viên Workspace, tôi muốn cấu hình SIP Trunking riêng và khai báo hồ sơ Voice Brandname chính danh, để màn hình người nhận hiển thị đúng tên thương hiệu công ty tôi khi bot gọi đến.
- **Tóm tắt Acceptance Criteria:**
  - Cho phép Workspace cấu hình SIP Trunking credentials (SIP Domain, Port, Username, Password, Caller ID/Brandname) và lưu trữ mã hóa chuẩn AES-256-GCM trong PII Vault.
  - Cung cấp luồng Instant Onboarding Day-1: Cấp đầu số cố định DID (024/028-7xxx) cho phép gọi ngay trong ngày cho các kịch bản Warm Lead.
  - Cung cấp cổng tiếp nhận hồ sơ đăng ký Voice Brandname (GPKD, Mẫu số 01 NĐ 91, Giấy chứng nhận nhãn hiệu) kết nối API với đối tác viễn thông Aggregator (FPT/Stringee).
  - Tích hợp In-flight Anti-Spam Circuit Breaker: Tự động ngắt chiến dịch khẩn cấp nếu tỷ lệ cuộc gọi dưới 5 giây $> 40\%$ hoặc tỷ lệ khiếu nại spam $> 6\%$.

---

## PHẦN 6: KẾT LUẬN & CAM KẾT CHẤT LƯỢNG SẢN PHẨM

Bản kế hoạch kiến trúc và chiến lược này là sự kết hợp chặt chẽ giữa:
1. **Năng lực kỹ thuật đỉnh cao từ Winston & Murat:** Phá vỡ rào cản RTT viễn thông bằng Local Filler Audio Injection, Multi-tier Ducking Barge-in và kiến trúc Kamailio + LiveKit SIP Gateway.
2. **Khung pháp lý vững chắc từ Mary:** Bảo vệ Nowing và khách hàng khỏi các án phạt 100 triệu VNĐ của Nghị định 91/2020/NĐ-CP thông qua bộ lọc DNC Quốc gia, Curfew hành chính và giải pháp Day-1 Onboarding với đầu số cố định.
3. **Mô hình kinh tế bền vững từ John:** Khóa chặt biên lợi nhuận gộp $> 58\%$ nhờ hạn mức Hang-up Protection Cap 15%, module AMD dập hộp thư thoại $< 4s$, và giới hạn trần cuộc gọi 180s.

Epic 38 khi hoàn thành sẽ đưa Nowing trở thành nền tảng B2B Sales Automation đầu tiên tại Việt Nam sở hữu trạm thoại AI tự hành chuẩn pháp lý, kết nối liền mạch giữa dữ liệu doanh nghiệp và tương tác thoại thời gian thực.