# Manus vs Nowing Feature Audit

**Date:** 2026-08-20  
**Source:** Public Manus.im marketing + feature pages (2026) cross-checked against Nowing `prd-Nowing-2026-07-22/prd.md`, `epics.md`, `ARCHITECTURE-SPINE.md`, and `sprint-status.yaml`.  
**Scope:** Map Manus public feature set to Nowing FR/Epic/Story/AD. Identify gaps and next steps before elevating Epic 27 to in-scope.

## Assumptions

- Nowing canonical architecture spine (2026-08-20, approved) defines Nowing as an **Autonomous Workstation** with 25 Manus.im-like subsystems (`AD-111`–`AD-115` explicitly, the rest implicit across Epic 21–26).
- This audit uses the **publicly advertised Manus feature set** as the benchmark, not the 25 internal subsystems.
- Status legend:
  - **✅ Covered** — implemented or has a committed done story in `sprint-status.yaml`.
  - **⚠️ Partial** — some pieces exist but not full parity.
  - **📋 Backlog** — explicitly planned in `epics.md` but status is `backlog`/`ready-for-dev`.
  - **❌ Gap** — not in PRD/epics or not planned.

## Feature Matrix

| # | Manus Feature | Nowing Equivalent | Status | Gap / Next Step |
|---|---|---|---|---|
| 1 | **Wide Research** (parallel multi-agent research) | FR-24 Deep-Open Web Research via ChainLens; Epic 9 (`9.1b` contract guard, `9.2` cost metering, `9.3` latency budget); `chainlens.research` capability | ✅ Covered | Scale/parallelism is ChainLens-side; Nowing side needs measured baseline and State A/B gating (9.3 done, awaiting p95 data). |
| 2 | **Browser Operator** (Chrome extension, CDP, logged-in session automation, human takeover) | AD-111; Story `24.8` (Browser Operator CDP Capability + Human Live Takeover); Epic 24 | ⚠️ Partial | `24-8` is `review`. Core CDP bridge, SSE auth, challenge detection, `browser_operator.execute` capability, and `web_crawler` subagent prompt are implemented. Full mission pause/resume lifecycle, 15-minute TTL, dashboard Human Live Takeover popover, and PII redaction remain open. |
| 3 | **App/Website Builder** (full-stack from prompt, Next.js/React, DB, auth, Stripe, deploy) | AD-113; Story `27.1`; Epic 27; **FR-93** | ✅ Ready-for-dev | `27-1` upgraded to `ready-for-dev`; story file created; PRD §4.10 updated. |
| 4 | **AI Design / Design View / Mark Tool** (visual canvas, AST-mutate generated JSX) | AD-114; part of Story `27.1`; **FR-93** | ✅ Ready-for-dev | Same as 27.1. Iframe preview + Bounding Box Selector + JSX AST mutator. |
| 5 | **Slides / Nano Banana Pro** (PPTX/Marp from prompt) | Story `27.2` (Manus Slides + Speaker Diarization); uses `video_presentations_routes.py`, `reports_routes.py`; **FR-94** | ✅ Ready-for-dev | `27-2` upgraded to `ready-for-dev`; story file created; PRD §4.10 updated. |
| 6 | **AI Image Generator** | FR-23; Epic 5 (Deliverables) — report/podcast/video/image | ✅ Covered | Epic 5 done. Image generation exists. |
| 7 | **AI Music Generator** | None | ❌ Gap | Not in PRD or epics. Add if Manus-like creative suite is a priority. |
| 8 | **Mail Manus** (inbound email task delegation) | AD-115; Story `6.10` (Inbound Mail Gateway `task@nowing.ai`); Epic 6 | 📋 Backlog | `6-10` is `backlog`. Need SendGrid/Mailgun webhook adapter, delta analysis. |
| 9 | **Slack Integration** | FR-7 OAuth connector; FR-18 write-back Slack action; `gateway_webhook_routes.py` Slack/Telegram/Discord/WhatsApp | ✅/⚠️ Partial | Connector + write-back done. Missing: "assign task from Slack message" as a first-class trigger; could reuse gateway framework. |
| 10 | **API Access** (PAT/API key, programmatic workflows) | FR-2 API/PAT; FR-56 Public Agent-Chat API; FR-29 MCP server; Epic 18 | ✅/⚠️ Partial | PAT/API key done; public agent-chat API + `AgentConfig` registry in progress (`E18` in-progress). |
| 11 | **Team Plan + SSO** | FR-4 Invites/Memberships; FR-10 RBAC; FR-41 Admin UI; workspace limits | ⚠️ Partial | Team plan not explicit. SSO (SAML/SCIM) not in PRD. Add if targeting enterprise. |
| 12 | **Desktop App** | FR-26 Desktop Client (Electron); Epic 7 | ⚠️ Partial | FR-26 in PRD and marked done in inventory, but no story file in `epics.md` and no `7-x` entry in `sprint-status.yaml`. Verify code or add story. |
| 13 | **Mobile App** | None | ❌ Gap | Not in PRD or epics. Native iOS/Android not planned. |
| 14 | **Voice-to-Text / Speaker Diarization** | Story `27.2` (Speaker Diarization); `services/stt_service.py` (faster-whisper) | 📋 Backlog | `27-2` backlog. Add `pyannote.audio`/`whisperx` diarization. |
| 15 | **In-Sandbox Code / Python Data Studio** | AD-112; Story `26.9` (Wide Research Client & Pro Excel Formatter via Daytona sandbox) | 📋 Backlog | `26-9` backlog. Sandbox exists; need `output=wide_research` client and Pro Excel formatter. |
| 16 | **SEO optimization for built sites** | None explicit | ❌ Gap | Not in Story 27.1 ACs. Add if web builder ships publicly. |
| 17 | **Analytics for built sites** | Story `8.10` (PostHog analytics) | ✅ Covered | PostHog integration done; can be reused for web builder analytics. |
| 18 | **Real-time notifications** | Notifications table + SSE + Telegram/Slack gateway; `8.11` pricing/alerts | ✅/⚠️ Partial | Infra exists. Need specific web builder / slide pipeline notifications. |
| 19 | **Lead collection & management** | Epic 21–26 (lead intelligence, CRM sync, outreach) | ✅ Covered | Extensive lead pipeline done/in-progress. |
| 20 | **Domain connect / custom CNAME** | Story `27.1` (Custom CNAME manager) | 📋 Backlog | Part of 27.1 backlog. |
| 21 | **Export code** | Story `27.1` (Next.js project in `/workspace/web-app`) | 📋 Backlog | Code is already in workspace; formal export UX is part of 27.1. |
| 22 | **Visual controls (no-code layout/color/typo)** | Story `27.1` (Mark Tool) | 📋 Backlog | AST mutator + bounding box selector. |
| 23 | **Memory / long-term research memory** | FR-32; Epic 3 (Memory KB, recall, provenance) | ✅ Covered | Core differentiator, done. |
| 24 | **Scraper connectors (15+)** | FR-6, FR-43–47, FR-70–79; Epic 2, 12, 22 | ✅ Covered | 15+ research-producing capabilities registered. |
| 25 | **Automation / scheduled tasks** | FR-18/19/20/35; Epic 6 | ✅ Covered | Automation engine + scheduled tasks exists. |
| 26 | **Lead intelligence / CRM / outreach** | Epic 21–26 | ✅/⚠️ Partial | Large lead ecosystem; some stories still in progress/backlog (E18, E24, E26). |

## Summary

- **✅ Covered:** 14/26 features (Wide Research, Image, Slack partial, API partial, Analytics, Lead, Memory, Scrapers, Automation, etc.)
- **📋 Backlog / planned:** 4/26 (Mail, Sandbox Excel); **✅ Ready-for-dev:** 3/26 (Web Builder, Slides, Design View); **⚠️ Partial:** 1/26 (Browser Operator)
- **❌ Gap / not planned:** 4/26 (AI Music, Mobile App, SEO for built sites, Team SSO)
- **⚠️ Partial / needs verification:** 2/26 (Desktop app status unclear, Team Plan + SSO not explicit)

## Top 5 gaps to close for Manus parity

1. **Story 24.8 (Browser Operator Chrome Extension)** — enables agent to act inside user's logged-in sessions; `review`. Core CDP capability is implemented; still needs full mission pause/resume lifecycle, 15-minute TTL, dashboard popover, and PII redaction.
2. **Story 6.10 (Inbound Mail Gateway)** — `task@nowing.ai` task delegation; `backlog`.
3. **Story 26.9 (Python Data Science Sandbox)** — in-sandbox code execution for deliverables; `backlog`.
4. **Story 6.10 (Inbound Mail Gateway)** — `task@nowing.ai` task delegation; `backlog`.
5. **AI Music Generator / Mobile App / SEO** — decide if these are in scope or explicitly out-of-scope.

## Recommended next actions

1. **Promote Epic 27 from out-of-PRD backlog to in-PRD / product vision.** Add FR-27.1 and FR-27.2 to `prd-Nowing-2026-07-22/prd.md` via PRD Amendment.
2. **Update `sprint-status.yaml`:** set `epic-27`, `27-1`, `27-2` to `ready-for-dev` (or `in-progress` if starting immediately).
3. **Create story files** for `27-1` and `27-2` so `bmad-sprint-planning` can pick them up.
4. **Clarify Desktop Client (FR-26)** — verify code status and add a `7-x` story if needed.
5. **Decide on Music / Mobile / SEO / SSO** — add to product plan or to Non-Goals.

## Artifacts updated

- This audit: `_bmad-output/planning-artifacts/manus-nowing-feature-audit-2026-08-20.md`
