"use client";

import { useAtom } from "jotai";
import { useEffect, useMemo } from "react";
import {
	type DockTabId,
	dockActiveTabAtom,
	dockExpandedAtom,
	dockOpenAtom,
	dockTabUpdatesAtom,
	dockVerboseModeAtom,
	dockWidthAtom,
} from "@/atoms/layout/dock.atom";
import { canvasLeftWidthAtom } from "@/atoms/leads/leads-canvas.atoms";
import type { ThreadParsedContext } from "@/components/leads/thread-intent-detector";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import type { Lead } from "@/contracts/types/leads.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { type ThreadMessageLike, useDockTabs } from "../hooks/useDockTabs";
import { DockBody } from "./DockBody";
import { DockHeader } from "./DockHeader";
import { DockResizer } from "./DockResizer";
import { FloatingReopenPill } from "./FloatingReopenPill";
import { MobileDockSheet } from "./MobileDockSheet";

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
	const isMobile = useIsMobile();
	const [isOpen] = useAtom(dockOpenAtom);
	const [activeTab, setActiveTab] = useAtom(dockActiveTabAtom);
	const [storedWidth] = useAtom(dockWidthAtom);
	const [isExpanded] = useAtom(dockExpandedAtom);
	const [leftWidth] = useAtom(canvasLeftWidthAtom);
	const [verbose] = useAtom(dockVerboseModeAtom);
	const [updates, setUpdates] = useAtom(dockTabUpdatesAtom);
	const {
		tabs,
		activeTab: effectiveActiveTab,
		activePayload,
		webAppResult,
	} = useDockTabs({
		messages,
		leads,
		threadContext,
	});

	// Keep active tab in sync with available tabs.
	useEffect(() => {
		if (tabs.length === 0) return;
		if (!tabs.find((t) => t.id === activeTab)) {
			setActiveTab(tabs[0].id);
		}
	}, [tabs, activeTab, setActiveTab]);

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

	const bodyProps = {
		activeTab: effectiveActiveTab,
		activePayload,
		webAppResult,
		workspaceId,
		threadId,
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
	};

	if (isMobile) {
		return <MobileDockSheet tabs={tabs} {...bodyProps} />;
	}

	if (!isOpen) {
		return <FloatingReopenPill tabs={tabs} />;
	}

	const expandedWidth = useMemo(() => {
		if (typeof window === "undefined") return storedWidth;
		return Math.max(840, window.innerWidth - leftWidth - 56);
	}, [leftWidth, storedWidth]);

	const effectiveWidth = isExpanded ? expandedWidth : storedWidth;

	return (
		<aside
			className={cn(
				"relative flex h-full shrink-0 flex-col overflow-hidden border-l bg-panel text-sidebar-foreground",
				className
			)}
			style={{ width: effectiveWidth }}
		>
			<DockHeader tabs={tabs} />
			<DockResizer />
			<div
				id="dock-tabpanel"
				role="tabpanel"
				aria-labelledby={`dock-tab-${effectiveActiveTab}`}
				className={cn("flex-1 min-h-0 overflow-hidden transition-opacity", verbose && "opacity-60")}
			>
				<DockBody {...bodyProps} />
			</div>
		</aside>
	);
}
