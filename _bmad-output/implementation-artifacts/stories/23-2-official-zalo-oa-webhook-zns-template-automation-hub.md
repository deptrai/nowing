---
story_key: 23-2-official-zalo-oa-webhook-zns-template-automation-hub
status: done
epic: 23
---

# Story 23.2: Official Zalo OA Webhook & ZNS Template Automation Hub

**Status:** `done`  
**Epic:** Epic 23 — Lead Capture & Outreach Infrastructure

## Story

As a sales operator,  
I want to integrate official Zalo OpenAPI v3 webhooks and ZNS templates,  
so that I can send instant template messages and log two-way chat conversations directly in Nowing.

## Acceptance Criteria

- **Given** an incoming webhook POST from Zalo Official Account server, **When** validated against the workspace app secret using HMAC-SHA256 with timestamp delta <= 300s, **Then** the event is enqueued into `zalo_inbox_events` and acknowledged with `HTTP 200 OK` in < 100ms.
- **Given** a verified lead with an unlocked Vietnamese mobile number within the valid sending window (08:00–21:30), **When** a user clicks `⚡ Send ZNS`, **Then** Nowing opens a split-pane modal, dispatches via Zalo OpenAPI v3, and records the delivery receipt in `outbound_messages`.
- **Given** a prospect responding to an outbound Zalo message, **When** Zalo OA fires the `user_send_text` event within the 48h active conversation window, **Then** the lead record status updates to `responded` and an in-app notification alerts the workspace owner.

## Dev Notes

- Compliance: Nghị định 91/2020/NĐ-CP (anti-spam), DNC blacklist, sending window 08:00–21:30.
- Webhook: `app/gateway/zalo/webhook.py` with `hmac.compare_digest`
- ZNS templates: `zalo_outbound_service.py`

## Verification

- Module: `app/gateway/zalo/webhook.py`
- HMAC tests, ZNS delivery receipt tests
