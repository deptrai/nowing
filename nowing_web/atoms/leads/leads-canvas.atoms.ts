import { atom } from "jotai";
import type { FilterPresets, Lead } from "@/contracts/types/leads.types";

export type CanvasMode = "leads" | "research" | "automations" | "scrapers" | "artifacts";

// Global fallback mode (for fresh new-chat sessions)
export const canvasModeAtom = atom<CanvasMode>("leads");

// Thread-scoped active canvas modes: key is thread_id, value is CanvasMode
export const threadCanvasModeMapAtom = atom<Record<string, CanvasMode>>({});

// Left Chat Panel width in pixels (clamped: min 280px, max 520px, default 340px)
export const canvasLeftWidthAtom = atom<number>(340);

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
