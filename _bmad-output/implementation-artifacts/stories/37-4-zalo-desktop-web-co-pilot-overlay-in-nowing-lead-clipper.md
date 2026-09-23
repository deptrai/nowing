---
story_key: 37-4-zalo-desktop-web-co-pilot-overlay-in-nowing-lead-clipper
status: done
baseline_commit: 150b7a5a4da3917b2123d0e0a677397159d54d56
epic: 37
priority: P0
target_codebase: apps/chrome-extension, nowing_backend
architectural_invariants: [AD-118]
---

# Story 37.4: Zalo Desktop/Web Co-pilot Overlay in Nowing Lead Clipper

**Status:** `done`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P0  
**Target Codebase:** `apps/chrome-extension`, `nowing_backend`  
**Architectural Alignment:** Extends `apps/chrome-extension/` (Nowing Lead Clipper, Epic 24.4) and `zalo.me/{phone}` assisted link.

## Story

As a Sales Rep using Zalo on browser or desktop,  
I want the Nowing Lead Clipper extension to detect open Zalo chats and provide a 1-click contextual prompt drawer,  
So that I can execute personalized outbound touches with human-in-the-loop control without risking account bans.

## Acceptance Criteria

- **AC-1 (Zalo Chat Target Detection):** Detects active phone/conversation on `chat.zalo.me`, matching with unlocked leads from Nowing. Renders a 36px floating action pill at the right edge, expanding on click into a 320px contextual flyout drawer.
- **AC-2 (Docked Context Drawer):** Displays prospect company context, recent intent signals, and recommended pitch copy with 2 tab options: `[Ngắn gọn]` / `[Kèm link Pitch]`.
- **AC-3 (Semantic Selector & Zero Ban Guarantee):** `Chèn tin nhắn` button populates Zalo's active textbox via semantic selector (`div[contenteditable="true"]`, `div[role="textbox"]`) using standard `InputEvent`/`insertText` per AD-118 without background automated sending, ensuring zero account ban penalty.
- **AC-4 (DNC Blacklist Suppression):** If prospect phone exists in DNC blacklist (Decree 91/2020/NĐ-CP), renders a red warning banner and disables message insertion.
- **AC-5 (Non-Destructive Paste):** If the Zalo input already contains draft text, prompts confirmation before overwriting or appends below.

## Review Triage Log

| # | Finding | Verdict | Evidence |
|---|---------|---------|----------|
| 1 | `GET /leads/copilot-context` shadowed by `GET /leads/{lead_id}` → 422 dead endpoint | **high → patch** | Verified: `routes/__init__.py` included `leads_router` before `lead_clipper_router`; UUID parse of "copilot-context" → 422 on every call, no test caught it (helper-only coverage). Fixed: include order swapped + comment; new route-level test asserts 200 contract. |
| 2 | `setPhone` race — stale fetch overwrites new phone's context | **high → patch** | Verified: no seq guard; rapid conversation switch could land earlier phone's payload last. Fixed: `requestSeq` counter discards mismatched responses. |
| 3 | `ilike(company_name)` treats `%`/`_` as wildcards → cross-company signal leak | **medium → patch** | Verified: claim "ilike = exact match" false. Fixed: `func.lower() ==` equality. |
| 4 | Toast destroyed by `render()` innerHTML reset same tick | **medium → patch** | Verified in `handleInsert`. Fixed: render first, then toast. |
| 5 | Error-retry dead code (`lastPhone` dedup precedes `setPhone`'s error recheck) | **medium → patch** | Verified. Fixed: removed `lastPhone`; `setPhone` dedups and retries on error. |
| 6 | Content script on all `*.zalo.me` + dead `pageHost==='zalo.me'` apex check | **medium → patch** | AC-1 scopes to `chat.zalo.me`; wildcard also let detector latch stray numbers on unrelated subdomains. Fixed: `chat.zalo.me` only, both manifest arrays + gate. |
| 7 | `document.body.innerText` fallback → wrong-phone attribution + layout thrash | **medium → patch** | Verified: first VN-looking number anywhere (sidebar, quoted msg) could hijack pill. Fixed: fallback dropped — URL/anchors/header only. |
| 8 | `phoneFromZaloLink` unanchored regex + raw `m[1]` return | **low → patch** | `notzalo.me/` matched; unvalidated digits returned. Fixed: `new URL` hostname check + `extractPhone` only. |
| 9 | Portal generated for DNC-blocked contact | **medium → patch** | `ensure_pitch_portal` ran even when insert disabled. Fixed: skipped when `dnc_blocked`; `pitch_with_link` falls back to short. |
| 10 | `offsetParent` filter excludes `position:fixed` composers | **low → patch** | Fixed: `getClientRects().length > 0`. |
| 11 | Drawer stays expanded on null phone; insert btn enabled on empty pitch | **low → patch** | Fixed: auto-collapse when `!phone`; btn disabled when `!currentPitch()`. |
| 12 | `errBody.detail` array → `[object Object]`; fetch no timeout; no per-phone cache | **medium → patch** | Verified: 422 detail is an array (the exact path users hit under the shadowing bug). Fixed: `detailToMessage`, `AbortSignal.timeout(15s)`, 60s per-phone SW cache. |
| 13 | Vacuous `test_corrupt_ciphertext_returns_none`; no route-level coverage | **medium → patch** | Assert sat inside `if is_encrypted(...)` — silently passed. Fixed: unconditional assert + `TestCopilotRouteLevel` via ASGITransport on real aggregate router. |
| 14 | `last_updated` rewritten as bare YAML date | **low → patch** | Restored quoted `'MM-DD-YYYY HH:MM'` convention. |
| 15 | `target_codebase` frontmatter pointed at wrong package | **low → patch** | Real clipper is `apps/chrome-extension`; `nowing_browser_extension` is the Story-32 CDP collector. Corrected. |
| 16 | `SignalEvent.confidence` rendered without ×100 | **false** | `radar.py:69` documents confidence on the 0–100 scale (`>= 75`); `Math.round(confidence)%` is correct. |
| 17 | Missing `logger`/`datetime` imports → NameError | **false** | `datetime` imported at :16, `logger` defined at :47; module imports fine (32 tests pass). |
| 18 | `dispatchInsertFallback` fires `beforeinput` before mutation (stale state for handlers) | **false/low** | Spec order is beforeinput→mutate→input — already correct; wholesale `innerText` replace is the accepted last-resort fallback for editors ignoring `execCommand`. |
| 19 | `SignalEvent` has no lead FK — rename drops history, same-name leads share signals | **defer** | Schema lacks `lead_id`/`client_domain` on `signal_events`; adding one is a migration beyond this story. Recorded in deferred-work. |
| 20 | Zalo real-DOM unverifiable (selectors, detection heuristics, composer insert) | **defer** | No live `chat.zalo.me` session available; heuristic detection degrade path is "no pill" (safe). Recorded in deferred-work. |
