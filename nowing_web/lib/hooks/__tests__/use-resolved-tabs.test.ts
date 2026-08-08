import assert from "node:assert/strict";
import { test } from "node:test";
import type { UseQueryResult } from "@tanstack/react-query";
import type { Tab } from "@/atoms/tabs/tabs.atom";
import { NotFoundError } from "@/lib/error";
import {
	getChatUrl,
	getFallbackTitle,
	isNotFoundError,
	isValidEntityId,
	parseEntityId,
	resolveTab,
} from "../use-resolved-tabs";

// Run with: pnpm exec tsx --test lib/hooks/__tests__/use-resolved-tabs.test.ts

// --- Minimal helpers to build mock query results without a React runtime ---

function loadingResult(): UseQueryResult<unknown, Error> {
	return {
		data: undefined,
		error: null,
		isLoading: true,
		isPending: true,
		isError: false,
		isSuccess: false,
		isFetching: true,
		isPlaceholderData: false,
		status: "pending",
		fetchStatus: "fetching",
	} as unknown as UseQueryResult<unknown, Error>;
}

function successResult(data: unknown): UseQueryResult<unknown, Error> {
	return {
		data,
		error: null,
		isLoading: false,
		isPending: false,
		isError: false,
		isSuccess: true,
		isFetching: false,
		isPlaceholderData: false,
		status: "success",
		fetchStatus: "idle",
	} as unknown as UseQueryResult<unknown, Error>;
}

function errorResult(error: Error): UseQueryResult<unknown, Error> {
	return {
		data: undefined,
		error,
		isLoading: false,
		isPending: false,
		isError: true,
		isSuccess: false,
		isFetching: false,
		isPlaceholderData: false,
		status: "error",
		fetchStatus: "idle",
	} as unknown as UseQueryResult<unknown, Error>;
}

const chatTab: Tab = { id: "chat-42", type: "chat", entityId: "42", workspaceId: 1 };
const docTab: Tab = { id: "doc-99", type: "document", entityId: "99", workspaceId: 5 };
const newChatTab: Tab = { id: "chat-new", type: "chat", entityId: "new", workspaceId: 1 };

// --- isValidEntityId ---

test("isValidEntityId rejects empty string and 'new'", () => {
	assert.equal(isValidEntityId(""), false);
	assert.equal(isValidEntityId("new"), false);
	assert.equal(isValidEntityId("42"), true);
	assert.equal(isValidEntityId("1"), true);
});

// --- parseEntityId ---

test("parseEntityId returns 0 for non-numeric, negative, or zero", () => {
	assert.equal(parseEntityId("abc"), 0);
	assert.equal(parseEntityId("-1"), 0);
	assert.equal(parseEntityId("0"), 0);
	assert.equal(parseEntityId("42"), 42);
});

// --- isNotFoundError ---

test("isNotFoundError returns true only for NotFoundError instances", () => {
	assert.equal(isNotFoundError(new NotFoundError("not found", 404)), true);
	assert.equal(isNotFoundError(new Error("network failure")), false);
	assert.equal(isNotFoundError(null), false);
	assert.equal(isNotFoundError(undefined), false);
});

// --- getChatUrl ---

test("getChatUrl derives thread URL for valid entityId", () => {
	assert.equal(getChatUrl(1, "42"), "/dashboard/1/new-chat/42");
});

test("getChatUrl derives new-chat URL for 'new' entityId", () => {
	assert.equal(getChatUrl(1, "new"), "/dashboard/1/new-chat");
});

test("getChatUrl derives new-chat URL for empty entityId", () => {
	assert.equal(getChatUrl(3, ""), "/dashboard/3/new-chat");
});

// --- getFallbackTitle ---

test("getFallbackTitle returns 'New Chat' for new chat tab", () => {
	assert.equal(getFallbackTitle(newChatTab), "New Chat");
});

test("getFallbackTitle returns 'Chat {id}' for existing chat tab", () => {
	assert.equal(getFallbackTitle(chatTab), "Chat 42");
});

test("getFallbackTitle returns 'Document {id}' for document tab", () => {
	assert.equal(getFallbackTitle(docTab), "Document 99");
});

// --- resolveTab: live title resolution ---

test("resolveTab uses live title from thread metadata when available", () => {
	const result = successResult({ title: "My Research Chat" });
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.title, "My Research Chat");
	assert.equal(resolved.url, "/dashboard/1/new-chat/42");
	assert.equal(resolved.isLoading, false);
	assert.equal(resolved.isNotFound, false);
});

test("resolveTab uses live title from document metadata when available", () => {
	const result = successResult({ title: "Q3 Report" });
	const resolved = resolveTab(docTab, result);
	assert.equal(resolved.title, "Q3 Report");
	assert.equal(resolved.isNotFound, false);
});

test("resolveTab falls back to placeholder title while loading", () => {
	const result = loadingResult();
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.title, "Chat 42");
	assert.equal(resolved.isLoading, true);
	assert.equal(resolved.isNotFound, false);
});

test("resolveTab falls back to 'New Chat' for new chat tab while loading", () => {
	const result = loadingResult();
	const resolved = resolveTab(newChatTab, result);
	assert.equal(resolved.title, "New Chat");
	assert.equal(resolved.url, "/dashboard/1/new-chat");
});

// --- resolveTab: 404 pruning vs transient errors ---

test("resolveTab sets isNotFound=true on definitive 404 (NotFoundError)", () => {
	const result = errorResult(new NotFoundError("Thread not found", 404));
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.isNotFound, true);
	assert.equal(resolved.title, "Chat 42"); // fallback title
});

test("resolveTab sets isNotFound=false on transient network error", () => {
	const result = errorResult(new Error("Network timeout"));
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.isNotFound, false);
	assert.equal(resolved.title, "Chat 42"); // fallback title
});

test("resolveTab sets isNotFound=false on 500 server error", () => {
	const result = errorResult(new Error("Internal server error"));
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.isNotFound, false);
});

// --- resolveTab: edge cases ---

test("resolveTab handles null metadata gracefully", () => {
	const result = successResult(null);
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.title, "Chat 42");
	assert.equal(resolved.isNotFound, false);
});

test("resolveTab handles metadata without title field", () => {
	const result = successResult({ id: 42 });
	const resolved = resolveTab(chatTab, result);
	assert.equal(resolved.title, "Chat 42");
});
