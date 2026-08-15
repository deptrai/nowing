import { atom } from "jotai";
import type { FilterPresets, Lead } from "@/contracts/types/leads.types";

export type CanvasMode = "leads" | "research" | "automations" | "scrapers" | "artifacts";

// Polymorphic Right Panel Mini-App active mode
export const canvasModeAtom = atom<CanvasMode>("leads");

// Left Chat Panel width in pixels (clamped: min 360px, max 650px, default 420px)
export const canvasLeftWidthAtom = atom<number>(420);

// Panel collapse & fullscreen states
export const isLeftPanelCollapsedAtom = atom<boolean>(false);
export const isMatrixFullscreenAtom = atom<boolean>(false);

// Bi-directional Context Sync: Selected lead for Chat Copilot prompt badge
export const selectedLeadContextAtom = atom<Lead | null>(null);

// Table Multi-Selection for Floating Bulk Action Bar
export const selectedLeadIdsAtom = atom<string[]>([]);

// Active Lead for Right Slide-Over Detail Flyout Drawer (480px)
export const activeDrawerLeadAtom = atom<Lead | null>(null);

// Chat -> Table: Highlighted rows triggered by AI assistant
export const chatHighlightedRowIdsAtom = atom<string[]>([]);

// Active filter preset applied to table
export const activeFilterPresetAtom = atom<FilterPresets | null>(null);
