import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";
import { patchThreadEverywhere } from "@/lib/chat/thread-cache";
import { queryClient } from "@/lib/query-client/client";
import { makeChatTabId, makeDocumentTabId, migrateLegacyTabs, type TabType } from "./migrate-tabs";

export type { TabType } from "./migrate-tabs";

export interface Tab {
	id: string;
	type: TabType;
	entityId: string;
	workspaceId: number;
}

interface TabsState {
	tabs: Tab[];
	activeTabId: string | null;
}

const initialState: TabsState = {
	tabs: [{ id: "chat-new", type: "chat", entityId: "new", workspaceId: 0 }],
	activeTabId: "chat-new",
};

// Prevent race conditions where route-sync recreates a just-deleted chat tab.
const deletedChatIdsAtom = atom<Set<number>>(new Set<number>());

// Persist tabs in localStorage so they survive a hard refresh and let the user
// keep tabs open across multiple workspaces (browser-like behavior).
const localStorageAdapter = createJSONStorage<TabsState>(
	() => (typeof window !== "undefined" ? localStorage : undefined) as Storage
);

const V1_STORAGE_KEY = "nowing:tabs";
const V2_STORAGE_KEY = "nowing:tabs:v2";

// Wrap getItem so the v2 key can migrate from an existing v1 snapshot.
const baseGetItem = localStorageAdapter.getItem.bind(localStorageAdapter);
localStorageAdapter.getItem = (key, initialValue) => {
	if (key !== V2_STORAGE_KEY) {
		return baseGetItem(key, initialValue);
	}

	const v2 = baseGetItem(V2_STORAGE_KEY, initialValue);
	if (v2 !== initialValue) {
		return migrateLegacyTabs(v2);
	}

	const v1 = baseGetItem(V1_STORAGE_KEY, initialValue);
	if (v1 !== initialValue) {
		const migrated = migrateLegacyTabs(v1);
		if (typeof window !== "undefined") {
			try {
				window.localStorage.setItem(V2_STORAGE_KEY, JSON.stringify(migrated));
			} catch {
				// Ignore storage write failures; the in-memory state is already migrated.
			}
		}
		return migrated;
	}

	return initialValue;
};

export const tabsStateAtom = atomWithStorage<TabsState>(
	V2_STORAGE_KEY,
	initialState,
	localStorageAdapter,
	{ getOnInit: true }
);

export const tabsAtom = atom((get) => get(tabsStateAtom).tabs);
export const activeTabIdAtom = atom((get) => get(tabsStateAtom).activeTabId);
export const activeTabAtom = atom((get) => {
	const state = get(tabsStateAtom);
	return state.tabs.find((t) => t.id === state.activeTabId) ?? null;
});

/**
 * Sync the current chat from Next.js routing into the tab bar.
 * If a tab for this chat already exists, activate it.
 * Otherwise, replace the "new chat" tab or create one.
 */
export const syncChatTabAtom = atom(
	null,
	(get, set, { chatId, workspaceId }: { chatId: number | null; workspaceId: number }) => {
		if (chatId && get(deletedChatIdsAtom).has(chatId)) {
			return;
		}

		const state = get(tabsStateAtom);
		const entityId = chatId ? String(chatId) : "new";
		const tabId = makeChatTabId(entityId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) =>
					t.id === tabId ? { ...t, workspaceId: workspaceId ?? t.workspaceId } : t
				),
			});
			return;
		}

		// If navigating to a new chat (no chatId), ensure there is a "new chat" tab
		// scoped to the current workspace.
		if (!chatId) {
			const hasNewChatTab = state.tabs.some((t) => t.id === "chat-new");
			if (hasNewChatTab) {
				set(tabsStateAtom, {
					...state,
					activeTabId: "chat-new",
					tabs: state.tabs.map((t) => (t.id === "chat-new" ? { ...t, workspaceId } : t)),
				});
			} else {
				set(tabsStateAtom, {
					tabs: [...state.tabs, { id: "chat-new", type: "chat", entityId: "new", workspaceId }],
					activeTabId: "chat-new",
				});
			}
			return;
		}

		// Replace the "new chat" tab if it exists and is empty, otherwise add a new tab.
		const newChatTabIdx = state.tabs.findIndex((t) => t.id === "chat-new");
		const newTab: Tab = {
			id: tabId,
			type: "chat",
			entityId,
			workspaceId,
		};

		let updatedTabs: Tab[];
		if (newChatTabIdx !== -1) {
			updatedTabs = [...state.tabs];
			updatedTabs[newChatTabIdx] = newTab;
		} else {
			updatedTabs = [...state.tabs, newTab];
		}

		set(tabsStateAtom, { tabs: updatedTabs, activeTabId: tabId });
	}
);

/**
 * Update the live title for a chat tab.
 * In the pointer model, titles live in the thread query cache, so this patches
 * the cache that `useResolvedTabs` reads instead of mutating the tab itself.
 */
export const updateChatTabTitleAtom = atom(
	null,
	(
		get,
		_set,
		{ chatId, title, workspaceId }: { chatId: number; title: string; workspaceId?: number }
	) => {
		const state = get(tabsStateAtom);
		const tabWorkspaceId =
			workspaceId ??
			state.tabs.find((t) => t.type === "chat" && t.entityId === String(chatId))?.workspaceId;

		if (tabWorkspaceId == null) {
			return;
		}

		patchThreadEverywhere(queryClient, tabWorkspaceId, chatId, { title });
	}
);

/** Open a document tab. If already open, just switch to it. */
export const openDocumentTabAtom = atom(
	null,
	(get, set, { documentId, workspaceId }: { documentId: number; workspaceId: number }) => {
		const state = get(tabsStateAtom);
		const entityId = String(documentId);
		const tabId = makeDocumentTabId(entityId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, { ...state, activeTabId: tabId });
			return;
		}

		const newTab: Tab = {
			id: tabId,
			type: "document",
			entityId,
			workspaceId,
		};

		set(tabsStateAtom, {
			tabs: [...state.tabs, newTab],
			activeTabId: tabId,
		});
	}
);

/** Switch to a tab by ID. Returns the tab so the caller can navigate if needed. */
export const switchTabAtom = atom(null, (get, set, tabId: string) => {
	const state = get(tabsStateAtom);
	const tab = state.tabs.find((t) => t.id === tabId);
	if (tab) {
		set(tabsStateAtom, { ...state, activeTabId: tabId });
	}
	return tab ?? null;
});

/** Close a tab. If it was active, activate the nearest sibling. */
export const closeTabAtom = atom(null, (get, set, tabId: string) => {
	const state = get(tabsStateAtom);
	const idx = state.tabs.findIndex((t) => t.id === tabId);
	if (idx === -1) return null;

	const remaining = state.tabs.filter((t) => t.id !== tabId);

	// Don't close the last tab — always keep at least one.
	if (remaining.length === 0) {
		set(tabsStateAtom, { ...initialState });
		return initialState.tabs[0];
	}

	let newActiveId = state.activeTabId;
	if (state.activeTabId === tabId) {
		// Activate the tab to the left (or right if first).
		const newIdx = Math.min(idx, remaining.length - 1);
		newActiveId = remaining[newIdx]?.id ?? null;
	}

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
	return remaining.find((t) => t.id === newActiveId) ?? null;
});

/** Remove a chat tab by chat ID (used when a chat is deleted). */
export const removeChatTabAtom = atom(null, (get, set, chatId: number) => {
	const state = get(tabsStateAtom);
	const tabId = makeChatTabId(String(chatId));
	const idx = state.tabs.findIndex((t) => t.id === tabId);
	if (idx === -1) return null;

	const deletedChatIds = get(deletedChatIdsAtom);
	set(deletedChatIdsAtom, new Set([...deletedChatIds, chatId]));

	const remaining = state.tabs.filter((t) => t.id !== tabId);

	// Always keep at least one tab available.
	if (remaining.length === 0) {
		set(tabsStateAtom, { ...initialState });
		return initialState.tabs[0];
	}

	let newActiveId = state.activeTabId;
	if (state.activeTabId === tabId) {
		const newIdx = Math.min(idx, remaining.length - 1);
		newActiveId = remaining[newIdx]?.id ?? null;
	}

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
	return remaining.find((t) => t.id === newActiveId) ?? null;
});

/** Reset tabs when switching workspaces. */
export const resetTabsAtom = atom(null, (_get, set) => {
	set(tabsStateAtom, { ...initialState });
	set(deletedChatIdsAtom, new Set<number>());
});
