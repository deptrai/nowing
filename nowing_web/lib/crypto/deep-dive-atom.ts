import { atom } from "jotai";

/**
 * Pending deep-dive prompt.
 * NextActionBar (inside AssistantMessage context) writes here.
 * Thread composer (at thread level) reads and clears it.
 */
export const pendingDeepDiveAtom = atom<string | null>(null);
