"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { type DockTabId, dockActiveTabAtom, dockTabUpdatesAtom } from "@/atoms/layout/dock.atom";
import type { ThreadParsedContext } from "@/components/leads/thread-intent-detector";
import type { Lead } from "@/contracts/types/leads.types";
import { parseWebAppResult, type WebAppBuildResult } from "../lib/parse-web-app-result";

export interface DockTab {
	id: DockTabId;
	label: string;
	icon?: string;
	hasUpdate: boolean;
	payload?: unknown;
}

export interface ThreadMessageLike {
	role: string;
	content?: unknown;
}

function isToolCallPart(
	part: unknown
): part is { type: "tool-call"; toolName: string; result?: unknown } {
	return (
		typeof part === "object" &&
		part !== null &&
		(part as { type?: unknown }).type === "tool-call" &&
		typeof (part as { toolName?: unknown }).toolName === "string"
	);
}

function extractLatestWebAppResult(
	messages: readonly ThreadMessageLike[]
): Partial<WebAppBuildResult> | null {
	let latest: Partial<WebAppBuildResult> | null = null;
	for (const message of messages) {
		if (message.role !== "assistant" || !Array.isArray(message.content)) continue;
		for (const part of message.content) {
			if (!isToolCallPart(part)) continue;
			if (part.toolName !== "build_web_app") continue;
			const parsed = parseWebAppResult(part.result);
			if (parsed.app_id) latest = parsed;
		}
	}
	return latest;
}

export interface UseDockTabsInput {
	messages: readonly ThreadMessageLike[];
	leads: Lead[];
	threadContext?: ThreadParsedContext;
}

export function useDockTabs({ messages, leads, threadContext }: UseDockTabsInput) {
	const activeTab = useAtomValue(dockActiveTabAtom);
	const updates = useAtomValue(dockTabUpdatesAtom);

	const webAppResult = useMemo(() => extractLatestWebAppResult(messages), [messages]);

	// ponytail: only leads and web-builder tabs are wired; extend here for slides/research/charts/images/etc.
	const tabs = useMemo<DockTab[]>(() => {
		const list: DockTab[] = [];

		if (leads.length > 0 || threadContext?.detectedIntent === "leads") {
			list.push({ id: "leads", label: "Leads", hasUpdate: Boolean(updates.leads) });
		}

		if (webAppResult?.app_id) {
			list.push({
				id: "web-builder",
				label: "Web Builder",
				hasUpdate: Boolean(updates["web-builder"]),
				payload: { result: webAppResult },
			});
		}

		return list;
	}, [leads.length, threadContext?.detectedIntent, webAppResult, updates]);

	const defaultTab = tabs[0]?.id ?? "leads";
	const effectiveActiveTab = tabs.find((t) => t.id === activeTab) ? activeTab : defaultTab;

	return {
		tabs,
		activeTab: effectiveActiveTab,
		webAppResult,
	};
}
