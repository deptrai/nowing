import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";
import { atomFamily } from "jotai-family";
import type { FilterPresets, Lead } from "@/contracts/types/leads.types";

export interface FastUnlockSessionState {
	expires_at: number;
}

const fastUnlockSessionStorage = createJSONStorage<FastUnlockSessionState | null>(
	() => (typeof window !== "undefined" ? sessionStorage : undefined) as Storage
);

// Per-workspace, per-user fast-unlock session keyed in sessionStorage.
export const fastUnlockSessionAtom = atomFamily((key: string) =>
	atomWithStorage<FastUnlockSessionState | null>(
		`nowing:fast-unlock-session:${key}`,
		null,
		fastUnlockSessionStorage
	)
);

export function makeFastUnlockKey(workspaceId: number | string, userId?: string | null) {
	return `${workspaceId}:${userId ?? "anon"}`;
}

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

// Active viewing Artifact / Dataset Card ID (for chat <-> right canvas synchronization)
export const activeArtifactIdAtom = atom<string | null>("leads-main");

// Ping / Focus trigger timestamp (when user clicks artifact card in chat to ping right panel)
export const canvasHighlightTriggerAtom = atom<number>(0);
