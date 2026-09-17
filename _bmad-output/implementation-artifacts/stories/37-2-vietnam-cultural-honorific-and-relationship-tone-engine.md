---
story_key: 37-2-vietnam-cultural-honorific-and-relationship-tone-engine
status: ready-for-dev
epic: 37
priority: P0
target_codebase: nowing_backend
architectural_invariants: [AD-116]
---

# Story 37.2: Vietnam Cultural Honorific & Relationship Tone Engine

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P0  
**Target Codebase:** `nowing_backend`  
**Architectural Alignment:** Extends `app/services/sequencer/services/executor.py`, `app/services/sequencer/dispatch.py`, and `app/services/sequencer/inbound.py`.

## Story

As a B2B Sales Representative,  
I want the sequencer and auto-reply agent to dynamically select native Vietnamese honorific pronouns (Anh/Chị/Em/Quý đối tác) based on prospect seniority and estimated age,  
So that cold outreach and automated replies sound respectful, professional, and indistinguishable from an experienced local sales rep.

## Acceptance Criteria

- **AC-1 (Deterministic Honorific Resolution):** `VietnamHonorificResolver` infers age differential (from birth year in CCCD/MST or graduation year) and title seniority per AD-116 (0ms latency, $0 token cost), mapping to addressing pairs (`Anh - Em`, `Chị - Em`, `Quý đối tác - Chúng tôi`).
- **AC-2 (Prompt Context Injection):** Injects resolved honorific variables into LLM generation context under the `{salutation}` token for sequence steps and two-way auto-replies.
- **AC-3 (Anti-Translation Quality Gate & Foreign Fallback):** Rejects robotic direct translations (such as "Bạn/Tôi"); defaults to standard English business honorifics (`Dear Mr./Ms. [Lastname]`) for foreign prospects/international domains, and neutral professional phrasing (`Quý anh/chị` or `Quý đối tác`) when demographics are ambiguous.
- **AC-4 (Decree 91 Curfew Enforcement):** Message dispatch strictly halts between 21:00 and 08:00 ICT per Decree 91/2020/NĐ-CP.
