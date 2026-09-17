---
story_key: 37-6-realtime-prospect-engagement-tracker-and-telegram-alert-bot
status: ready-for-dev
epic: 37
priority: P1
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-120]
---

# Story 37.6: Realtime Prospect Engagement Tracker & Telegram Alert Bot Ping

**Status:** `ready-for-dev`  
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
