---
story_key: 37-6-realtime-prospect-engagement-tracker-and-telegram-alert-bot
status: done
baseline_commit: d9222f3fa38f7b96987212180a86fac8625a4a9f
epic: 37
priority: P1
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-120]
---

# Story 37.6: Realtime Prospect Engagement Tracker & Telegram Alert Bot Ping

**Status:** `done`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`, `nowing_web`  
**Architectural Alignment:** Extends Telegram Alert Engine (`app/alerts/`, Epic 22.3) and CRM Timeline.

## Story

As a Sales Representative,  
I want real-time notifications sent to my Telegram bot whenever a prospect opens their personalized mini-pitch portal or presentation slides,  
So that I can follow up at the exact moment of peak buyer engagement.

## Acceptance Criteria

- **AC-1 (Lightweight Telemetry Beacon):** Records dwell time, sections viewed, and device type on `pitch.nowing.ai` using `navigator.sendBeacon` without third-party cookies.
- **AC-2 (Beacon Debounce & 30-Minute Cooldown - AD-120):** Limits Telegram push alerts to at most 1 alert per 30 minutes per lead ID via Redis lock (`lock:pitch_beacon:{lead_id}`); subsequent dwell time updates record silently to `LeadActivityTimeline`.
- **AC-3 (Bot Preview Filter):** Discards crawler user-agents (`facebookexternalhit`, `ZaloPC-crawler`) and sessions with dwell time $< 3$s as preview pings.
- **AC-4 (Instant Telegram Push & 1-Click Zalo Link):** Eligible views trigger a Telegram alert to the assigned sales rep with dwell time, section read, and 1-click Zalo chat deep-link.

## Review Triage Log

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `VerifiedContact.phone` là ciphertext Fernet (AD-42/49) — `_resolve_zalo_deep_link` đọc raw → `zalo.me` rác | high | patch | decrypt qua `VerifiedContactEncryption.is_encrypted/decrypt` (pattern `sequencer/dispatch.py:267`); decrypt fail → no link |
| 2 | UA marker `"zalo"`/`"whatsapp"` bare substring filter cả prospect mở link trong Zalo in-app browser (kênh chính) | high | patch | bỏ bare markers; giữ `zalopc-crawler` + prefix `whatsapp/` (preview fetcher là bare `WhatsApp/2.x`, webview giữ Mozilla UA) |
| 3 | Mỗi heartbeat/close INSERT row mới → ~20 duplicate `LeadActivityLog`/session | medium | patch | dedupe theo `session_id`: event sau update row hiện có (merge sections, OR `telegram_alerted`); first event vẫn insert |
| 4 | `visibilitychange→hidden` + `pagehide` đều gửi `close` → duplicate | medium | patch | `closed` guard; hidden chỉ pause dwell, `pagehide` gửi close duy nhất |
| 5 | SSR `getPitchMeta` fetch từ Next server IP → rate-limit bucket dùng chung → 429 → `notFound()` cho prospect thật | high | patch | forward `x-forwarded-for`/`x-real-ip` từ `headers()`; `/meta` limit nới 30→120/min |
| 6 | `_dispatch_telegram_alert` unguarded — exception trước `session.add` → 500, mất timeline row, lock đã burn | high | patch | wrap toàn dispatch; fail → `recorded_silent`, row vẫn ghi |
| 7 | Failed/unsent alert giữ lock → transient failure tắt alert 30 phút | medium | patch | `alert_due && !alerted` → `redis.delete(lock_key)` để retry không bị chặn |
| 8 | `request.body()` buffer trước khi check 16KB | low | patch | check `Content-Length` header trước; post-read check giữ làm fallback (chunked) |
| 9 | `extra` field accepted-unused + `event` free-form string | low | patch | bỏ `extra`; `event` → `Literal["open","heartbeat","close"]` |
| 10 | `crypto.randomUUID()` throw trên non-HTTPS/old browser → mất toàn bộ telemetry | low | patch | fallback `s-{ts}-{rand}` |
| 11 | Crawler filter sau workspace+lead DB lookups → preview ping tốn DB | low | patch | `is_crawler_user_agent` check trước DB trong route (vẫn 204) |
| 12 | Dispatch chain + route 204-contract + wire schema untested (AC-4 mock hết) | high | patch | +26 tests: dispatch happy/no-binding/no-recipient, encrypted-phone zalo link, recipient fallback, MarkdownV2 escape, session dedupe, lock-release, 204 cho crawler/oversized/malformed/unknown, payload schema khớp `send()` shape |
| 13 | Transient meta 5xx → `notFound()` cached 60s trong ISR | medium | patch | null chỉ trên 404 thật; failure khác retry 1 lần `no-store` rồi mới bỏ |
| 14 | Lock re-arm starvation bởi forged beacon | — | reject | claim sai: `SET NX EX` không refresh TTL; forger chỉ burn được 1 window — rủi ro bẩm sinh của capability-URL design |
| 15 | Beacon limiter 429 vi phạm "always-204" | — | reject | 429 không leak existence (uniform), flood-guard đáng giữ hơn; NAT-flood beacon loss chấp nhận được |
| 16 | Numeric `workspace_ref` bỏ qua `published` check | — | reject | numeric refs = internal/testing path (như booking links); published-gate chỉ áp cho branded slug theo AD-119 |
| 17 | Host rewrite `/:a/:b` over-broad trên pitch host | — | reject | pitch.nowing.ai chỉ serve portal; stray 2-segment path 404 vô hại |
| 18 | Telegram `send_message` trong open DB transaction | — | defer | network call giữ tx/connection; đã mitigate bằng try/except + lock-release, reorder cấu trúc lớn hơn scope |
| 19 | Live Telegram delivery + pitch.nowing.ai DNS cutover unverified | — | defer | cần bound Telegram account thật + edge config; unit coverage đủ cho dispatch logic |
