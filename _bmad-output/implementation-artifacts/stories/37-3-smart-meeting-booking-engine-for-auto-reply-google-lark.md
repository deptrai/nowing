---
story_key: 37-3-smart-meeting-booking-engine-for-auto-reply-google-lark
status: ready-for-dev
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
