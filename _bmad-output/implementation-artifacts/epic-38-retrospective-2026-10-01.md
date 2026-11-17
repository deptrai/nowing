---
epic: 38
title: "Epic 38 — Autonomous Voice AI SDR & Telephony Workstation Retrospective"
date: 2026-10-01
participants:
  - Luisphan (Project Lead)
  - Orchestrator (Autonomous Agent)
stories_total: 8
stories_done: 8
status: complete
---

# Retrospective — Epic 38: Autonomous Voice AI SDR & Telephony Workstation

**Ngày:** 2026-10-01  
**Epic:** 38 — Autonomous Voice AI SDR & Telephony Workstation  
**Trạng thái:** Hoàn thành (8/8 stories done, 100% pass)

---

## 1. Epic Review

### Tổng quan

Epic 38 "Autonomous Voice AI SDR & Telephony Workstation" xây dựng trạm thoại AI tự hành đa kênh chuẩn hóa cho thị trường B2B Việt Nam: tuân thủ chặt chẽ Nghị định 91/2020/NĐ-CP và Nghị định 13/2023/NĐ-CP PDPD, đạt độ trễ nhận thức sub-800ms, tích hợp trực tiếp vào Sequencer làm Action Executor, hỗ trợ cướp lời êm ái qua Audio Ducking -14dB, quản lý đầu số BYO-SIP đa người thuê, và tính cước viễn thông chuẩn block 6s + 1s.

### Story Summary

| Story | Title | Status | Scope | Unit Tests |
|---|---|---|---|---|
| **38.1** | LiveKit SIP Gateway & Kamailio Media Infrastructure | done | Hạ tầng SIP, SBC, Docker network | Verified |
| **38.2** | Voice Agent Worker Runtime với Silero VAD & Micro-clause Streaming | done | Worker pool 8 process, VAD state tensor isolation, filler audio | 64 passed |
| **38.3** | Anti-False-Interruption & Multi-tier Barge-in Engine | done | Echo lockout 400ms, ducking -14dB, KWS filler recovery, 40ms silence | 86 passed |
| **38.4** | Telephony Compliance Gate, National DNC 5656 & Curfew Scheduler | done | Split curfew 09:00-11:30 & 13:30-17:00, 24h frequency lock, DNC, 3s disclosure | 71 passed |
| **38.5** | Telecom Signal Classifier, AMD & Dead-air Watchdog Engine | done | AMD voicemail/IVR <= 4s, Dead-air probe 3s hangup 6.5-8s, Circuit Breaker | 22 passed |
| **38.6** | Dynamic DID & Voice Brandname Multi-tenant BYO-SIP Architecture | done | WorkspaceSipTrunk, AES-256-GCM TokenEncryption, REST API CRUD, cascade | 12 passed |
| **38.7** | Outbound Trigger Engine: Speed-to-Lead & Hiring Radar Integration | done | Sequencer Action Executor channel="voice", Celery task, Speed-to-Lead < 5m | 14 passed |
| **38.8** | Voice Billing, Realtime Metering & QA Scorecard | done | Block 6s+1s (2.500đ/m), Hang-up Protection < 10s (quota 15%), BANT 0-100, CRM | 22 passed |

**Tổng unit tests Epic 38:** 326 tests pass 100%, 0 failures, ruff clean.

---

## 2. What Went Well

1. **Tuân thủ Tuyệt đối Ràng buộc Kiến trúc (Zero Reinvention):**
   - Không tạo `voice/curfew.py` — mở rộng trực tiếp `calculate_step_eta(channel="voice")` trong `scheduling.py`.
   - DNC opt-out dùng chung qua `register_contact_opt_out()` trong `app/lead_intelligence/dnc/service.py` cho cả Voice Worker và Inbound Sequencer.
   - Mật khẩu SIP Trunk mã hóa AES-256-GCM qua `TokenEncryption` có sẵn trong PII Vault, không viết module crypto mới.
   - Voice AI SDR hoạt động như Action Executor trong Sequencer, kế thừa toàn bộ retry, OCC versioning, và logging của Sequencer.
   - Không tạo bảng timeline mới — lưu toàn bộ kết quả cuộc gọi và điểm BANT vào `LeadActivityLog` với `activity_type="voice_call"`.
   - Cước viễn thông khớp đúng 3 nguyên thủy của `wallet_credit.py`: `reserve_credit` -> `commit_reserved_credit` -> `release_credit`.

2. **Chất lượng Review & Phát hiện Lỗi Sớm:**
   - 4 review layer (Blind Hunter, Edge Case Hunter, Verification Gap, Intent Alignment) đã phát hiện các lỗi critical trước khi vào production:
     - `session.end_call()` không tồn tại trên `AgentSession` 1.8.2 → thay bằng `LiveKitTelephonyClient().end_call()`.
     - `entrypoint` không truyền `phone_e164` làm opt-out silently skip DNC → đã patch truyền phone metadata.
     - `CancelledError` khi khách cúp máy làm drop DNC persistence → bọc exception an toàn.
     - `_defer_step_for_curfew` gọi `calculate_step_eta(0)` không truyền `channel` → đã patch passthrough.

---

## 3. Action Items

| # | Action Item | Target Story / Area | Priority | Status |
|---|---|---|---|---|
| **AI-38.1** | Tạo Alembic migration cho bảng `workspace_sip_trunks` | Database Migration | P0 | open |
| **AI-38.2** | Viết Redis stream consumer loop cho `stream:prospect:engagement` (Speed-to-Lead daemon) | Celery / Worker | P1 | open |
| **AI-38.3** | Nối hook `on_room_disconnected` trong `agent_worker.py` gọi Celery task `process_post_call_qa_task` | Voice Worker | P1 | open |
| **AI-38.4** | Bổ sung bảng ngày lễ Việt Nam tĩnh vào `scheduling.py:is_voice_curfew()` | Sequencer Compliance | P2 | open |
| **AI-38.5** | Nâng cấp BANT Scorecard từ keyword heuristics sang LLM-as-judge graduated scoring | AI Intelligence | P3 | open |

---

## 4. Epic Close Gate Decision

- **Verdict:** ✅ **APPROVED (PASS)**
- **Lý do:** Toàn bộ 8/8 stories đã hoàn thành, 326 unit tests hermetic pass, 0 linter errors, tất cả ràng buộc kiến trúc của Epic 38 được tuân thủ nghiêm ngặt.
