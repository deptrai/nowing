---
story_key: 37-1-proactive-intent-signal-radar-background-ingestion-tele
status: ready-for-dev
epic: 37
priority: P1
target_codebase: nowing_backend
architectural_invariants: [AD-115]
---

# Story 37.1: Proactive Intent Signal Radar (Background Ingestion & Telegram Stream Matcher)

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`  
**Architectural Alignment:** Extends `SignalDetectionService` (`app/lead_intelligence/signals/service.py`), `LeadAssignmentService` (`app/services/lead_assignment_service.py`), and Telegram stream pipeline (`stream:telegram:raw_events`).

## Story

As a Growth / RevOps Engineer,  
I want a background daemon and stream listener that proactively scans hiring spikes, newly registered tax codes, and Telegram buy-requests,  
So that buying-intent leads are captured into the workspace matrix without requiring manual query triggers.

## Acceptance Criteria

- **AC-1 (Periodic Signal Scanner):** Celery Beat task `scan_high_intent_companies_periodic` executes every 6 hours, scanning hiring surges ($\ge 3$ new job postings in 7 days across TopCV/VietnamWorks) and newly incorporated tax codes from `masothue.com`/`dangkykinhdoanh.gov.vn`, persisting `SignalEvent` records with `intent_score >= 0.75`.
- **AC-2 (Aho-Corasick Telegram Stream Intent Matcher):** A consumer worker listening to Redis stream `stream:telegram:raw_events` runs an in-memory compiled Aho-Corasick keyword trie ($O(n)$) per AD-115 to pre-filter messages matching purchase intent patterns ("cần tìm nhà cung cấp", "báo giá", "tìm agency", "thuê ngoài"), extracts contact info, and creates an enriched `Lead` assigned round-robin via `LeadAssignmentService`.
- **AC-3 (Zero-Credit Penalty for Missing Contact):** If a Telegram intent message contains NO extractable phone or email, the system creates an Unqualified Signal Lead with `status='pending_enrichment'` and does NOT deduct workspace credits until contact data is resolved.
- **AC-4 (Budget Guardrails & Rate Limits):** Background scanning enforces AD-115 budget caps: maximum 100 scans per workspace per day, pausing automatically if credit balance falls below 50 credits.
