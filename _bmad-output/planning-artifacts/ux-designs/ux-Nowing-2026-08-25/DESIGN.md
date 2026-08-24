---
name: Contextual Right Dock
status: final
updated: 2026-08-25
description: Visual identity and component tokens for the Nowing chat Contextual Right Dock. Inherits the existing Nowing shadcn/ui + Tailwind design system; this file specifies the dock-specific brand-layer deltas only.
---

# Contextual Right Dock — DESIGN.md

The Contextual Right Dock turns the Nowing chat workspace into a Manus-like agentic canvas: the chat stream stays text-only, while rich deliverables (leads, web builder, research, charts, tables, images, code, reports, slides) render in a tabbed panel on the right. The design inherits Nowing's existing shadcn/ui surface; this file only defines the deltas needed for the dock chrome, tab behavior, and content-type badge vocabulary.

## Brand & Style

The dock is **a secondary, context-aware surface**, not a main navigation chrome. Its personality is "quiet until needed":

- Neutral background (`bg-panel`) so it does not compete with chat.
- Active tab uses the same `bg-background` elevation as cards.
- Contextual updates are signaled by a single **emerald pulse** (`emerald-500`), never by multiple competing colors.
- The dock collapses to zero chrome when closed; chat becomes the only stage.

## Colors

The dock adds no new palette. It composes existing tokens:

- `background` / `foreground` — tab content area.
- `panel` / `panel-foreground` — dock background and header.
- `muted` / `muted-foreground` — inactive tabs, secondary meta.
- `border` / `border-border/80` — dividers between tabs and content.
- `ring` — focus rings on tab buttons and resizer.
- `emerald-500` / `emerald-500/20` — **contextual update pulse** and badge dot.
- `amber-500` / `amber-500/20` — **verbose-mode active** indicator (only when verbose is on).
- `primary` — primary CTAs inside tab content (Publish, Open Editor, Regenerate).

## Typography

Inherit Nowing's existing Geist Sans ramp:

- Dock header title: `text-xs font-medium uppercase tracking-wide text-muted-foreground`.
- Tab labels: `text-xs font-medium`.
- Badge counts: `text-[10px] font-mono font-bold`.
- Content titles (tab-level): `text-sm font-semibold`.
- Everything else inside tab content uses the component's own text scale (e.g. lead matrix, report panel).

## Layout & Spacing

- Default dock width: `420px`.
- Min width: `360px`.
- Max width: `80vw` (resize clamp).
- Header height: `h-9` (`36px`).
- Tab bar: horizontal scroll, `gap-0.5`, `px-2`.
- Content area: `flex-1 min-h-0 overflow-hidden`.
- Resize handle: `w-1.5` hit area, `bg-border`, `hover:bg-emerald-500/80`, keyboard `ArrowLeft` / `ArrowRight` move 20px.

## Elevation & Depth

- Dock: `border-l bg-panel` — one separator line, no shadow.
- Active tab: `bg-background border border-border/80 shadow-xs` — raised slightly above the panel.
- Floating reopen pill (when dock closed): `bg-background border shadow-md rounded-full`.
- Tab content scroll shadows at top/bottom only when overflow exists.

## Shapes

- Tab buttons: `rounded-md`.
- Badges/dots: `rounded-full`.
- Close/expand/verbose buttons: `rounded-full` icon buttons, `size-7`.
- Floating pill: `rounded-full`.

## Components

### DockHeader

Row of controls at the top of the right dock:

- **Close button** (`X`) — top-left, closes dock completely; chat becomes full-width.
- **Tab bar** — horizontal scroll of tab chips; overflow collapses into `⋯` dropdown.
- **Verbose toggle** — icon-only, tooltip `Show full output in chat`.
- **Expand/Fullscreen** — optional, maximizes dock to full viewport.

### DockTab

A tab chip in the header:

- Icon + truncated label.
- Active: `bg-background border shadow-xs`.
- Inactive: `text-muted-foreground hover:text-foreground hover:bg-muted/60`.
- Has new content: `ring-1 ring-emerald-500/60 animate-pulse` + emerald dot badge.
- Closable tabs (ephemeral inline content): show `×` on hover.

### DockContent

Container that renders the active tab's component. No extra chrome beyond the tab's own layout.

### FloatingReopenPill

Appears top-right when the dock is closed and at least one tab has content:

- `PanelRightOpen` icon + optional count badge.
- Click reopens dock to the last active tab.

### VerboseBadge

A small chip near the composer or header when verbose mode is active:

- `MessageSquare` icon + `Verbose` label.
- Amber background to signal "chat stream is showing everything".

## Do's and Don'ts

- **Do** keep the dock background neutral; let the content inside carry color.
- **Do** use a single emerald pulse for contextual updates.
- **Do** truncate tab labels aggressively; use tooltips for full names.
- **Do** make the resizer keyboard-accessible.
- **Don't** auto-switch tabs without user action.
- **Don't** show the dock when no contextual content exists.
- **Don't** add a second sidebar inside the dock; tabs are the navigation.
- **Don't** use verbose mode by default on desktop.
