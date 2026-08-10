# Epic 21 — Lead Intelligence UX Design (Nowing ← Origami Analysis)

**Date:** 2026-08-10
**Author:** Sally (UX Designer)
**Status:** Merged into canonical UX contracts (`ux-contract-lead-intelligence-panel.md` and `ux-contract-fit-score-badge.md`) — Zalo OA setup and outcome-pricing display screens require validation before final design.
**Source:** Origami UI analysis via Chrome MCP + Nowing current state

---

## 1. Origami UI/UX Analysis

### 1.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌──────────────────────────────────────────────┐   │
│ │ Sidebar  │ │ Main Area                                     │   │
│ │          │ │ ┌──────────────────┐ ┌────────────────────┐ │   │
│ │ Logo     │ │ │ Chat Panel       │ │ Data Table Panel   │ │   │
│ │ Switch   │ │ │                  │ │                    │ │   │
│ │ Project  │ │ │ Conversation     │ │ [Tab1][Tab2][Tab3] │ │   │
│ │          │ │ │ Log              │ │                    │ │   │
│ │ Dashboard│ │ │                  │ │ Fit│Company│Web   │ │   │
│ │ Sequences│ │ │ Suggested        │ │ 100│Natural │nat...│ │   │
│ │ Tables   │ │ │ Actions:         │ │ 100│Truc   │tra...│ │   │
│ │          │ │ │ [Draft sequence] │ │ 100│ETOP   │eto...│ │   │
│ │ Your     │ │ │ [Show labels]    │ │                    │ │   │
│ │ Chats    │ │ │ [Find overlaps]  │ │ [Find similar]     │ │   │
│ │          │ │ │                  │ │ [Send & export]    │ │   │
│ │ Chat 1   │ │ │ Input:           │ │                    │ │   │
│ │ Chat 2   │ │ │ [Attach][Connect]│ │ Filters: [VN][Agar]│ │   │
│ │ Chat 3   │ │ │ [Model][Voice][S]│ │                    │ │   │
│ │          │ │ └──────────────────┘ └────────────────────┘ │   │
│ └──────────┘ └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Key UI Patterns (Origami)

| Pattern | Description | UX Value |
|---------|-------------|----------|
| **Chat-first** | Conversational UI is primary interaction | Low learning curve |
| **2-panel layout** | Chat left + Data table right | Context without switching |
| **Suggested Actions** | AI-powered next step buttons | Guided workflow |
| **Multi-table tabs** | Switch between lead lists | Organization |
| **Inline filters** | Filter chips for refining | Quick data manipulation |
| **Fit Score** | Lead quality indicator (0-100) | Prioritization |
| **Quick actions** | Star, Remove per row | Fast curation |
| **Campaigns** | Sequences integration | Outreach readiness |
| **Credits display** | Cost per lead transparent | Trust |

### 1.3 Origami Component Hierarchy

```
ChatPage
├── LeftSidebar
│   ├── Logo + ProjectSwitcher
│   ├── Navigation (Dashboard, Sequences, Tables)
│   ├── ChatList (Your Chats)
│   ├── Progress (Get started: 0/5)
│   └── Footer (Slack, Settings, UserAvatar)
├── MainContent
│   ├── ChatPanel (left side)
│   │   ├── ChatHeader (title, actions)
│   │   ├── ConversationLog (messages)
│   │   ├── SuggestedActions (AI buttons)
│   │   └── InputBar (attach, connectors, model, voice, send)
│   └── DataTablePanel (right side)
│       ├── TableTabs (multiple lead lists)
│       ├── TableHeader (campaigns, filters, actions)
│       ├── DataTable (Fit, Company, Website, Industry)
│       └── RowActions (Star, Remove)
└── IntercomMessenger
```

---

## 2. Nowing Current UI Analysis

### 2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌──────────────────────────────────────────────┐   │
│ │ Sidebar  │ │ Main Area (Full-width Chat)                  │   │
│ │          │ │                                               │   │
│ │ My       │ │ [Tab1][Tab2][Tab3][New Chat]                 │   │
│ │ Workspace│ │                                               │   │
│ │          │ │ ┌──────────────────────────────────────────┐ │   │
│ │ New chat │ │ │ Onboarding Banner                        │ │   │
│ │ Automati │ │ │ [Feature1][Feature2][Feature3]           │ │   │
│ │ Artifacts│ │ └──────────────────────────────────────────┘ │   │
│ │ Playgrnd │ │                                               │   │
│ │          │ │ ┌──────────────────────────────────────────┐ │   │
│ │ Recents  │ │ │ Chat Log                                 │ │   │
│ │ Chat 1   │ │ │                                          │ │   │
│ │ Chat 2   │ │ │                                          │ │   │
│ │ Chat 3   │ │ └──────────────────────────────────────────┘ │   │
│ │          │ │                                               │   │
│ │ Document │ │ Input:                                       │   │
│ │ Folder   │ │ [Upload][Platforms][Model][Image][Send]     │   │
│ │ File     │ │                                               │   │
│ │          │ │                                               │   │
│ │ Usage    │ │                                               │   │
│ │ Credits  │ │                                               │   │
│ │ $5.03    │ │                                               │   │
│ └──────────┘ └──────────────────────────────────────────────┘   │
│                     ┌──────────────┐                             │
│                     │ API Playground│ (Right Sidebar)            │
│                     │ (collapsible)│                             │
│                     └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Key UI Patterns (Nowing)

| Pattern | Description | UX Value |
|---------|-------------|----------|
| **Chat-first** | Conversational UI is primary | Low learning curve |
| **Full-width chat** | No data panel alongside | Focus on conversation |
| **Chat tabs** | Multiple chats open | Multitasking |
| **Left sidebar** | Workspace navigation | Organization |
| **Documents** | File management | Knowledge base |
| **API Playground** | Right sidebar scraper tools | Power user feature |
| **Platform icons** | Quick access to scrapers | Efficiency |
| **Onboarding banner** | Feature highlights | Discovery |
| **Credits** | Balance + Earn/Buy | Transparency |

### 2.3 Nowing Component Hierarchy

```
ChatPage
├── LeftSidebar
│   ├── WorkspaceSwitcher
│   ├── Navigation (New chat, Automations, Artifacts, Playground)
│   ├── Recents (chat history)
│   ├── Documents (file tree)
│   └── Footer (Usage, Credits, Earn/Buy)
├── MainContent
│   ├── ChatTabs (multiple chats)
│   ├── OnboardingBanner (feature highlights)
│   ├── ChatLog (messages)
│   └── InputBar (upload, platforms, model, image, send)
└── RightSidebar (API Playground)
    ├── Navigation (Overview, Runs, API Keys)
    └── ScraperTools (Reddit, Batdongsan, YouTube, etc.)
```

---

## 3. Comparative Analysis

### 3.1 Feature Comparison Matrix

| Feature | Origami | Nowing | Gap | Priority |
|---------|---------|--------|-----|----------|
| **Data table panel** | ✅ Inline with leads | ❌ Not present | HIGH | P0 |
| **Suggested actions** | ✅ AI-powered buttons | ❌ Not present | HIGH | P0 |
| **Lead scoring** | ✅ Fit Score column | ❌ Not present | HIGH | P0 |
| **Multi-table tabs** | ✅ Switch lead lists | ❌ Not present | MEDIUM | P1 |
| **Inline filters** | ✅ Filter chips | ❌ Not present | MEDIUM | P1 |
| **Campaigns/Sequences** | ✅ Built-in | ❌ Not present | HIGH | P0 |
| **Quick actions** | ✅ Star, Remove | ❌ Not present | MEDIUM | P1 |
| **Chat tabs** | ❌ Single chat | ✅ Multiple | — | — |
| **API Playground** | ❌ Not present | ✅ Right sidebar | — | — |
| **Documents** | ❌ Not present | ✅ File management | — | — |
| **Connectors** | ✅ Input toolbar | ✅ Platform icons | — | — |
| **Credits display** | ✅ Per-lead cost | ✅ Balance only | LOW | P2 |

### 3.2 UX Strengths to Adopt from Origami

1. **2-Panel Layout (Chat + Data)**
   - Origami: Chat left, data table right
   - Benefit: See results without leaving conversation
   - Nowing gap: Results appear only in chat, no structured view

2. **Suggested Next Actions**
   - Origami: 3-4 AI-powered action buttons after each response
   - Benefit: Guided workflow, reduces decision paralysis
   - Nowing gap: User must know what to type next

3. **Lead Scoring (Fit Score)**
   - Origami: Numeric score (0-100) per lead
   - Benefit: Quick prioritization
   - Nowing gap: No quality indicator for results

4. **Multi-Table Tabs**
   - Origami: Switch between different lead lists
   - Benefit: Organization, comparison
   - Nowing gap: Single conversation context

5. **Inline Filters**
   - Origami: Filter chips (e.g., "Doanh nghiệp ở Việt Nam")
   - Benefit: Quick data refinement
   - Nowing gap: Must re-prompt to filter

6. **Campaigns Integration**
   - Origami: "Connect a campaign" for sequences
   - Benefit: Seamless outreach
   - Nowing gap: No outbound capability

### 3.3 Nowing Strengths to Keep

1. **Chat Tabs** — Multiple chats open simultaneously
2. **API Playground** — Power user scraper tools
3. **Documents** — File management + knowledge base
4. **Platform Icons** — Quick scraper access in input bar
5. **Workspace Sidebar** — Clear navigation hierarchy
6. **Credits System** — Earn/Buy transparency

---

## 4. Recommended UX Updates for Nowing Epic 21

### 4.1 Layout Update: 2-Panel Mode

**Current:** Full-width chat
**Proposed:** Collapsible 2-panel mode (chat + data table)

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌─────────────────────┬────────────────────────┐   │
│ │ Sidebar  │ │ Chat Panel          │ Data Panel (new)       │   │
│ │          │ │                     │                        │   │
│ │ Workspace│ │ Conversation Log    │ [Leads][Signals][Seq]  │   │
│ │ Nav      │ │                     │                        │   │
│ │          │ │ Suggested Actions:  │ Fit│Company│Score│Act  │   │
│ │ Recents  │ │ [Enrich leads]      │ 100│Acme  │100  │[★]  │   │
│ │          │ │ [Find similar]      │ 85 │Beta  │85   │[★]  │   │
│ │ Documents│ │ [Start sequence]    │ 70 │Gamma │70   │[★]  │   │
│ │          │ │                     │                        │   │
│ │          │ │ Input:              │ Filters: [VN][Agar]    │   │
│ │          │ │ [Upload][Platforms] │ [Find similar][Export] │   │
│ │          │ │ [Model][Send]       │                        │   │
│ └──────────┘ └─────────────────────┴────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Data panel is collapsible (toggle button in chat header)
- Default: visible when leads are generated
- Can be hidden for focus mode
- State persisted per workspace

### 4.2 New Components

#### 4.2.1 Data Table Panel

**Purpose:** Display leads, signals, and sequence enrollments in structured format

**Components:**
```
DataTablePanel
├── PanelHeader
│   ├── TabBar ([Leads][Signals][Sequences])
│   ├── CollapseToggle
│   └── CreditsDisplay
├── FilterBar
│   ├── FilterChips (removable)
│   ├── AddFilterButton
│   └── SortDropdown
├── DataTable
│   ├── ColumnHeaders (sortable)
│   │   ├── FitScore (with color coding)
│   │   ├── Company/Name
│   │   ├── Website
│   │   ├── Industry
│   │   ├── Signals
│   │   └── Actions
│   └── Row
│       ├── StarButton
│       ├── EnrichButton
│       ├── SequenceButton
│       └── RemoveButton
└── TableFooter
    ├── Pagination
    ├── ExportButton
    └── FindSimilarButton
```

**Fit Score Color Coding:**
- 🟢 80-100: High fit (green)
- 🟡 50-79: Medium fit (yellow)
- 🔴 0-49: Low fit (red)

#### 4.2.2 Suggested Actions

**Purpose:** AI-powered next step buttons after each agent response

**Components:**
```
SuggestedActions
├── ActionButton (primary)
│   ├── Icon
│   ├── Label (e.g., "Enrich 5 leads")
│   └── CostIndicator (e.g., "2.5 credits")
├── ActionButton (secondary)
│   ├── Icon
│   └── Label (e.g., "Find similar companies")
└── ActionButton (tertiary)
    ├── Icon
    └── Label (e.g., "Start outreach sequence")
```

**Behavior:**
- Appear after agent responses that generate leads/data
- Max 3-4 actions visible
- Actions context-aware (enrichment, sequencing, filtering)
- Cost displayed for transparency

#### 4.2.3 Lead Scoring Badge

**Purpose:** Visual indicator of lead quality

**Components:**
```
FitScoreBadge
├── Score (0-100)
├── ColorCode (green/yellow/red)
└── Tooltip (score breakdown)
```

**Score Breakdown Tooltip:**
```
Fit Score: 85/100
├── Company Size: 20/20
├── Industry Match: 18/20
├── Location: 15/20
├── Intent Signals: 17/20
└── Tech Stack: 15/20
```

#### 4.2.4 Filter Chips

**Purpose:** Quick data refinement

**Components:**
```
FilterBar
├── FilterChip (active)
│   ├── Label (e.g., "Vietnam")
│   └── RemoveButton (×)
├── FilterChip (active)
│   ├── Label (e.g., "Agarwood")
│   └── RemoveButton (×)
├── AddFilterButton (+)
│   └── Dropdown (Location, Industry, Size, etc.)
└── ClearAllButton
```

#### 4.2.5 Campaigns/Sequences Integration

**Purpose:** Connect leads to outreach sequences

**Components:**
```
CampaignSection
├── StatusIndicator
│   ├── "Not sending yet — connect a campaign"
│   └── "Active: Sequence Name"
├── ConnectCampaignButton
│   └── Dropdown (existing sequences)
├── SequenceProgress
│   ├── Step 1: ✅ Sent
│   ├── Step 2: ⏳ Waiting
│   └── Step 3: ○ Pending
└── ViewSequenceButton
```

---

## 5. UX Specifications

### 5.1 Data Table Specifications

**Table Columns (Leads Tab):**

| Column | Width | Sortable | Filterable | Notes |
|--------|-------|----------|------------|-------|
| ⭐ | 40px | No | No | Star/favorite |
| Fit Score | 80px | Yes | Yes | Color-coded badge |
| Company | 200px | Yes | Yes | With favicon |
| Website | 150px | No | No | Link + domain |
| Industry | 120px | Yes | Yes | |
| Signals | 100px | Yes | Yes | Signal count |
| Contact | 150px | No | No | Email/phone |
| Actions | 120px | No | No | Enrich, Sequence, Remove |

**Table Columns (Signals Tab):**

| Column | Width | Sortable | Notes |
|--------|-------|----------|-------|
| Company | 200px | Yes | |
| Signal Type | 120px | Yes | Funding, Hiring, etc. |
| Source | 150px | No | URL |
| Confidence | 100px | Yes | 0-100 |
| Detected | 100px | Yes | Date |
| Actions | 120px | No | View, Create Lead |

**Table Columns (Sequences Tab):**

| Column | Width | Sortable | Notes |
|--------|-------|----------|-------|
| Sequence | 200px | Yes | |
| Leads | 80px | Yes | Count |
| Status | 100px | Yes | Active/Paused |
| Sent | 80px | Yes | Count |
| Replies | 80px | Yes | Count |
| Meetings | 80px | Yes | Count |
| Actions | 120px | No | View, Pause, Stop |

### 5.2 Interaction Specifications

**Data Panel Toggle:**
- Button in chat header (right side)
- Icon: table icon (📊) when closed, X icon when open
- Keyboard shortcut: `Cmd/Ctrl + D`
- State persisted in localStorage

**Suggested Actions:**
- Appear 500ms after agent response
- Fade-in animation (200ms)
- Hover: slight scale (1.02) + shadow
- Click: execute action + loading state
- Cost indicator: small text below label

**Filter Chips:**
- Add: click "+" → dropdown → select filter → chip appears
- Remove: click "×" on chip
- Clear all: "Clear" link
- Max 5 visible chips, overflow in dropdown

**Row Actions:**
- Hover row → actions appear (star, enrich, sequence, remove)
- Star: toggle favorite (persisted)
- Enrich: trigger enrichment (cost indicator)
- Sequence: open sequence selector
- Remove: confirm dialog → remove from list

### 5.3 Responsive Behavior

**Desktop (>1200px):**
- Full 2-panel layout visible
- Sidebar + Chat + Data Panel

**Tablet (768-1200px):**
- Data panel collapses to overlay
- Toggle button to show/hide

**Mobile (<786px):**
- Single panel (chat only)
- Data panel as bottom sheet
- Swipe up to view leads

---

## 6. Design Tokens (Consistent with Nowing)

### 6.1 Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | `#6366f1` | Primary actions, links |
| `--success` | `#22c55e` | High fit (80-100) |
| `--warning` | `#f59e0b` | Medium fit (50-79) |
| `--danger` | `#ef4444` | Low fit (0-49), remove |
| `--surface` | `#ffffff` | Panel backgrounds |
| `--border` | `#e5e7eb` | Dividers, borders |
| `--text-primary` | `#111827` | Headings |
| `--text-secondary` | `#6b7280` | Labels, metadata |

### 6.2 Typography

| Token | Value | Usage |
|-------|-------|-------|
| `--font-sans` | `Inter, system-ui` | Body text |
| `--font-mono` | `JetBrains Mono` | Code, data |
| `--text-xs` | `12px` | Badges, chips |
| `--text-sm` | `14px` | Body, labels |
| `--text-base` | `16px` | Headings |
| `--text-lg` | `18px` | Panel titles |

### 6.3 Spacing

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | `4px` | Tight padding |
| `--space-2` | `8px` | Chip padding |
| `--space-3` | `12px` | Button padding |
| `--space-4` | `16px` | Panel padding |
| `--space-6` | `24px` | Section spacing |

---

## 7. Implementation Priority

### Phase 1: Foundation (Weeks 1-2)
| Component | Effort | Dependency |
|-----------|--------|------------|
| Data Panel shell (collapsible) | 2d | None |
| Basic data table (Leads tab) | 3d | Data Panel |
| Fit Score badge | 1d | Data Table |
| Star/Remove actions | 1d | Data Table |

### Phase 2: Intelligence (Weeks 3-4)
| Component | Effort | Dependency |
|-----------|--------|------------|
| Suggested Actions | 2d | Agent response hook |
| Filter Chips | 2d | Data Table |
| Sort/Column resize | 1d | Data Table |
| Signals Tab | 2d | Signal detection |

### Phase 3: Automation (Weeks 5-6)
| Component | Effort | Dependency |
|-----------|--------|------------|
| Sequences Tab | 2d | Sequence engine |
| Campaign integration | 2d | Sequences |
| Export functionality | 1d | Data Table |
| Find Similar | 2d | Enrichment API |

---

## 8. User Flow: Lead Intelligence

### 8.1 Primary Flow (Find → Enrich → Sequence)

```
1. User prompt: "Find agarwood companies in Vietnam"
   ↓
2. Agent searches web → generates leads
   ↓
3. Data panel appears with leads table
   ↓
4. Suggested Actions:
   - [Enrich 5 leads] → Waterfall API → Verified contacts
   - [Find similar] → Expand search
   - [Start sequence] → Create outreach
   ↓
5. User clicks [Enrich 5 leads]
   ↓
6. Credits deducted → Contacts enriched
   ↓
7. Data panel updates with contact info
   ↓
8. Suggested Actions:
   - [Start sequence] → Select/create sequence
   - [Export CSV] → Download leads
   ↓
9. User clicks [Start sequence]
   ↓
10. Sequence panel opens → Select template
    ↓
11. Sequence activated → Progress tracked in Sequences tab
```

### 8.2 Signal Detection Flow

```
1. Signal detected: "Company X raised Series A"
   ↓
2. Notification: "New signal for saved search"
   ↓
3. User opens Signals tab
   ↓
4. Signal details: Company, Source, Confidence, Date
   ↓
5. Actions: [Create Lead] [View Company] [Dismiss]
   ↓
6. User clicks [Create Lead]
   ↓
7. Lead added to Leads tab with high intent score
```

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first lead | < 5 min | From prompt to results |
| Lead enrichment rate | > 80% | % leads with verified contact |
| Sequence activation | > 30% | % leads enrolled in sequences |
| Data panel usage | > 60% | % sessions with panel open |
| User satisfaction | > 4.2/5 | Post-interaction survey |

---

**Draft Date:** 2026-08-10
**Author:** Sally (UX Designer)
**Status:** Merged into canonical UX contracts — Zalo/outcome-pricing screens require validation
**Next Step:** Validate Zalo OA setup + outcome-pricing UX with legal/business; then create final UX contract updates
