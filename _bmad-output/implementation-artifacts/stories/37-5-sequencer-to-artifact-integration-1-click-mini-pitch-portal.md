---
story_key: 37-5-sequencer-to-artifact-integration-1-click-mini-pitch-portal
status: ready-for-dev
epic: 37
priority: P1
target_codebase: nowing_backend, nowing_web
architectural_invariants: [AD-119]
---

# Story 37.5: Sequencer-to-Artifact Integration (1-Click Mini-Pitch Portal Generator)

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P1  
**Target Codebase:** `nowing_backend`, `nowing_web`  
**Architectural Alignment:** Extends Web Builder (`app/services/web_builder/`, Epic 27.1), Next.js SSR (`nowing_web/`), and Visual Cadence Builder.

## Story

As an Outbound Campaign Manager,  
I want the sequencer to automatically trigger the Web Builder to generate personalized 1-click interactive mini-pitch portals for target prospects,  
So that our outreach emails and messages feature a tailored, branded interactive value proposition.

## Acceptance Criteria

- **AC-1 (Single Multi-Tenant SSR Invariant - AD-119):** Portals are served via a unified Next.js SSR route (`pitch.nowing.ai/[workspace_slug]/[lead_id]`) reading metadata dynamically from Postgres/Redis with Cloudflare edge caching (TTFB $< 100$ms). Deploying individual Dokploy Docker containers per lead is strictly prohibited.
- **AC-2 (Personalized Branded Presentation):** Combines prospect logo, company name, 30-second executive summary, interactive ROI calculator, and inline calendar booking CTA.
- **AC-3 (Stored XSS Sanitization):** All dynamic prospect fields (company name, notes, title) are strictly sanitized against Stored XSS via DOMPurify/escaping.
- **AC-4 (Decree 13 Opt-Out Compliance):** Portal footer must include a verified "Yêu cầu xóa thông tin của tôi / Opt-out" link compliant with Decree 13/2023/NĐ-CP.
- **AC-5 (Template Injection):** Injects generated portal URL into `{{pitch_portal_url}}` variable for cadence copy with idempotent caching to avoid duplicate builds.
