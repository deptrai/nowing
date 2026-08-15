"use client";

import { useAtom } from "jotai";
import {
	Activity,
	Code2,
	FileText,
	Maximize2,
	Minimize2,
	Table as TableIcon,
	Zap,
} from "lucide-react";
import type React from "react";
import {
	type CanvasMode,
	canvasModeAtom,
	isMatrixFullscreenAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import type { Lead } from "@/contracts/types/leads.types";
import { cn } from "@/lib/utils";
import { OrigamiLeadMatrix } from "./OrigamiLeadMatrix";
import { ArtifactsStudioPanel } from "./panels/ArtifactsStudioPanel";
import { AutomationBuilderPanel } from "./panels/AutomationBuilderPanel";
import { ResearchStudioPanel } from "./panels/ResearchStudioPanel";
import { ScraperPlatformMonitorPanel } from "./panels/ScraperPlatformMonitorPanel";

export interface DynamicRightPanelCanvasProps {
	leads: Lead[];
	isLoading?: boolean;
	workspaceId?: string | number;
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

export const DynamicRightPanelCanvas: React.FC<DynamicRightPanelCanvasProps> = (props) => {
	const [activeMode, setActiveMode] = useAtom(canvasModeAtom);
	const [isFullscreen, setIsFullscreen] = useAtom(isMatrixFullscreenAtom);

	const modeTabs: Array<{ id: CanvasMode; label: string; icon: React.ReactNode; badge?: string }> =
		[
			{
				id: "leads",
				label: "Leads Matrix",
				icon: <TableIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />,
				badge: props.leads.length > 0 ? String(props.leads.length) : undefined,
			},
			{
				id: "research",
				label: "Deep Research",
				icon: <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />,
			},
			{
				id: "automations",
				label: "Automations",
				icon: <Zap className="w-3.5 h-3.5 text-amber-500" />,
			},
			{
				id: "scrapers",
				label: "Scraper Hub",
				icon: <Activity className="w-3.5 h-3.5 text-indigo-500" />,
			},
			{
				id: "artifacts",
				label: "Artifacts",
				icon: <Code2 className="w-3.5 h-3.5 text-purple-500" />,
			},
		];

	return (
		<div
			data-testid="dynamic-right-panel-canvas"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				isFullscreen && "fixed inset-0 z-50",
				props.className
			)}
		>
			{/* Polymorphic Master Tab Bar on Right Panel */}
			<div className="h-10 border-b border-border/80 bg-muted/40 flex items-center justify-between px-3 shrink-0">
				<div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar flex-1">
					{modeTabs.map((tab) => {
						const isActive = activeMode === tab.id;
						return (
							<button
								key={tab.id}
								type="button"
								onClick={() => setActiveMode(tab.id)}
								className={cn(
									"flex items-center gap-1.5 px-3 py-1 rounded-t-md text-xs font-semibold transition-all shrink-0 cursor-pointer",
									isActive
										? "bg-background text-foreground border-t-2 border-t-emerald-500 border-x border-border/80 shadow-xs"
										: "text-muted-foreground hover:text-foreground hover:bg-background/60 border border-transparent hover:border-border/50"
								)}
							>
								{tab.icon}
								<span>{tab.label}</span>
								{tab.badge && (
									<span className="px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-mono text-[10px] font-bold">
										{tab.badge}
									</span>
								)}
							</button>
						);
					})}
				</div>

				<div className="flex items-center gap-2 shrink-0">
					<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium border border-emerald-500/20">
						<span className="text-[10px]">💎</span>
						<span className="font-mono font-bold">1,420</span> Credits
					</div>
					<button
						type="button"
						onClick={() => setIsFullscreen(!isFullscreen)}
						className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
					>
						{isFullscreen ? (
							<Minimize2 className="w-3.5 h-3.5" />
						) : (
							<Maximize2 className="w-3.5 h-3.5" />
						)}
					</button>
				</div>
			</div>

			{/* Dynamic Mini-App Body Viewport */}
			<div className="flex-1 overflow-hidden">
				{activeMode === "leads" && <OrigamiLeadMatrix {...props} />}

				{activeMode === "research" && <ResearchStudioPanel workspaceId={props.workspaceId} />}

				{activeMode === "automations" && <AutomationBuilderPanel workspaceId={props.workspaceId} />}

				{activeMode === "scrapers" && (
					<ScraperPlatformMonitorPanel workspaceId={props.workspaceId} />
				)}

				{activeMode === "artifacts" && <ArtifactsStudioPanel workspaceId={props.workspaceId} />}
			</div>
		</div>
	);
};
