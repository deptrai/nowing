# Epic 21 UX Wireframes / Figma Prompt (P0/P1)

**Date:** 2026-08-11
**Author:** Sally (UX Designer)
**Source:** `ux-research-origami-final-2026-08-11.md`, `ux-contract-epic21-addendum-2026-08-11.md`
**Purpose:** ASCII wireframes + Figma-ready prompt for the highest-priority Epic 21 screens.

---

## 1. Inbox Empty State with Email CTA + Lead-Source Picker (N4 — P0)

### ASCII wireframe

```
+----------------------------------------------------------+
|  Inbox                                                   |
+----------------------------------------------------------+
|                                                          |
|              [ illustration: empty inbox ]               |
|                                                          |
|        Start your first outreach campaign                |
|     Build a lead list, then connect a sequence.          |
|                                                          |
|             +-------------------------+                  |
|             |    Start a campaign     |                  |
|             +-------------------------+                  |
|                                                          |
|   Choose a lead source:                                  |
|   [ All scrapers              ▾ ]                        |
|                                                          |
+----------------------------------------------------------+
```

### Figma prompt

Create a centered empty-state card inside the `/sequences/inbox` page.
- **Heading:** 24px semibold, `Start your first outreach campaign`.
- **Subtext:** 16px regular, `Build a lead list from any scraper, then connect an email sequence.`.
- **Primary CTA:** 40px tall, filled button, label `Start a campaign`.
- **Lead-source picker:** single-select dropdown, default `All scrapers`. Lists all connected scraper/connector sources in the workspace. Disabled sources show a lock/tooltip state.
- **Channel row (outbound):** only **Email** is shown. LinkedIn and Zalo are hidden/disabled in MVP.
- **Spacing:** 24px between elements, 64px top padding.
- **Illustration:** line-art mailbox or paper plane, neutral color.

---

## 2. Workspace Mode Switch (N2 — P1)

### ASCII wireframe

```
+----------------------------------------------------------+
|  [Logo]   [Outbound] [Research] [Content]    [Search]  [User] |
|           selected                                      |
+----------------------------------------------------------+
|  Sidebar                                                 |
|  --------------------                                    |
|  Inbox                                                   |
|  Campaigns                                               |
|  Senders                                                 |
|  Tables                                                  |
|  Leads                                                   |
|  Settings                                                |
+----------------------------------------------------------+
```

### Figma prompt

Add a pill/tabs component at the top of the sidebar.
- **Tabs:** `Outbound`, `Research`, `Content`.
- **Selected tab:** filled pill with primary color, white text.
- **Unselected tab:** ghost pill, subtle border.
- **Nav list below:** updates instantly when tab changes (no page reload).
- **Default:** Research for general users, Outbound for `sales` role.
- **Out of scope:** Content tab can be hidden behind a feature gate.

---

## 3. Sidebar Onboarding Checklist (N1 — P1)

### ASCII wireframe

```
+----------------------------------------------------------+
|  Sidebar                                                 |
|  --------------------                                    |
|  +-------------------------------+                       |
|  | Lead-gen setup: 2/5 done    x |                       |
|  +-------------------------------+                       |
|  ✅ Define your ICP                                        |
|  ✅ Run your first search                                  |
|  ○ Enrich a lead                                          |
|  ○ Connect a campaign                                     |
|  ○ Send your first message                                |
|  +-------------------------------+                       |
|  ... nav items ...                                       |
+----------------------------------------------------------+
```

### Figma prompt

Insert a collapsible checklist card inside the sidebar.
- **Header row:** `Lead-gen setup: X/5 done` + close `×` icon.
- **Steps:** 5 rows with a circular done/check icon on the left and a chevron on the right for the next step.
- **Done step:** green checkmark, muted text.
- **Next step:** primary color circle + bold text.
- **Future step:** empty circle, default text.
- **State:** hidden when all 5 steps complete or user dismisses.

---

## 4. Lead Table — Projected Cost + Campaign Chip (N6 + N8 — P1)

### ASCII wireframe

```
+--------------------------------------------------------------------------------+
|  128 leads    Projected cost: 320 credits ($4.61) for 128 leads   [Enrich 5]  |
|                                                                                |
|  Filters: [Vietnam ×] [SaaS ×]              [+ Add filter]                     |
|                                                                                |
|  ⭐ Fit  Company      Website       Industry  Contact       Campaign            |
|  ───────────────────────────────────────────────────────────────────────────── |
|  ★  92   Acme Co     acme.co       SaaS      ...          Not sending yet      |
|                                                            connect a campaign  |
|  ☆  78   Beta Inc    beta.io       Fintech   ...          Active: Vietnam SDR  |
|  ☆  65   Gamma       g.io          E-comm    ...          Not sending yet      |
|                                                            connect a campaign  |
|                                                                                |
|  Row hover: ⭐  🔍 Enrich (2.5 cr)  📧 Sequence  🗑️ Remove                     |
+--------------------------------------------------------------------------------+
```

### Figma prompt

Update the existing data panel table in `ux-contract-lead-intelligence-panel.md`.
- **Table header:** left shows lead count; right shows `Projected cost: X credits ($Y) for Z leads` and primary `[Enrich X]` button.
- **Campaign column:** status chip per row.
  - `Not sending yet — connect a campaign` (subtle gray/yellow, clickable, opens dropdown).
  - `Active: Sequence Name` (green, clickable, opens sequence detail).
  - `Paused: Sequence Name` (orange).
- **Projected cost:** updates as filters/selection change; show `estimated` with a tooltip if cost cannot be computed.
- **Hover row actions:** keep existing star/enrich/sequence/remove pattern.

---

## 5. Source Tabs (N7 — P2)

### ASCII wireframe

```
+--------------------------------------------------------------------------------+
|  [Leads] [Signals] [Sequences] [Sources]                                       |
|                                                                                |
|  [All 128] [X 34] [Instagram 21] [TikTok 45] [Reddit 12] [Web 28] ...          |
|                                                                                |
|  ⭐ Fit  Company      Source      ...       Campaign                             |
|  ───────────────────────────────────────────────────────────────────────────── |
|  ☆  88   Acme Co     X           ...       Not sending yet — connect           |
|  ☆  74   Beta Inc    Reddit      ...       Active: Vietnam SDR                  |
|                                                                                |
+--------------------------------------------------------------------------------+
```

### Figma prompt

Add a `Sources` top-level tab in the data panel.
- **Sub-tabs:** `All` + one tab for each scraper/connector that has generated leads in the workspace (e.g. `X`, `Instagram`, `TikTok`, `Reddit`, `Google Search`, `Web`).
- **Badges:** lead count per source, small pill.
- **Source column:** added to the table when `Sources` tab is active.
- **Cross-reference:** clicking a lead shows a panel of matching profiles from other sources.

---

## 6. Positive-Reply Notification Settings (N5 — P1)

### ASCII wireframe

```
+----------------------------------------------------------+
|  Settings > Notifications                                |
+----------------------------------------------------------+
|                                                          |
|  Positive reply alerts                                   |
|  ─────────────────                                       |
|  [✅] Email me about positive replies                    |
|  [ ] Telegram positive reply alerts (connect Telegram)   |
|                                                          |
|  Browser notifications for agent responses               |
|  [✅] Enabled                                            |
|                                                          |
+----------------------------------------------------------+
```

### Figma prompt

Add a `Positive reply alerts` section to workspace/user notification settings.
- Two toggle rows: Email, Telegram.
- If a channel is not connected, the toggle is disabled and a `Connect` link sits to the right.
- **Email default:** off (respects anti-spam policy).
- **Zalo disabled** in MVP.

---

## 7. Figma component list (for design system)

| Component | Variants |
|---|---|
| `ModeSwitch` | Outbound / Research / Content, selected/default |
| `OnboardingChecklist` | 5 steps, done/next/future, collapsed |
| `CampaignChip` | Not connected / Active / Paused |
| `ChannelCTA` | Email (LinkedIn / Zalo disabled in MVP) |
| `LeadSourcePicker` | All / any connected scraper or connector source |
| `SourceTab` | All / dynamic sub-tabs per scraper/connector source |
| `ProjectedCost` | exact / estimated / per-lead / bulk |
| `PositiveReplyToggle` | Email / Telegram, connected/disabled |
