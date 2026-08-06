import assert from "node:assert/strict";
import { test } from "node:test";
import { migrateLegacyTabs } from "./migrate-tabs";

// Run with: pnpm exec tsx --test atoms/tabs/migrate-tabs.test.ts

test("maps legacy searchSpaceId to workspaceId on read", () => {
	const migrated = migrateLegacyTabs({
		tabs: [{ id: "chat-new", type: "chat", searchSpaceId: 7 }],
		activeTabId: "chat-new",
	});
	const tab = migrated.tabs[0];
	assert.equal(tab?.workspaceId, 7);
	assert.equal(tab?.entityId, "new");
	assert.equal(tab?.id, "chat-new");
	assert.equal(migrated.activeTabId, "chat-new");
});

test("leaves an already-migrated workspaceId untouched", () => {
	const migrated = migrateLegacyTabs({
		tabs: [{ id: "d1", type: "document", workspaceId: 3, searchSpaceId: 9 }],
	});
	const tab = migrated.tabs[0];
	assert.equal(tab?.workspaceId, 3);
});

test("migrates a v1 chat snapshot to a v2 pointer and updates the active tab id", () => {
	const migrated = migrateLegacyTabs({
		tabs: [
			{
				id: "chat-new",
				type: "chat",
				title: "My Chat",
				chatId: 42,
				chatUrl: "/dashboard/1/new-chat/42",
				workspaceId: 1,
				visibility: "PRIVATE",
				hasComments: false,
			},
		],
		activeTabId: "chat-new",
	});
	const tab = migrated.tabs[0];
	assert.equal(tab?.id, "chat-42");
	assert.equal(tab?.type, "chat");
	assert.equal(tab?.entityId, "42");
	assert.equal(tab?.workspaceId, 1);
	assert.equal((tab as { title?: string }).title, undefined);
	assert.equal(migrated.activeTabId, "chat-42");
});

test("migrates a v1 document snapshot to a v2 pointer", () => {
	const migrated = migrateLegacyTabs({
		tabs: [
			{
				id: "doc-99",
				type: "document",
				title: "Notes",
				documentId: 99,
				workspaceId: 5,
			},
		],
		activeTabId: "doc-99",
	});
	const tab = migrated.tabs[0];
	assert.equal(tab?.id, "doc-99");
	assert.equal(tab?.type, "document");
	assert.equal(tab?.entityId, "99");
	assert.equal(tab?.workspaceId, 5);
	assert.equal((tab as { title?: string }).title, undefined);
});

test("is idempotent for an already-migrated v2 state", () => {
	const state = {
		tabs: [{ id: "chat-7", type: "chat" as const, entityId: "7", workspaceId: 2 }],
		activeTabId: "chat-7",
	};
	const migrated = migrateLegacyTabs(state);
	assert.deepEqual(migrated.tabs, state.tabs);
	assert.equal(migrated.activeTabId, "chat-7");
});
