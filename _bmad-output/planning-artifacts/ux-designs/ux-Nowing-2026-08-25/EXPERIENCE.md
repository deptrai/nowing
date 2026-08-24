---
name: Contextual Right Dock
status: final
updated: 2026-08-25
sources:
  - _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md
  - _bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md
  - _bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md
---

# Contextual Right Dock — EXPERIENCE.md

The Contextual Right Dock is a secondary workspace that lives to the right of the Nowing chat stream. It holds rich, non-text outputs generated during a chat turn — leads matrices, web builder previews, research reports, charts, tables, images, code, slides, and media. The chat stream stays focused on conversation; the dock focuses on artifacts.

Two display modes exist:

- **Dynamic (default):** rich content is parsed into dock tabs.
- **Verbose:** all content renders inline in the chat stream, like the legacy behavior. Session-scoped toggle.

## Foundation

Nowing responsive web app. Primary surface is desktop (`≥lg`, 1024px+) where the dock sits beside chat. On mobile (`<md`, 768px-) the dock becomes a bottom-sheet tab switcher. shadcn/ui + Tailwind CSS + Framer Motion for transitions.

## Information Architecture

| Surface | Trigger | Content |
|---|---|---|
| Chat stream | Always | Conversation, quick actions, status chips, compact tool result cards |
| Right dock | Rich output present | Tabbed context workspace |
| Leads tab | Lead-gen intent or `leads` tool result | `NowingLeadMatrix`, filters, bulk actions |
| Web Builder tab | `build_web_app` tool result / `WorkspaceApp` artifact | App preview iframe, code viewer, prompt editor, publish CTA |
| Slides tab | `build_slides` tool result (Story 27.2) | Slide deck preview/editor |
| Research tab | `chainlens.research` / research report | `ResearchStudioPanel` with citations |
| Reports tab | `generate_report` result | `ReportPanelContent` |
| Images tab | `generate_image` result(s) | Thumbnail gallery, lightbox |
| Media tab | `generate_video` / `generate_podcast` | Player + metadata |
| Data tab | Markdown table or tool JSON table | Rendered table with CSV export |
| Charts tab | Mermaid / chart spec / JSON chart | Chart renderer or code fallback |
| Code tab | Code block > 12 lines or `ProjectWriter` files | Syntax highlighted viewer, copy, open editor |
| Sources tab | Citations / source list | Citation panel |
| Artifacts tab | Any deliverable tool call | Aggregated deliverable list |

## Voice and Tone

The dock does not speak on its own. Labels and tooltips:

- "Open canvas" / "Close canvas"
- "View in Web Builder"
- "2 new in Research"
- "Showing full output in chat"

Avoid celebratory copy. The agent already celebrated in chat; the dock is a workspace.

## Component Patterns

### Tab bar

- Horizontal scroll.
- Leftmost: close button.
- Tabs ordered by most-recently-updated, pinned tabs first.
- Active tab has solid background and border.
- Tabs with unseen updates pulse with emerald ring and badge.
- Overflow (>5 visible tabs) collapses into `⋯ More` dropdown.
- Rightmost: verbose toggle.

### Dock content area

- `flex-1 min-h-0`.
- Each tab owns its own scroll container.
- Empty tab: component's own empty state (e.g. `No leads yet`).

### Floating reopen pill

- Appears top-right when dock is closed and tabs exist.
- Shows `PanelRightOpen` icon + optional count badge.
- Click reopens dock to the most recently updated tab.

### Verbose toggle

- Icon toggle in dock header and also in chat composer menu.
- When on, chat stream expands rich content inline and dock visually dims to indicate it is not the primary surface.

## State Patterns

| State | Treatment |
|---|---|
| No rich content | Dock hidden; chat full width. |
| Content available, dock closed | Floating pill with badge. |
| Content available, dock open | Active tab shown; other tabs show badges if updated. |
| User switches tab | Previous tab state preserved (scroll, selection). |
| New content in inactive tab | Tab pulses; badge increments. |
| User closes tab | Tab removed if ephemeral; pinned tabs cannot be closed by user. |
| Verbose mode on | Rich content also renders in chat; dock still available. |
| Mobile | Dock becomes bottom sheet with vertical tab list. |
| Resize | Width persists in session atom; double-click resizer resets to 420px. |

## Interaction Primitives

- **Click tab** — switch tab.
- **Click pulsing tab** — switch and clear update badge.
- **Click X (top-left header)** — close dock; chat full width.
- **Click floating pill** — reopen dock.
- **Drag resizer** — resize dock width, clamped 360px–80vw.
- **Keyboard** — `ArrowLeft`/`ArrowRight` on resizer nudges 20px; `Esc` inside dock does not close it (only Escape in header or close button).
- **Click "Open Editor" in chat card** — open Web Builder tab inline.
- **Toggle verbose** — session-scoped; chat stream rerenders.

## Accessibility Floor

- WCAG 2.2 AA inherited from shadcn defaults.
- Tab bar is a `tablist`; each tab is `role="tab"` with `aria-selected`.
- Update pulse uses motion; respect `prefers-reduced-motion` by switching to static emerald dot.
- Resizer is keyboard-operable and announces width changes via `aria-valuenow`.
- Dock close and reopen buttons have `aria-expanded`.

## Responsive & Platform

| Breakpoint | Dock behavior |
|---|---|
| `≥lg` (1024px+) | Fixed right panel beside chat; resizable. |
| `md` (768–1023px) | Dock width clamped to `360px`; chat shrinks. |
| `<md` (768px-) | Dock hidden; a bottom sheet tab switcher appears when rich content exists. Verbose toggle is primary fallback. |

On mobile, the bottom sheet can be swiped up to half-screen height and swiped down to collapse. Chat remains usable underneath.

## Key Flows

### Flow 1 — Building a landing page (Minh, marketer)

1. Minh types: "Build a modern SaaS landing page."
2. Agent returns a `GenerateWebAppToolUI` card in chat and a `WorkspaceApp` result.
3. The `Web Builder` tab in the dock pulses. Dock stays closed if it was closed; the floating pill shows a dot.
4. Minh clicks the floating pill (or the `Open Editor` button in the chat card).
5. Dock opens to the Web Builder tab: preview iframe, code file tree, and a `Publish` button.
6. Minh drags the resizer to make the preview wider.
7. He edits the prompt in the dock and clicks `Regenerate`; the agent streams a new version in the same thread.
8. After publish, the tab badge changes to `Published`.
9. Minh clicks the header X; dock closes; chat is full width again.

### Flow 2 — Lead gen turns into a chart (Linh, growth)

1. Linh asks for "lead list for BĐS Hà Nội."
2. Agent returns leads; the `Leads` tab auto-appears and pulses.
3. Linh asks: "Plot them by district."
4. Agent returns a chart; the `Charts` tab appears and pulses. The `Leads` tab stays active because Linh was reviewing it.
5. Linh clicks `Charts`; a bar chart renders.
6. She toggles verbose to show the chart inline in chat for a screenshot.
7. She toggles verbose off; dock remains the source of truth.

### Flow 3 — Mobile user on the go (Tùng, field sales)

1. Tùng chats on phone. The dock is not visible.
2. Agent returns leads. A bottom sheet handle appears with "2 tabs."
3. Tùng swipes up to see Leads, Web Builder, etc.
4. He taps a lead, detail flyout opens over the sheet.
5. He swipes the sheet down to return to chat.

## Inspiration & Anti-patterns

- **Lifted from Manus / Claude Artifacts / v0:** the artifact lives next to the conversation, not inside it; the chat is the orchestrator.
- **Lifted from Linear:** tab bar is quiet, badges are minimal, keyboard-friendly.
- **Lifted from Figma:** right panel is a contextual properties/artifacts surface; collapsible to maximize canvas.
- **Rejected — auto-switch tabs:** would disorient users who are reviewing one artifact while another updates.
- **Rejected — persistent dock with no content:** empty chrome is noise; hide it when nothing is there.
- **Rejected — separate `/web-builder` page as the only editor:** breaks thread context; the page remains available for full-screen editing but the dock is the default entry point from chat.
