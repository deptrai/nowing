---
title: "Origami UI/UX Competitive Research — Final Report (Nowing Epic 21)"
date: 2026-08-11
author: Sally (UX Designer)
source: Chrome MCP live audit of https://origami.chat (tab 282531806)
type: ux-research
status: final
---

# Origami UI/UX Competitive Research — Final Report

## 1. Executive Summary

Origami (`origami.chat`) is a lead-generation workspace that combines a conversational agent with a structured data panel, multi-source lead tables, and built-in outreach sequences. Its UI/UX patterns are a strong reference for **Nowing Epic 21 — Lead Intelligence**, especially for Vietnam-market sales/SDR workflows. This report records the screens, components, and interaction patterns observed during a live Chrome MCP session, then maps them to Nowing's existing UX contracts and identifies the gaps that should be added to the product backlog.

**Bottom line:**
- Most core patterns from Origami are already represented in Nowing's canonical contracts (`ux-contract-lead-intelligence-panel.md`, `ux-contract-fit-score-badge.md`, `ux-contract-usage-dashboard.md`) and in `epic21-lead-intelligence-ux.md`.
- Eight new patterns (N1–N8) are not yet covered and are recommended for validation. The highest-impact, Vietnam-specific items are the **Inbox empty-state channel CTA with Zalo** (N4) and the **per-lead projected cost** (N6).

---

## 2. Research Method

- **Tool:** Chrome MCP (`chrome-mcp`)
- **Browser tab:** `282531806`
- **Base URL:** `https://origami.chat/chat/03eca082-6b38-4ef2-b6a0-520fc9f3cb6e?table=9e8e62b0-ea37-4d96-9f8b-c46ed9fc67fd`
- **Views navigated:** `/tables`, `/sequences/inbox`, `/sequences`, `/sequences/senders`, `/chats`, `/dashboard`, `/settings`, and the initial chat/data-panel view.
- **Evidence captured:** screenshots saved to `_bmad-output/planning-artifacts/evidence/`
- **Nowing documents referenced:**
  - `epics.md:48-54` — Epic 21 FR-63..FR-69 (intent, scoring, enrichment, outreach, Zalo, CRM, outcome pricing)
  - `briefs/brief-Nowing-2026-07-25/brief.md:55-82` — Nowing positioning as lead + knowledge intelligence, Vietnam SDR use-case, Zalo as primary channel
  - `ux-design/epic21-lead-intelligence-ux.md` — full Epic 21 UX design derived from the first Origami audit
  - `ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md` — canonical 2-panel data panel contract
  - `ux-designs/ux-Nowing-2026-07-22/ux-contract-fit-score-badge.md` — fit-score visualization
  - `ux-designs/ux-Nowing-2026-07-22/ux-contract-usage-dashboard.md` — credit/usage dashboard
  - `ux-designs/ux-Nowing-2026-07-22/ux-contract-epic21-addendum-2026-08-11.md` — proposed N1–N8 contracts

---

## 3. Screens Explored

### 3.1 Chat + Data Panel (base view)

- **Layout:** collapsible sidebar left, chat panel center, data table panel right.
- **Lead table:** 9 rows with columns Fit Score, Company, Website, Industry, Description, Location, Customer Type.
- **Inline cost projection:** `Projected price 2.5 credits ($0.036) per lead`.
- **Filter chips:** e.g., `Doanh nghiệp ở Việt Nam`, `Doanh nghiệp thực sự liên quan đến trầm hưng`.
- **Campaign status:** `Not sending yet — connect a campaign`.
- **Suggested next actions:** buttons such as `Find decision maker`, `Filter to strong buying intent`, `Compare X/Instagram/TikTok`.

**Evidence:**
- Data panel close-up: `../evidence/origami-data-panel-2026-08-11.png`
- Chat / suggested actions: `../evidence/origami-chat-panel-2026-08-11.png`
- Table header region: `../evidence/origami-table-header-region-2026-08-11.png`

### 3.2 Tables List (`/tables`)

- Lists every saved lead table with search, sort, and `last updated` metadata.
- Source tags show where the list came from (web, X, Instagram, TikTok, etc.).
- Top of the sidebar exposes `Tables` and `Content` tabs, confirming a **workspace mode switch** between lead-gen and research/deliverables modes.

**Evidence:**
- Full tables page: `../evidence/origami-tables-full-2026-08-11.jpg`

### 3.3 Inbox Empty State (`/sequences/inbox`)

- Empty state heading: `Start your first outreach campaign`.
- Primary CTA: `Start a campaign`.
- Channel options: **Email**, **LinkedIn**.
- This is the natural activation moment for new sales users.

**Evidence:**
- Inbox empty state: `../evidence/origami-inbox-empty-2026-08-11.png`

### 3.4 Settings (`/settings`)

- Profile, avatar, email.
- Preferences observed:
  - Browser notifications for agent responses
  - Show credit balance in navigation
  - Keep sidebar expanded
  - Email me about positive replies

### 3.5 Top-Level Project Modes

- Sidebar has `Tables` / `Content` tabs at the top.
- The default view is the lead-gen/campaign workspace; `Content` appears to switch into research/deliverables mode.

---

## 4. Key UX Patterns from Origami

| Pattern | Description | UX Value |
|---------|-------------|----------|
| Chat-first workspace | Conversation is the primary input; data panel is the output surface. | Low learning curve |
| 2-panel layout (chat + data table) | Leads appear beside the conversation that generated them. | Keeps context intact |
| Table-as-a-list (multi-source) | Each source/topic gets its own table. | Scales with vertical/source expansion |
| Suggested next actions | 3–4 AI-suggested action buttons after a response. | Reduces decision paralysis |
| Empty state with channel CTA | `Start your first outreach campaign` + channel selection. | Drives activation |
| Per-lead cost projection | `X credits ($Y) per lead` shown before enrich/send. | Trust and transparency |
| Campaign connection prompt | `Not sending yet — connect a campaign`. | Clear status and next step |
| Onboarding sidebar checklist | `Next steps: 0 of 5 done`. | Progress toward activation |
| Positive-reply email notification | Setting to email when a lead replies positively. | Re-engagement |

---

## 5. Comparison with Nowing

### 5.1 Already covered in Nowing UX contracts

| Pattern | Nowing reference |
|---------|-----------------|
| 2-panel chat + data layout | `ux-contract-lead-intelligence-panel.md:11-20` |
| Data table with Leads / Signals / Sequences tabs | `ux-contract-lead-intelligence-panel.md:32-37` |
| Fit score badge (0–100, green/yellow/red) | `ux-contract-fit-score-badge.md:10-17` |
| Suggested actions (max 3, cost indicator) | `ux-contract-lead-intelligence-panel.md:66-80` |
| Filter chips | `ux-contract-lead-intelligence-panel.md:84-100` |
| Row actions (star, enrich, sequence, remove) | `ux-contract-lead-intelligence-panel.md:58-62` |
| Campaign/sequence integration | `ux-contract-lead-intelligence-panel.md:104-115` |
| Credit/usage dashboard | `ux-contract-usage-dashboard.md:20-28` |

### 5.2 New patterns not yet in Nowing — recommendations N1–N8

| ID | Pattern | Why it matters | Nowing link / status | Priority |
|---|---|---|---|---|
| **N1** | Onboarding checklist in sidebar (5 steps) | Reduces time-to-first-value for sales users | New; can extend Story 21.1 or add onboarding epic | P1 |
| **N2** | Workspace mode switch (Outbound / Research / Content) | Prevents sales users from drowning in research UI | New; affects Epic 21 + Epic 8 dashboard | P1 |
| **N3** | Tables directory / lead lists library | Manage many lead lists outside a single chat | New; lead-list management story | P2 |
| **N4** | Inbox empty state + channel CTA (Email / LinkedIn / **Zalo**) | Activation; Zalo is the dominant channel in Vietnam (FR-68) | Story 21.4 + 21.6; `ux-contract-epic21-addendum-2026-08-11.md:68-82` | **P0 (VN)** |
| **N5** | Positive-reply notifications (email / Zalo / Telegram) | Re-engage SDRs when leads reply | Extend Story 11.1 (Telegram); `ux-contract-epic21-addendum-2026-08-11.md:85-98` | P1 |
| **N6** | Per-lead projected cost inline | Builds trust before enrichment or send | Story 21.7 / FR-69; `ux-contract-epic21-addendum-2026-08-11.md:101-113` | P1 |
| **N7** | Source-specific table tabs (X / Instagram / TikTok / Web) | Matches multi-source aggregation in Epic 12 and 21 | Story 21.1 / Epic 12 | P2 |
| **N8** | `Connect a campaign` status chip in lead table | Clear sequence status and CTA | Story 21.4; `ux-contract-epic21-addendum-2026-08-11.md:132-145` | P1 |

### 5.3 Differences to preserve in Nowing

- **Multiple chat tabs** — Origami is single-chat; Nowing already supports multi-thread multitasking.
- **Research memory + citations** — Nowing's durable, provenance-aware memory is a core differentiator and not visible in Origami.
- **MCP / API Playground** — power-user surface unique to Nowing.
- **Self-host / open-core model** — different licensing and deployment story.

---

## 6. Recommended Next Steps

1. **P0 — Empty state / channel CTA (N4):** Validate Zalo OA setup with legal/ToS, then update `ux-contract-lead-intelligence-panel.md` §5 with the empty-state flow.
2. **P1 — Workspace mode switch (N2) + Onboarding checklist (N1):** Reduce cognitive load for sales users; create a dedicated `ux-contract-workspace-mode-switch.md` and `ux-contract-onboarding-checklist.md` if PO confirms.
3. **P1 — Positive-reply notifications (N5):** Extend Story 11.1 to include `lead_positive_reply` trigger for email and Zalo.
4. **P2 — Tables directory (N3) + Source-specific tabs (N7):** Add lead-list management and multi-source filtering once the core 2-panel layout ships.

---

## 7. Evidence Inventory

| File | Description | Format | Size |
|---|---|---|---|
| `../evidence/origami-tables-full-2026-08-11.jpg` | Full `/tables` page showing mode switch, table list, search | JPEG | 1967x1109 |
| `../evidence/origami-inbox-empty-2026-08-11.png` | `/sequences/inbox` empty state with `Start a campaign` CTA | PNG | 1360x680 |
| `../evidence/origami-data-panel-2026-08-11.png` | Lead table, filter chips, `Projected price` text, campaign status | PNG | 960x800 |
| `../evidence/origami-chat-panel-2026-08-11.png` | Suggested next actions below agent response | PNG | 620x740 |
| `../evidence/origami-table-header-region-2026-08-11.png` | Close-up of table header and controls | PNG | 1720x200 |

---

## 8. Traceability

- `epics.md:48-54` — Epic 21 FRs
- `briefs/brief-Nowing-2026-07-25/brief.md:55-82` — product positioning
- `ux-design/epic21-lead-intelligence-ux.md` — first-pass Epic 21 design from Origami
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md` — canonical data-panel contract
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-epic21-addendum-2026-08-11.md` — N1–N8 proposed contracts
- `ux-research-origami-refresh-2026-08-11.md` — draft research note that fed this final report

---

**Status:** Final — ready for PO review and merge into Epic 21 UX contracts.
