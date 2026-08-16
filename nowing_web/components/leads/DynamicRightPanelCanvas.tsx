"use client";

import { useAtom } from "jotai";
import { Activity, ChevronDown, PanelLeftOpen, Sparkles, Table as TableIcon, Zap } from "lucide-react";
import type React from "react";
import { useMemo } from "react";
import {
	type CanvasMode,
	isLeftPanelCollapsedAtom,
	isMatrixFullscreenAtom,
	threadCanvasModeMapAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import type { Lead } from "@/contracts/types/leads.types";
import { cn } from "@/lib/utils";
import { OrigamiLeadMatrix } from "./OrigamiLeadMatrix";
import { AutomationBuilderPanel } from "./panels/AutomationBuilderPanel";
import { ResearchStudioPanel } from "./panels/ResearchStudioPanel";
import { ScraperPlatformMonitorPanel } from "./panels/ScraperPlatformMonitorPanel";
import type { ThreadParsedContext } from "./thread-intent-detector";

export type { CanvasMode };

export interface DynamicRightPanelCanvasProps {
	leads: Lead[];
	isLoading?: boolean;
	workspaceId?: string | number;
	threadId?: string | number | null;
	threadContext?: ThreadParsedContext;
	sourceFilter: string;
	onSourceFilterChange: (source: string) => void;
	statusFilter: string;
	onStatusFilterChange: (status: string) => void;
	searchQuery: string;
	onSearchQueryChange: (query: string) => void;
	onRefresh: () => void;
	onOpenReverseIcp?: () => void;
	onOpenCompanyGraph?: (companyName: string) => void;
	className?: string;
}

const VIEW_MODES: Array<{
	id: CanvasMode;
	label: string;
	icon: React.ComponentType<{ className?: string }>;
}> = [
	{ id: "leads", label: "Leads Matrix", icon: TableIcon },
	{ id: "research", label: "Research Studio", icon: Sparkles },
	{ id: "automations", label: "Automation Flow", icon: Zap },
	{ id: "scrapers", label: "Scraper Health", icon: Activity },
];

export const DynamicRightPanelCanvas: React.FC<DynamicRightPanelCanvasProps> = (props) => {
	const [threadModesMap, setThreadModesMap] = useAtom(threadCanvasModeMapAtom);
	const [isFullscreen] = useAtom(isMatrixFullscreenAtom);

	// Session-Scoped Key for this specific chat thread
	const threadKey = String(props.threadId || "default");

	// Active mode is strictly scoped to this thread (derived from threadContext or user override)
	const activeMode: CanvasMode = useMemo(() => {
		if (threadModesMap[threadKey]) {
			return threadModesMap[threadKey];
		}
		return props.threadContext?.detectedIntent || "leads";
	}, [threadModesMap, threadKey, props.threadContext?.detectedIntent]);

	const setActiveMode = (mode: CanvasMode) => {
		setThreadModesMap((prev) => ({
			...prev,
			[threadKey]: mode,
		}));
	};

	// Contextual dynamic title derived strictly from THIS thread
	const dynamicTitle = useMemo(() => {
		if (props.threadContext?.title) {
			return props.threadContext.title;
		}
		if (props.leads.length > 0) {
			const firstLead = props.leads[0];
			if (firstLead.industry) {
				return `Doanh nghiệp ${firstLead.industry} (${props.leads.length})`;
			}
			return `Danh sách khách hàng tiềm năng (${props.leads.length})`;
		}
		return "Tất cả khách hàng tiềm năng";
	}, [props.threadContext?.title, props.leads]);

	// Segmented category chips detected dynamically in current dataset
	const detectedCategories = useMemo(() => {
		const cats = new Set<string>();
		for (const lead of props.leads) {
			if (lead.industry) cats.add(lead.industry);
		}
		return Array.from(cats);
	}, [props.leads]);

	const [isLeftCollapsed, setIsLeftCollapsed] = useAtom(isLeftPanelCollapsedAtom);

	return (
		<div
			data-testid="dynamic-right-panel-canvas"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				isFullscreen && "fixed inset-0 z-50",
				props.className
			)}
		>
			{/* Origami Contextual Top Tab Bar (Session-Scoped & Dynamic, Slim 32px) */}
			<header className="h-8 border-b border-border/80 bg-muted/40 flex items-center justify-between px-2.5 shrink-0 select-none">
				<div className="flex items-center gap-1 overflow-x-auto no-scrollbar flex-1">
					{isLeftCollapsed && (
						<button
							type="button"
							onClick={() => setIsLeftCollapsed(false)}
							className="inline-flex items-center gap-1 px-2 py-0.5 mr-1 rounded-md text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 transition-colors border border-emerald-500/30 shrink-0 cursor-pointer shadow-2xs"
							title="Mở Chat Co-pilot"
						>
							<PanelLeftOpen className="w-3.5 h-3.5" />
							<span>Mở Chat</span>
						</button>
					)}

					{/* Mode: Leads Matrix Dynamic Tabs */}
					{activeMode === "leads" && (
						<>
							{/* Primary Tab: Current Thread's Dataset */}
							<button
								type="button"
								onClick={() => props.onSourceFilterChange("all")}
								className={cn(
									"inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium transition-all cursor-pointer shadow-2xs",
									props.sourceFilter === "all"
										? "bg-background text-foreground shadow-xs font-semibold border border-border/80"
										: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
								)}
							>
								<TableIcon className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
								<span className="truncate max-w-[140px]">{dynamicTitle}</span>
								<span className="font-mono text-[9px] px-1 py-0.2 rounded bg-muted font-bold">
									{props.leads.length}
								</span>
								<ChevronDown className="w-2.5 h-2.5 text-muted-foreground opacity-60 ml-0.5" />
							</button>

							{/* Dynamic Category Tabs */}
							{detectedCategories.slice(0, 3).map((cat) => (
								<button
									key={cat}
									type="button"
									onClick={() => props.onSearchQueryChange(cat)}
									className={cn(
										"inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium transition-all cursor-pointer",
										props.searchQuery === cat
											? "bg-background text-foreground shadow-xs font-semibold border border-border/80"
											: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
									)}
								>
									<TableIcon className="w-2.5 h-2.5 text-muted-foreground" />
									<span className="truncate max-w-[90px]">{cat}</span>
								</button>
							))}
						</>
					)}

					{/* Mode: Research Report Tabs */}
					{activeMode === "research" && (
						<button
							type="button"
							className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-background text-foreground shadow-xs border border-border/80"
						>
							<Sparkles className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
							<span className="truncate max-w-[180px]">
								{props.threadContext?.researchReport?.title || "Báo Cáo Nghiên Cứu Chuyên Sâu"}
							</span>
						</button>
					)}

					{/* Mode: Automation Builder Tabs */}
					{activeMode === "automations" && (
						<button
							type="button"
							className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-background text-foreground shadow-xs border border-border/80"
						>
							<Zap className="w-3 h-3 text-amber-600 dark:text-amber-400" />
							<span className="truncate max-w-[180px]">
								{props.threadContext?.automationWorkflow?.name || "Visual Automation Pipeline"}
							</span>
						</button>
					)}

					{/* Mode: Scrapers Tabs */}
					{activeMode === "scrapers" && (
						<button
							type="button"
							className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-background text-foreground shadow-xs border border-border/80"
						>
							<Activity className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
							<span className="truncate max-w-[180px]">
								Trạng thái Scraper &amp; Phone Waterfall
							</span>
						</button>
					)}
				</div>

				{/* Right: Credits Badge & Mode Switcher */}
				<div className="flex items-center gap-1.5 shrink-0 ml-2">
					<div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-pink-500/10 dark:bg-pink-500/20 text-pink-600 dark:text-pink-400 text-[10px] font-semibold border border-pink-500/20">
						<span>🌸</span>
						<span className="font-mono font-bold">1,420</span> Credits
					</div>

					{/* Mini Mode Switcher */}
					<div className="flex items-center bg-muted/80 p-0.5 rounded-md border border-border/60">
						{VIEW_MODES.map((mode) => {
							const Icon = mode.icon;
							const isActive = activeMode === mode.id;
							return (
								<button
									key={mode.id}
									type="button"
									onClick={() => setActiveMode(mode.id)}
									title={mode.label}
									className={cn(
										"p-1 rounded text-muted-foreground transition-all cursor-pointer",
										isActive
											? "bg-background text-foreground shadow-xs font-semibold"
											: "hover:text-foreground"
									)}
								>
									<Icon className="w-3 h-3" />
								</button>
							);
						})}
					</div>
				</div>
			</header>

			{/* Panel View Switching Router */}
			<main className="flex-1 min-h-0 relative overflow-hidden">
				{activeMode === "leads" && (
					<OrigamiLeadMatrix
						leads={props.leads}
						isLoading={props.isLoading}
						workspaceId={props.workspaceId}
						sourceFilter={props.sourceFilter}
						onSourceFilterChange={props.onSourceFilterChange}
						statusFilter={props.statusFilter}
						onStatusFilterChange={props.onStatusFilterChange}
						searchQuery={props.searchQuery}
						onSearchQueryChange={props.onSearchQueryChange}
						onRefresh={props.onRefresh}
						onOpenReverseIcp={props.onOpenReverseIcp}
						onOpenCompanyGraph={props.onOpenCompanyGraph}
					/>
				)}

				{activeMode === "research" && (
					<ResearchStudioPanel
						workspaceId={props.workspaceId}
						report={props.threadContext?.researchReport}
					/>
				)}

				{activeMode === "automations" && (
					<AutomationBuilderPanel
						workspaceId={props.workspaceId}
						workflow={props.threadContext?.automationWorkflow}
					/>
				)}

				{activeMode === "scrapers" && (
					<ScraperPlatformMonitorPanel workspaceId={props.workspaceId} />
				)}
			</main>
		</div>
	);
};
