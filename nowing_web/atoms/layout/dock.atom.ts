"use client";

import { atom } from "jotai";

/** Tabs available in the contextual right dock. */
export type DockTabId =
	| "leads"
	| "web-builder"
	| "slides"
	| "research"
	| "reports"
	| "images"
	| "media"
	| "data"
	| "charts"
	| "code"
	| "sources"
	| "artifacts";

/** Whether the contextual right dock is open. */
export const dockOpenAtom = atom(false);

/** Currently active dock tab. */
export const dockActiveTabAtom = atom<DockTabId>("leads");

/** Dock width in pixels. */
export const dockWidthAtom = atom<number>(420);

/** Verbose mode: show rich content inline in the chat stream instead of (or in addition to) the dock. */
export const dockVerboseModeAtom = atom(false);

/** The app_id currently focused in the Web Builder tab. */
export const dockWebBuilderAppIdAtom = atom<string | null>(null);

/** Tracks which tabs have unseen updates since the user last viewed them. */
export const dockTabUpdatesAtom = atom<Partial<Record<DockTabId, number>>>({});
