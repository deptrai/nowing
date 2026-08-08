"use client";

import type { UseQueryOptions, UseQueryResult } from "@tanstack/react-query";
import { useQueries } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo, useRef } from "react";
import { activeTabIdAtom, removeChatTabAtom, type Tab, tabsAtom } from "@/atoms/tabs/tabs.atom";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getThreadFull } from "@/lib/chat/thread-persistence";
import { NotFoundError } from "@/lib/error";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const THREAD_STALE_TIME_MS = 60 * 1000;
const DOCUMENT_STALE_TIME_MS = 5 * 60 * 1000;

export interface ResolvedTab extends Tab {
	title: string;
	url?: string;
	isLoading: boolean;
	isNotFound: boolean;
}

export function isValidEntityId(entityId: string): boolean {
	return entityId !== "" && entityId !== "new";
}

export function parseEntityId(entityId: string): number {
	const parsed = Number.parseInt(entityId, 10);
	return Number.isNaN(parsed) || parsed <= 0 ? 0 : parsed;
}

export function isNotFoundError(error: unknown): boolean {
	return error instanceof NotFoundError;
}

export function getChatUrl(workspaceId: number, entityId: string): string {
	return isValidEntityId(entityId)
		? `/dashboard/${workspaceId}/new-chat/${parseEntityId(entityId)}`
		: `/dashboard/${workspaceId}/new-chat`;
}

export function getFallbackTitle(tab: Tab): string {
	if (tab.type === "chat") {
		return isValidEntityId(tab.entityId) ? `Chat ${tab.entityId}` : "New Chat";
	}
	return `Document ${tab.entityId}`;
}

function getQueryOptions(tab: Tab): UseQueryOptions<unknown, Error, unknown> {
	if (tab.type === "chat" && isValidEntityId(tab.entityId)) {
		const threadId = parseEntityId(tab.entityId);
		return {
			queryKey: cacheKeys.threads.detail(threadId),
			queryFn: () => getThreadFull(threadId),
			enabled: true,
			staleTime: THREAD_STALE_TIME_MS,
		};
	}

	if (tab.type === "document" && isValidEntityId(tab.entityId)) {
		const documentId = parseEntityId(tab.entityId);
		return {
			queryKey: cacheKeys.documents.document(String(documentId)),
			queryFn: () => documentsApiService.getDocument({ id: documentId }),
			enabled: true,
			staleTime: DOCUMENT_STALE_TIME_MS,
		};
	}

	return {
		queryKey: ["tabs", "noop", tab.id] as const,
		queryFn: () => null,
		enabled: false,
		staleTime: Number.POSITIVE_INFINITY,
	};
}

export function resolveTab(tab: Tab, result: UseQueryResult<unknown, Error>): ResolvedTab {
	const isNotFound = isNotFoundError(result.error);
	let title = getFallbackTitle(tab);
	let url: string | undefined;

	if (tab.type === "chat") {
		url = getChatUrl(tab.workspaceId, tab.entityId);
		const record = result.data as { title?: string } | null | undefined;
		if (record?.title) {
			title = record.title;
		}
	} else if (tab.type === "document") {
		const document = result.data as { title?: string } | null | undefined;
		if (document?.title) {
			title = document.title;
		}
	}

	return {
		...tab,
		title,
		url,
		isLoading: result.isLoading,
		isNotFound,
	};
}

export function useResolvedTabs() {
	const tabs = useAtomValue(tabsAtom);
	const activeTabId = useAtomValue(activeTabIdAtom);
	const removeChatTab = useSetAtom(removeChatTabAtom);

	const options = useMemo(() => tabs.map(getQueryOptions), [tabs]);
	const results = useQueries({ queries: options }) as UseQueryResult<unknown, Error>[];

	const resolvedTabs = useMemo(
		() => tabs.map((tab, i) => resolveTab(tab, results[i] as UseQueryResult<unknown, Error>)),
		[tabs, results]
	);

	const activeResolvedTab = useMemo(
		() => resolvedTabs.find((t) => t.id === activeTabId) ?? null,
		[resolvedTabs, activeTabId]
	);

	const isLoading = useMemo(() => resolvedTabs.some((t) => t.isLoading), [resolvedTabs]);

	const closingRef = useRef<Set<string>>(new Set());

	const notFoundKey = useMemo(
		() =>
			resolvedTabs
				.map((tab) => {
					if (tab.type === "chat" && tab.isNotFound) return tab.id;
					return "";
				})
				.filter(Boolean)
				.join(","),
		[resolvedTabs]
	);

	useEffect(() => {
		if (!notFoundKey) return;

		for (const tab of resolvedTabs) {
			if (tab.type === "chat" && tab.isNotFound && !closingRef.current.has(tab.id)) {
				closingRef.current.add(tab.id);
				const chatId = parseEntityId(tab.entityId);
				if (chatId > 0) {
					removeChatTab(chatId);
				}
			}
		}
	}, [notFoundKey, resolvedTabs, removeChatTab]);

	return {
		tabs: resolvedTabs,
		activeTab: activeResolvedTab,
		activeTabId,
		isLoading,
	};
}
