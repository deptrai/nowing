"use client";

import { useAtom } from "jotai";
import {
	Activity,
	ChevronDown,
	Code2,
	FileText,
	Maximize2,
	Minimize2,
	Plus,
	Table as TableIcon,
	Zap,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
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

const VIEW_MODES: Array<{ id: CanvasMode; label: string; icon: React.ReactNode }> = [
	{
		id: "leads",
		label: "Bảng Leads Matrix",
		icon: <TableIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />,
	},
	{
		id: "research",
		label: "Báo cáo Deep Research",
		icon: <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />,
	},
	{
		id: "automations",
		label: "Visual Automation",
		icon: <Zap className="w-3.5 h-3.5 text-amber-500" />,
	},
	{
		id: "scrapers",
		label: "Giám sát Scraper Hub",
		icon: <Activity className="w-3.5 h-3.5 text-indigo-500" />,
	},
	{
		id: "artifacts",
		label: "Artifacts & Studio",
		icon: <Code2 className="w-3.5 h-3.5 text-purple-500" />,
	},
];

export const DynamicRightPanelCanvas: React.FC<DynamicRightPanelCanvasProps> = (props) => {
	const [activeMode, setActiveMode] = useAtom(canvasModeAtom);
	const [isFullscreen, setIsFullscreen] = useAtom(isMatrixFullscreenAtom);
	const [isViewDropdownOpen, setIsViewDropdownOpen] = useState(false);

	// Contextual dynamic title derived from the current leads dataset
	const dynamicTitle = useMemo(() => {
		if (props.leads.length > 0) {
			const firstLead = props.leads[0];
			if (firstLead.industry) {
				return `Doanh nghiệp ${firstLead.industry} Việt Nam`;
			}
			return `Danh sách khách hàng tiềm năng (${props.leads.length})`;
		}
		return "Tất cả khách hàng tiềm năng";
	}, [props.leads]);

	// Segmented category chips detected dynamically in current dataset
	const detectedCategories = useMemo(() => {
		const cats = new Set<string>();
		for (const lead of props.leads) {
			if (lead.industry) cats.add(lead.industry);
		}
		return Array.from(cats);
	}, [props.leads]);

	const currentViewMeta = useMemo(() => {
		return VIEW_MODES.find((m) => m.id === activeMode) ?? VIEW_MODES[0];
	}, [activeMode]);

	return (
		<div
			data-testid="dynamic-right-panel-canvas"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				isFullscreen && "fixed inset-0 z-50",
				props.className
			)}
		>
			{/* Origami Contextual Top Tab Bar (Purely Dynamic, Zero Clutter) */}
			<header className="h-10 border-b border-border/80 bg-muted/40 flex items-center justify-between px-3 shrink-0 select-none">
				<div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar flex-1">
					{/* Mode: Leads Matrix Dynamic Tabs */}
					{activeMode === "leads" && (
						<>
							<button
								type="button"
								onClick={() => props.onSourceFilterChange("all")}
								className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-emerald-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0 cursor-pointer"
							>
								<TableIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
								<span className="truncate max-w-[200px]">{dynamicTitle}</span>
								{props.leads.length > 0 && (
									<span className="px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-mono text-[10px] font-bold">
										{props.leads.length}
									</span>
								)}
								<ChevronDown className="w-3 h-3 text-muted-foreground ml-0.5" />
							</button>

							{/* Dynamic category tabs if detected */}
							{detectedCategories.slice(0, 2).map((cat) => (
								<button
									key={cat}
									type="button"
									onClick={() => props.onSearchQueryChange(cat)}
									className="flex items-center gap-1 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-background/60 rounded-t-md transition-colors shrink-0 cursor-pointer border border-transparent hover:border-border/50"
								>
									<span className="truncate max-w-[140px]">{cat}</span>
								</button>
							))}

							<button
								type="button"
								title="Thêm bảng xem mới"
								className="p-1 text-muted-foreground hover:text-foreground hover:bg-background/80 rounded transition-colors cursor-pointer"
							>
								<Plus className="w-3.5 h-3.5" />
							</button>
						</>
					)}

					{/* Mode: Research Studio Dynamic Tabs */}
					{activeMode === "research" && (
						<div className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-blue-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0">
							<FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
							<span>Báo cáo nghiên cứu thị trường</span>
						</div>
					)}

					{/* Mode: Automation Builder Dynamic Tabs */}
					{activeMode === "automations" && (
						<div className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-amber-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0">
							<Zap className="w-3.5 h-3.5 text-amber-500" />
							<span>Quy trình Automation &amp; Triggers</span>
						</div>
					)}

					{/* Mode: Scraper Monitor Dynamic Tabs */}
					{activeMode === "scrapers" && (
						<div className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-indigo-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0">
							<Activity className="w-3.5 h-3.5 text-indigo-500" />
							<span>Trạng thái Scraper &amp; Phone Waterfall</span>
						</div>
					)}

					{/* Mode: Artifacts Studio Dynamic Tabs */}
					{activeMode === "artifacts" && (
						<div className="flex items-center gap-1.5 px-3 py-1 bg-background border-t-2 border-t-purple-500 border-x border-border/80 rounded-t-md text-xs font-semibold text-foreground shadow-xs shrink-0">
							<Code2 className="w-3.5 h-3.5 text-purple-500" />
							<span>Studio Artifacts &amp; Templates</span>
						</div>
					)}
				</div>

				{/* Right Side Utilities: Credits, View Mode Switcher Dropdown, Fullscreen Toggle */}
				<div className="flex items-center gap-2 shrink-0">
					{/* Credits pill */}
					<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium border border-emerald-500/20">
						<span className="text-[10px]">💎</span>
						<span className="font-mono font-bold">1,420</span> Credits
					</div>

					{/* Clean View Mode Switcher Dropdown */}
					<div className="relative">
						<button
							type="button"
							onClick={() => setIsViewDropdownOpen((prev) => !prev)}
							className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-border/80 bg-background hover:bg-muted/80 text-foreground transition-all cursor-pointer shadow-2xs"
							title="Chuyển chế độ xem"
						>
							{currentViewMeta.icon}
							<span className="hidden sm:inline">{currentViewMeta.label}</span>
							<ChevronDown className="w-3 h-3 text-muted-foreground" />
						</button>

						{isViewDropdownOpen && (
							<div className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-border bg-popover p-1 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-150">
								<div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
									Chế độ xem Canvas
								</div>
								{VIEW_MODES.map((mode) => (
									<button
										key={mode.id}
										type="button"
										onClick={() => {
											setActiveMode(mode.id);
											setIsViewDropdownOpen(false);
										}}
										className={cn(
											"w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium text-left transition-colors cursor-pointer",
											activeMode === mode.id
												? "bg-muted text-foreground font-semibold"
												: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
										)}
									>
										{mode.icon}
										<span>{mode.label}</span>
									</button>
								))}
							</div>
						)}
					</div>

					{/* Fullscreen Toggle */}
					<button
						type="button"
						onClick={() => setIsFullscreen((prev) => !prev)}
						title={isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}
						className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors cursor-pointer"
					>
						{isFullscreen ? (
							<Minimize2 className="w-3.5 h-3.5" />
						) : (
							<Maximize2 className="w-3.5 h-3.5" />
						)}
					</button>
				</div>
			</header>

			{/* Dynamic Mini-App Body View */}
			<div className="flex-1 overflow-hidden relative">
				{activeMode === "leads" && <OrigamiLeadMatrix {...props} />}

				{activeMode === "research" && <ResearchStudioPanel workspaceId={props.workspaceId} />}

				{activeMode === "automations" && <AutomationBuilderPanel workspaceId={props.workspaceId} />}

				{activeMode === "scrapers" && <ScraperPlatformMonitorPanel />}

				{activeMode === "artifacts" && <ArtifactsStudioPanel />}
			</div>
		</div>
	);
};
