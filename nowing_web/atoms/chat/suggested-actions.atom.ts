"use client";

import { atom } from "jotai";

export interface SuggestedActionsThreadState {
	isDismissed: boolean;
	lastUpdatedTurnId?: string | null;
}

/**
 * Stores thread-scoped suggested actions collapse/dismissal preferences.
 * Keyed by threadId (string or number).
 */
export const suggestedActionsSessionMapAtom = atom<Record<string, SuggestedActionsThreadState>>({});
