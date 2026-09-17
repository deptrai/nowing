---
story_key: 37-4-zalo-desktop-web-co-pilot-overlay-in-nowing-lead-clipper
status: ready-for-dev
epic: 37
priority: P0
target_codebase: nowing_browser_extension
architectural_invariants: [AD-118]
---

# Story 37.4: Zalo Desktop/Web Co-pilot Overlay in Nowing Lead Clipper

**Status:** `ready-for-dev`  
**Epic:** Epic 37: Nowing Revenue Engine — Unified Outbound Workstation  
**Priority:** P0  
**Target Codebase:** `nowing_browser_extension`  
**Architectural Alignment:** Extends `nowing_browser_extension/` (Epic 24.4) and `zalo.me/{phone}` assisted link.

## Story

As a Sales Rep using Zalo on browser or desktop,  
I want the Nowing Lead Clipper extension to detect open Zalo chats and provide a 1-click contextual prompt drawer,  
So that I can execute personalized outbound touches with human-in-the-loop control without risking account bans.

## Acceptance Criteria

- **AC-1 (Zalo Chat Target Detection):** Detects active phone/conversation on `chat.zalo.me`, matching with unlocked leads from Nowing. Renders a 36px floating action pill at the right edge, expanding on click into a 320px contextual flyout drawer.
- **AC-2 (Docked Context Drawer):** Displays prospect company context, recent intent signals, and recommended pitch copy with 2 tab options: `[Ngắn gọn]` / `[Kèm link Pitch]`.
- **AC-3 (Semantic Selector & Zero Ban Guarantee):** `Chèn tin nhắn` button populates Zalo's active textbox via semantic selector (`div[contenteditable="true"]`, `div[role="textbox"]`) using standard `InputEvent`/`insertText` per AD-118 without background automated sending, ensuring zero account ban penalty.
- **AC-4 (DNC Blacklist Suppression):** If prospect phone exists in DNC blacklist (Decree 91/2020/NĐ-CP), renders a red warning banner and disables message insertion.
- **AC-5 (Non-Destructive Paste):** If the Zalo input already contains draft text, prompts confirmation before overwriting or appends below.
