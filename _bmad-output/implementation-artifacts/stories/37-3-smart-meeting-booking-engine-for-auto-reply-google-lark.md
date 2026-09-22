---
story_key: 37-3-smart-meeting-booking-engine-for-auto-reply-google-lark
status: done
baseline_commit: d51120fed4172738bf9d7e5d51b6f45c55bc5927
epic: 37
priority: P1
target_codebase: nowing_backend
architectural_invariants: [AD-117]
---

# Story 37.3: Smart Meeting Booking Engine for Auto-Reply (Google & Lark Calendar)

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`  
**Architectural Alignment:** Extends `app/services/sequencer/inbound.py` and CRM pipeline routes.

## Story

As an Account Executive,  
I want the two-way AI auto-reply agent to extract my calendar availability and propose concrete meeting slots when a prospect shows interest,  
So that meetings are booked automatically into my calendar without back-and-forth scheduling ping-pong.

## Acceptance Criteria

- **AC-1 (Calendar Free/Busy Extraction):** Integrates Google Calendar & Lark Calendar APIs using workspace credentials to query free/busy slots across 5 upcoming business days, restricted strictly to working hours (09:00–12:00, 13:30–17:30 ICT, Monday–Friday) with a 15-minute buffer before/after existing events.
- **AC-2 (Redis Soft-Lock Concurrency Guard):** Proposed meeting slots are soft-locked in Redis with a 15-minute TTL (`lock:calendar_slot:{user_id}:{slot_timestamp}`) per AD-117 to prevent double-booking across concurrent prospect conversations.
- **AC-3 (Slot Proposal Generation):** When positive meeting intent is detected, the agent proposes exactly 2-3 specific time options formatted in ICT ("14:00 Thứ Ba" hoặc "10:00 Thứ Năm").
- **AC-4 (Auto-Booking & CRM Sync):** Automatically creates calendar event upon prospect confirmation, sends calendar invites with Google Meet/Lark link, releases Redis soft lock, and updates CRM lead status to `meeting_scheduled`.
- **AC-5 (Negotiation Limit & Fallback Link):** If the prospect rejects proposed slots across 2 negotiation turns, the agent provides a direct booking page link and appends a `human_takeover_needed` tag.

## Review Triage Log

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | Stale confirm books past/conflicted slot (state 24h vs lock 15min) | high | patch | `book_slot` now re-checks `slot.start > now` + `_ensure_slot_lock` NX-reacquire w/ token compare → `slot_past`/`lock_lost` |
| 2 | Lock namespace split (`_propose` caller uid vs route `credentials[0]`) | high | patch | `pick_owner_credential` — one owner credential per conversation; route + propose + state share its `user_id` |
| 3 | Route leaks lock on success; duplicate resolve | medium | patch | release on success added; `book_slot` accepts `credentials`/`lock_token` params |
| 4 | `release_slot_locks` deletes foreign locks after TTL | medium | patch | uuid token value + `_RELEASE_LOCK_LUA` compare-and-delete |
| 5 | `meeting/slots` returns locked slots | medium | patch | route filters existing `lock:` keys (fail-closed on Redis error) |
| 6 | VN parser gaps (chiều/tối, "thứ hai" ordinal collide, negations, bare digit, choice-vs-reject order, bare "hẹn") | high | patch | `_NEGATION_RE` + `_phrase_present`, sáng/trưa/chiều/tối shift, weekday aliases before ordinals, digit pick, choice checked first, "hẹn"/"đặt hẹn" added |
| 7 | `meeting_scheduled` stage missing from `DEFAULT_STAGES` | medium | patch | stage added (position 3); existing pipelines keep graceful fallback |
| 8 | `/book/{ws}/{lead}` page doesn't exist | medium | defer | nowing_web has no `/book` route — separate frontend deliverable; `MEETING_BOOKING_BASE_URL` can point at external page meanwhile |
| 9 | Lark `calendar_id="primary"` default + freebusy `items`/`user_id` shape | medium | patch | `calendar_id` required (raises); `user_id` top-level + `user_id_type` param; `items=[{calendar_id}]`. Live Lark verify deferred — no connector creds exist |
| 10 | `_google_native_busy` blocks event loop | medium | patch | `asyncio.to_thread` wrap; connector built session=None |
| 11 | `MeetingBookRequest` unvalidated (naive/past start, no EmailStr) | medium | patch | `EmailStr` + tz-aware required + `>= now+MIN_NOTICE` validator |
| 12 | Orphaned locks: `thread_id=""`, create_event raise, blanket except | medium | patch | early `None` on falsy thread_id; `_confirm_slot` releases picked lock on failure |
| 13 | `_handle_rejection` fallback loses rejections count → escalation unreachable | medium | patch | state saved (incremented rejections) in the `or` fallback branch |
| 14 | `pause_auto_reply` failure at debug level | low | patch | warning |
| 15 | `event_id=None` still marks `meeting_scheduled`; "invite sent" w/o attendee | medium | patch | missing event_id → `create_failed`; reply branches on attendee presence |
| 16 | Hot-lead dup block unguarded in meeting early-return | low | patch | extracted `_maybe_alert_hot_lead()` w/ try/except, shared with step 7 |
| 17 | `LARK_CALENDAR_CONNECTOR` missing from `LIVE_CONNECTOR_TYPES` | medium | patch | added; indexing/scheduler treat like Google calendar siblings |
| 18 | `resolve_credentials` ordered by nonexistent `updated_at` | medium | patch | `created_at` (found by new test) |
| 19 | `generate_reply` meeting interception untested — feature could be dead w/ green suite | high | patch | test asserts proposal reply returned, RAG skipped |
| 20 | Route endpoints zero coverage | medium | patch | 400/409/502(lock released)/200(commit+status) tests |
| 21 | `resolve_credentials` provider mapping mocked everywhere | medium | patch | connector_type→provider mapping test |
| 22 | `create_meeting_room` param forwarding unpinned | low | patch | execute_tool params assertion test |
| 23 | Lark OAuth/connect route absent — provider unreachable | medium | defer | no connector provisioning flow exists; creds must be seeded manually (documented) |
| 24 | Weekday+hour contradiction cross-check ("2h thứ ba") | low | reject | rare + adds parse complexity; worst case = clarify prompt |
| 25 | `handle_turn.attendee_email` never passed by call site | low | reject | legit override param on service API |
| 26 | `meeting_intent` event_metadata written but unread | false | reject | intended as write-only trace record per AC-1 design |
