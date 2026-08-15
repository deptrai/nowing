---
name: Nowing
description: "AI-Powered Lead & Knowledge Intelligence Workspace. 1:1 Origami-inspired architecture with crisp white surfaces, subtle grid-paper textures, and refreshing Light Green (Mint & Emerald) accents."
colors:
  # Primary Brand Palette (Light Green / Emerald / Mint)
  primary: '#10B981'
  primary-hover: '#059669'
  primary-active: '#047857'
  primary-foreground: '#FFFFFF'
  primary-subtle: '#ECFDF5'
  primary-border: '#A7F3D0'
  
  # Accent & Semantic Tokens
  accent-mint: '#34D399'
  accent-mint-light: '#D1FAE5'
  accent-mint-subtle: '#F0FDF4'
  
  # Neutral Backgrounds & Surfaces (Light First)
  background: '#FFFFFF'
  surface-subtle: '#F8FAFC'
  surface-card: '#FFFFFF'
  surface-sidebar: '#F9FAFB'
  surface-grid-paper: '#FFFFFF'
  foreground: '#0F172A'
  foreground-muted: '#475569'
  foreground-subtle: '#94A3B8'
  border: '#E2E8F0'
  border-subtle: '#F1F5F9'
  grid-line: '#F1F5F9'
  
  # Fit Score Tokens (Lead Intelligence)
  fit-score-high: '#10B981'
  fit-score-high-bg: '#ECFDF5'
  fit-score-high-border: '#A7F3D0'
  fit-score-med: '#F59E0B'
  fit-score-med-bg: '#FFFBEB'
  fit-score-med-border: '#FDE68A'
  fit-score-low: '#EF4444'
  fit-score-low-bg: '#FEF2F2'
  fit-score-low-border: '#FECACA'

  # Status & Channel Badges
  status-active: '#10B981'
  status-warning: '#F59E0B'
  status-warning-bg: '#FFFBEB'
  status-warning-border: '#FDE68A'
  channel-zalo: '#0068FF'
  channel-telegram: '#229ED9'
  channel-batdongsan: '#E03C31'
  channel-linkedin: '#0A66C2'

  # Dark Mode Fallback Tokens
  primary-dark: '#34D399'
  primary-foreground-dark: '#064E3B'
  background-dark: '#0B0F12'
  surface-card-dark: '#12181F'
  surface-sidebar-dark: '#0D1217'
  foreground-dark: '#F8FAFC'
  foreground-muted-dark: '#94A3B8'
  border-dark: '#1E293B'

typography:
  # Display (Origami Hero headlines, Welcome moments)
  display:
    fontFamily: 'Instrument Serif, Newsreader, serif'
    fontSize: '36px'
    fontWeight: '400'
    lineHeight: '1.15'
    letterSpacing: '-0.02em'
  display-lg:
    fontFamily: 'Instrument Serif, Newsreader, serif'
    fontSize: '48px'
    fontWeight: '400'
    lineHeight: '1.05'
    letterSpacing: '-0.03em'
  display-sm:
    fontFamily: 'Instrument Serif, Newsreader, serif'
    fontSize: '24px'
    fontWeight: '400'
    lineHeight: '1.2'
    letterSpacing: '-0.01em'

  # UI Sans (Headings, Body, Controls, Tables)
  heading-1:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '20px'
    fontWeight: '700'
    lineHeight: '1.3'
    letterSpacing: '-0.01em'
  heading-2:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '16px'
    fontWeight: '600'
    lineHeight: '1.35'
  body:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '14px'
    fontWeight: '400'
    lineHeight: '1.5'
  body-medium:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '14px'
    fontWeight: '500'
    lineHeight: '1.5'
  caption:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '12px'
    fontWeight: '400'
    lineHeight: '1.4'
  mono:
    fontFamily: 'JetBrains Mono, Menlo, monospace'
    fontSize: '12px'
    fontWeight: '500'

rounded:
  xs: '3px'
  sm: '6px'
  md: '10px'
  lg: '14px'
  xl: '20px'
  full: '9999px'

spacing:
  2xs: '2px'
  xs: '4px'
  sm: '8px'
  md: '12px'
  lg: '16px'
  xl: '24px'
  2xl: '32px'
  3xl: '48px'
  4xl: '64px'

components:
  # Mode Switcher Pill (Outbound / Research / Scrapers)
  mode-switch-container:
    background: '#F1F5F9'
    radius: '{rounded.lg}'
    padding: '3px'
  mode-switch-active:
    background: '#FFFFFF'
    foreground: '{colors.foreground}'
    radius: '{rounded.md}'
    shadow: '0 1px 3px rgba(0,0,0,0.06)'
    fontWeight: '600'

  # Floating Chat Composer Box
  chat-input-box:
    background: '#FFFFFF'
    border: '1px solid {colors.border}'
    radius: '{rounded.xl}'
    shadow: '0 4px 20px -2px rgba(16, 185, 129, 0.06), 0 2px 6px rgba(0,0,0,0.03)'
    padding: '12px 16px'
  chat-send-button:
    background: '{colors.primary}'
    foreground: '{colors.primary-foreground}'
    radius: '{rounded.sm}'
    hoverBackground: '{colors.primary-hover}'

  # Grid Paper Table Header (Origami Signature Pattern)
  table-grid-header:
    backgroundImage: 'linear-gradient(#F1F5F9 1px, transparent 1px), linear-gradient(90deg, #F1F5F9 1px, transparent 1px)'
    backgroundSize: '16px 16px'
    borderBottom: '1px solid {colors.border}'

  # Vertical Targeting Pill
  vertical-pill:
    background: '#FFFFFF'
    border: '1px solid {colors.border}'
    radius: '{rounded.full}'
    hoverBackground: '{colors.primary-subtle}'
    hoverBorder: '{colors.primary-border}'

  # Waterfall Enrichment Card
  waterfall-card:
    background: '#FFFFFF'
    border: '1px solid {colors.border}'
    radius: '{rounded.xl}'
    shadow: '0 1px 3px rgba(0,0,0,0.04)'
---

# Nowing — Design Spine (`DESIGN.md`)

> **Spec Compliance:** Google Labs `DESIGN.md` standard.
> **Visual Reference:** 1:1 architectural alignment with **Origami (`origami.chat`)**, translated into Nowing's **Mint & Emerald Green** identity for Vietnam & Southeast Asian markets.

---

## 1. Brand & Style

### 1.1 Brand Identity: "Origami Precision meets Real-World Lead Growth"
Nowing adapts the celebrated UI elegance of Origami — structured prompt-to-matrix workflow, minimal 2-panel workspaces, and high-density lead tables — while replacing the pink palette with an authoritative, growth-oriented **Light Green (Emerald & Mint)** palette.

### 1.2 Signature Visual Details from Origami
1. **Grid-Paper Table Header Background:** A subtle 16px graph-paper pattern behind the table title and metrics row, giving a drafting/workbench feel.
2. **Tabbed Showcase Navigation:** Clean underlined tab switcher (`Find new leads` · `Enrich data` · `Sequence leads`) providing instant clarity of the 3-step value chain.
3. **Transparent Per-Lead Cost Indicator:** `Projected price 1.5 credits ($0.022) per lead ⌄` positioned directly beside total lead counts.
4. **Editorial Serif Headlines:** `Instrument Serif` / `Newsreader` for high-impact title moments, balanced by crisp `Plus Jakarta Sans` for dense grids.
5. **Waterfall Enrichment Badges:** Multi-provider fallback indicators (Batdongsan → Chotot → Zalo OA).

---

## 2. Colors

- **Primary Emerald (`#10B981` / `#059669`):** Primary buttons, active tabs, confirmed high fit-score badges (`🟩 98%`), and send actions.
- **Mint Subtle Wash (`#ECFDF5` / `#F0FDF4`):** Table row hover highlight, selected filter pills, and AI action card backgrounds.
- **Pure White Canvas (`#FFFFFF`):** High contrast, uncluttered space for multi-column spreadsheets.
- **Border Crispness (`#E2E8F0` / `#F1F5F9`):** 1px dividers defining columns without heavy visual noise.

---

## 3. Typography & Layout Hierarchy

- **Hero & Greetings:** `Instrument Serif` (48px / 36px) — "Tìm kiếm khách hàng mục tiêu. Chỉ với một câu lệnh."
- **Data Tables & Controls:** `Plus Jakarta Sans` (14px body, 12px captions) + `JetBrains Mono` (12px fit scores and decoded phone numbers).
- **Proportions:** 240px Sidebar + 400px Chat Co-pilot Pane + Flex 1 Data Table Matrix.
