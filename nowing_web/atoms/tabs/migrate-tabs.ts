/**
 * One-time read-migration for persisted tabs.
 *
 * v1 stored full snapshots (`chatId`, `documentId`, `title`, `chatUrl`,
 * `visibility`, `hasComments`). v2 stores lightweight pointers (`entityId`,
 * `workspaceId`) plus `id` and `type`. The legacy state is migrated on first
 * read and the active tab is preserved.
 */

export type TabType = "chat" | "document";

export interface V2Tab {
	id: string;
	type: TabType;
	entityId: string;
	workspaceId: number;
}

interface V1Tab {
	id?: string;
	type?: TabType;
	title?: string;
	chatId?: number | null;
	chatUrl?: string;
	visibility?: string;
	hasComments?: boolean;
	documentId?: number;
	workspaceId?: number;
	searchSpaceId?: number;
}

interface V1State {
	tabs: V1Tab[];
	activeTabId?: string | null;
}

interface V2State {
	tabs: V2Tab[];
	activeTabId: string | null;
}

export function makeChatTabId(entityId: string): string {
	return entityId && entityId !== "new" ? `chat-${entityId}` : "chat-new";
}

export function makeDocumentTabId(entityId: string): string {
	return `doc-${entityId}`;
}

function isV2Tab(tab: unknown): tab is V2Tab {
	return (
		typeof tab === "object" &&
		tab !== null &&
		"entityId" in tab &&
		!("chatId" in tab) &&
		!("documentId" in tab)
	);
}

function getV1EntityId(tab: V1Tab, type: TabType): string {
	if (type === "chat") {
		if (tab.chatId != null) return String(tab.chatId);
		if (tab.id === "chat-new") return "new";
		if (tab.id?.startsWith("chat-")) return tab.id.slice(5);
		return "";
	}
	if (tab.documentId != null) return String(tab.documentId);
	if (tab.id?.startsWith("doc-")) return tab.id.slice(4);
	return "";
}

function migrateTab(tab: V1Tab | V2Tab): V2Tab {
	if (isV2Tab(tab)) {
		return {
			id: tab.id,
			type: tab.type,
			entityId: tab.entityId,
			workspaceId: tab.workspaceId,
		};
	}

	const legacy = tab as V1Tab;
	const workspaceId =
		legacy.workspaceId !== undefined && legacy.workspaceId !== null
			? legacy.workspaceId
			: (legacy.searchSpaceId ?? 0);
	const type = legacy.type ?? "chat";
	const entityId = getV1EntityId(legacy, type);
	const id = type === "chat" ? makeChatTabId(entityId) : makeDocumentTabId(entityId);

	return { id, type, entityId, workspaceId };
}

export function migrateLegacyTabs(state: V1State | V2State): V2State {
	const tabs = state.tabs.map(migrateTab);

	const oldToNewId = new Map<string, string>();
	for (let i = 0; i < state.tabs.length; i++) {
		const old = state.tabs[i]?.id;
		if (old != null) {
			oldToNewId.set(old, tabs[i]?.id ?? old);
		}
	}

	let activeTabId = state.activeTabId;
	if (activeTabId != null) {
		activeTabId = oldToNewId.get(activeTabId) ?? activeTabId;
	}

	return { ...state, tabs, activeTabId: activeTabId ?? null };
}
