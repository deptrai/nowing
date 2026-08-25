"use client";

import { DynamicRightPanelCanvas } from "@/components/leads/DynamicRightPanelCanvas";
import type { ThreadParsedContext } from "@/components/leads/thread-intent-detector";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import type { Lead } from "@/contracts/types/leads.types";
import type { DockTabPayload } from "../lib/parse-dock-content";
import type { WebAppBuildResult } from "../lib/parse-web-app-result";
import { DockContent } from "./DockContent";
import { WebBuilderDockTab } from "./WebBuilderDockTab";

export interface DockBodyProps {
	activeTab: string;
	activePayload?: DockTabPayload;
	webAppResult: Partial<WebAppBuildResult> | null;
	workspaceId: number | string;
	threadId?: number | string | null;
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
}

export function DockBody({
	activeTab,
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
}: DockBodyProps) {
	if (activeTab === "leads") {
		return (
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
		);
	}

	if (activeTab === "web-builder" && webAppResult) {
		return <WebBuilderDockTab workspaceId={workspaceId} result={webAppResult} />;
	}

	if (activePayload) {
		return <DockContent activeTab={activeTab} payload={activePayload} workspaceId={workspaceId} />;
	}

	return null;
}
