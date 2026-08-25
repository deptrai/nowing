"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { type DockTabId, dockActiveTabAtom, dockTabUpdatesAtom } from "@/atoms/layout/dock.atom";
import type { ThreadParsedContext } from "@/components/leads/thread-intent-detector";
import type { Lead } from "@/contracts/types/leads.types";
import { type DockTabPayload, parseDockContent } from "../lib/parse-dock-content";
import type { WebAppBuildResult } from "../lib/parse-web-app-result";

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

export interface UseDockTabsInput {
	messages: readonly ThreadMessageLike[];
	leads: Lead[];
	threadContext?: ThreadParsedContext;
}

export function useDockTabs({ messages, leads, threadContext }: UseDockTabsInput) {
	const activeTab = useAtomValue(dockActiveTabAtom);
	const updates = useAtomValue(dockTabUpdatesAtom);

	const hasLeads = leads.length > 0 || threadContext?.detectedIntent === "leads";

	const parsedTabs = useMemo(
		() => parseDockContent(messages as ThreadMessageLike[], { hasLeads }),
		[messages, hasLeads]
	);

	const tabs = useMemo<DockTab[]>(
		() =>
			parsedTabs.map((tab) => ({
				...tab,
				hasUpdate: Boolean(updates[tab.id as DockTabId]),
			})),
		[parsedTabs, updates]
	);

	const defaultTab = tabs[0]?.id ?? (hasLeads ? "leads" : undefined);
	const effectiveActiveTab = tabs.find((t) => t.id === activeTab)?.id ?? defaultTab ?? "leads";

	const activePayload = useMemo<DockTabPayload | undefined>(() => {
		const active = tabs.find((t) => t.id === effectiveActiveTab);
		return (active?.payload as DockTabPayload | undefined) ?? undefined;
	}, [tabs, effectiveActiveTab]);

	const webAppResult = useMemo<Partial<WebAppBuildResult> | null>(() => {
		const found = parsedTabs.find((t) => t.id === "web-builder")?.payload as
			| { kind: "web-builder"; result: Partial<WebAppBuildResult> }
			| undefined;
		return found?.result ?? null;
	}, [parsedTabs]);

	return {
		tabs,
		activeTab: effectiveActiveTab,
		activePayload,
		webAppResult,
	};
}
