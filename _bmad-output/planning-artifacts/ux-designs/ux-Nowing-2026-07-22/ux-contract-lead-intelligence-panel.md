# UX Contract — Lead Intelligence Data Panel

**Ngày:** 2026-08-10
**Phạm vi:** Epic 21 — Lead Intelligence 2-panel layout
**Bám vào:** FR-63..FR-69, Story 21.1-21.7, AD-36..AD-42
**Loại tài liệu:** *contract* — định nghĩa UI phải biểu diễn được những trạng thái nào.
**Ghi chú:** Zalo OA connection setup UI và outcome-pricing display screens còn pending validation sau khi legal/ToS và business verification đóng.

---

## 1. Layout: 2-Panel Mode

Chat panel (trái) + Data panel (phải), collapsible.

| Trạng thái | Nguồn event | Bắt buộc |
|---|---|---|
| **Split view** | Có leads/signals/sequences trong workspace | ✅ |
| **Full-width chat** | User collapse data panel | ✅ |
| **Panel restored** | User toggle panel hoặc có data mới | ✅ |
| **Mobile** | Viewport < 768px | Panel → bottom sheet |

### Toggle Behavior
- Toggle button ở chat header (phải)
- Icon: table (📊) khi đóng, X khi mở
- Keyboard shortcut: `Cmd/Ctrl + D`
- State persisted trong localStorage

---

## 2. Data Table Panel

### Table Tabs
| Tab | Nội dung | Nguồn |
|-----|----------|-------|
| Leads | Lead list với fit score, company, website | FR-64, FR-65 |
| Signals | Intent signals (funding, hiring, tech stack) | FR-63 |
| Sequences | Outreach sequences & progress | FR-66 |

### Table Columns (Leads Tab)
| Column | Width | Sortable | Filterable |
|--------|-------|----------|------------|
| ⭐ | 40px | No | No |
| Fit Score | 80px | Yes | Yes |
| Company | 200px | Yes | Yes |
| Website | 150px | No | No |
| Industry | 120px | Yes | Yes |
| Signals | 100px | Yes | Yes |
| Contact | 150px | No | No |
| Actions | 120px | No | No |

### Fit Score Color Coding
| Range | Color | Meaning |
|-------|-------|---------|
| 80-100 | 🟢 Green | High fit |
| 50-79 | 🟡 Yellow | Medium fit |
| 0-49 | 🔴 Red | Low fit |

### Row Actions (hover to reveal)
- ⭐ Star: toggle favorite (persisted)
- 🔍 Enrich: trigger enrichment (cost indicator)
- 📧 Sequence: open sequence selector
- 🗑️ Remove: confirm dialog → remove from list

---

## 3. Suggested Actions

Xuất hiện sau agent response tạo leads/data.

| # | Action | Channel | Cost |
|---|--------|---------|------|
| 1 | Enrich 5 leads | FR-65 | 2.5 credits |
| 2 | Find similar companies | FR-6 | Free |
| 3 | Start outreach sequence | FR-66 | Variable |

### Behavior
- Fade-in animation (200ms) sau 500ms delay
- Max 3 actions visible
- Hover: scale 1.02 + shadow
- Click: execute + loading state

---

## 4. Filter Chips

Inline data refinement.

| Type | Options |
|------|---------|
| Location | Vietnam, US, EU, ... |
| Industry | SaaS, Fintech, E-commerce, ... |
| Company Size | 1-10, 11-50, 51-200, 200+ |
| Signal Type | Funding, Hiring, Tech Stack, News |
| Date Range | Last 7d, 30d, 90d, All |

### Behavior
- Add: click "+" → dropdown → select → chip appears
- Remove: click "×" on chip
- Clear all: "Clear" link
- Max 5 visible chips, overflow in dropdown

---

## 5. Campaigns/Sequences Section

| Trạng thái | Hiển thị |
|---|---|
| Not connected | "Not sending yet — connect a campaign" |
| Active | "Active: Sequence Name" + progress |
| Paused | "Paused: Sequence Name" |

### Sequence Progress
```
Step 1: ✅ Sent    Step 2: ⏳ Waiting    Step 3: ○ Pending
```

---

## 6. Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (>1200px) | Full 2-panel (sidebar + chat + data) |
| Tablet (768-1200px) | Data panel collapses to overlay |
| Mobile (<768px) | Single panel, data as bottom sheet |

---

## 7. Credits Display

Hiển thị cost-per-action transparency.

| Context | Display |
|---------|---------|
| Enrich button | "2.5 credits ($0.036) per lead" |
| Sequence start | "Est. 5-10 credits per sequence" |
| Header | Total credits remaining: "$5.03" |

---

_Trace: epic21-lead-intelligence-ux.md → AD-36..AD-42 → FR-63..FR-69_
