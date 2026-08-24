"use client";

import { useAtom } from "jotai";
import { useEffect } from "react";
import {
	type DockTabId,
	dockActiveTabAtom,
	dockOpenAtom,
	dockTabUpdatesAtom,
	dockWidthAtom,
} from "@/atoms/layout/dock.atom";
import { DynamicRightPanelCanvas } from "@/components/leads/DynamicRightPanelCanvas";
import type { ThreadParsedContext } from "@/components/leads/thread-intent-detector";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import type { Lead } from "@/contracts/types/leads.types";
import { cn } from "@/lib/utils";
import { type ThreadMessageLike, useDockTabs } from "../hooks/useDockTabs";
import { DockHeader } from "./DockHeader";
import { FloatingReopenPill } from "./FloatingReopenPill";
import { WebBuilderDockTab } from "./WebBuilderDockTab";

export interface ContextualDockProps {
	workspaceId: number | string;
	threadId?: number | string | null;
	messages: ThreadMessageLike[];
	leads: Lead[];
	isLoading?: boolean;
	threadContext?: ThreadParsedContext;
	sourceFilter: string;
	onSourceFilterChange: (source: string) => void;
	statusFilter: string;
	onStatusFilterChange: (status: string) => void;
	searchQuery: string;
	onSearchQueryChange: (query: string) => void;
	onRefresh: () => void;
	onOpenReverseIcp?: () => void;
	onOpenDnc?: () => void;
	onOpenCompanyGraph?: (companyName: string) => void;
	shimmerCount?: number;
	unlockedPhones?: Record<string, string | null>;
	onPhoneChange?: (leadId: string, phone: string | null, unlocked: boolean) => void;
	missionControl?: DshMissionControl | null;
	latestMission?: DshMission | null;
	missionLoading?: boolean;
	missionError?: string | null;
	className?: string;
}

export function ContextualDock({
	workspaceId,
	threadId,
	messages,
	leads,
	isLoading,
	threadContext,
	sourceFilter,
	onSourceFilterChange,
	statusFilter,
	onStatusFilterChange,
	searchQuery,
	onSearchQueryChange,
	onRefresh,
	onOpenReverseIcp,
	onOpenDnc,
	onOpenCompanyGraph,
	shimmerCount,
	unlockedPhones,
	onPhoneChange,
	missionControl,
	latestMission,
	missionLoading,
	missionError,
	className,
}: ContextualDockProps) {
	const [isOpen] = useAtom(dockOpenAtom);
	const [activeTab, setActiveTab] = useAtom(dockActiveTabAtom);
	const [width] = useAtom(dockWidthAtom); // ponytail: dock width is fixed at 420px; add a resizer in the next iteration.
	const [updates, setUpdates] = useAtom(dockTabUpdatesAtom);
	const {
		tabs,
		activeTab: effectiveActiveTab,
		webAppResult,
	} = useDockTabs({ messages, leads, threadContext });

	// Keep active tab in sync with available tabs.
	useEffect(() => {
		if (tabs.length === 0) return;
		if (!tabs.find((t) => t.id === activeTab)) {
			setActiveTab(tabs[0].id);
		}
	}, [tabs, activeTab, setActiveTab]);

	// The dock only auto-opens when the user explicitly asks (e.g. "Open Editor").
	// New contextual tabs pulse in the floating pill instead of stealing focus.

	// Mark the active tab as "seen" when it is active.
	useEffect(() => {
		if (updates[effectiveActiveTab]) {
			setUpdates((prev: Partial<Record<DockTabId, number>>) => ({
				...prev,
				[effectiveActiveTab]: 0,
			}));
		}
	}, [effectiveActiveTab, updates, setUpdates]);

	if (tabs.length === 0) return null;

	if (!isOpen) {
		return <FloatingReopenPill tabs={tabs} />;
	}

	return (
		<aside
			className={cn(
				"relative flex h-full shrink-0 flex-col overflow-hidden border-l bg-panel text-sidebar-foreground",
				className
			)}
			style={{ width }}
		>
			<DockHeader tabs={tabs} />
			<div className="flex-1 min-h-0 overflow-hidden">
				{effectiveActiveTab === "leads" && (
					<DynamicRightPanelCanvas
						leads={leads}
						isLoading={isLoading}
						workspaceId={workspaceId}
						threadId={threadId}
						threadContext={threadContext}
						sourceFilter={sourceFilter}
						onSourceFilterChange={onSourceFilterChange}
						statusFilter={statusFilter}
						onStatusFilterChange={onStatusFilterChange}
						searchQuery={searchQuery}
						onSearchQueryChange={onSearchQueryChange}
						onRefresh={onRefresh}
						onOpenReverseIcp={onOpenReverseIcp}
						onOpenDnc={onOpenDnc}
						onOpenCompanyGraph={onOpenCompanyGraph}
						shimmerCount={shimmerCount}
						unlockedPhones={unlockedPhones}
						onPhoneChange={onPhoneChange}
						missionControl={missionControl}
						latestMission={latestMission}
						missionLoading={missionLoading}
						missionError={missionError}
					/>
				)}
				{effectiveActiveTab === "web-builder" && webAppResult && (
					<WebBuilderDockTab workspaceId={workspaceId} result={webAppResult} />
				)}
			</div>
		</aside>
	);
}
