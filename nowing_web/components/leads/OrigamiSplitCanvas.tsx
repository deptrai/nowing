"use client";

import { useAtom } from "jotai";
import { GripVertical, PanelLeftOpen } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
	activeDrawerLeadAtom,
	canvasLeftWidthAtom,
	isLeftPanelCollapsedAtom,
	isMatrixFullscreenAtom,
	selectedLeadContextAtom,
	selectedLeadIdsAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import type { FilterPresets } from "@/contracts/types/leads.types";
import { useLeads } from "@/lib/hooks/use-leads";
import { cn } from "@/lib/utils";
import { CompanyGraphDrawer } from "./CompanyGraphDrawer";
import { DynamicRightPanelCanvas } from "./DynamicRightPanelCanvas";
import { FloatingBulkActionBar } from "./FloatingBulkActionBar";
import { LeadDetailFlyoutDrawer } from "./LeadDetailFlyoutDrawer";
import { OrigamiLeadMatrix } from "./OrigamiLeadMatrix";
import { ReverseIcpModal } from "./ReverseIcpModal";
import { extractLeadsFromChatMessages } from "./lead-parser";

const MIN_LEFT_WIDTH = 360;
const MAX_LEFT_WIDTH = 650;
const DEFAULT_LEFT_WIDTH = 420;

export interface OrigamiSplitCanvasProps {
	workspaceId?: string | number;
	chatSlot?: React.ReactNode;
	hasActiveThread?: boolean;
	messages?: Array<{ role: string; content?: unknown }>;
	className?: string;
}

export const OrigamiSplitCanvas: React.FC<OrigamiSplitCanvasProps> = ({
	workspaceId = "1",
	chatSlot,
	hasActiveThread = false,
	messages = [],
	className,
}) => {
	const [leftWidth, setLeftWidth] = useAtom(canvasLeftWidthAtom);
	const [isCollapsed, setIsCollapsed] = useAtom(isLeftPanelCollapsedAtom);
	const [isFullscreen] = useAtom(isMatrixFullscreenAtom);
	const [selectedLeadIds, setSelectedLeadIds] = useAtom(selectedLeadIdsAtom);
	const [, setSelectedLeadContext] = useAtom(selectedLeadContextAtom);
	const [activeDrawerLead, setActiveDrawerLead] = useAtom(activeDrawerLeadAtom);

	const containerRef = useRef<HTMLElement>(null);
	const [isDragging, setIsDragging] = useState(false);
	const [isReverseIcpOpen, setIsReverseIcpOpen] = useState(false);
	const [selectedCompanyForGraph, setSelectedCompanyForGraph] = useState<string | null>(null);
	const [isGraphDrawerOpen, setIsGraphDrawerOpen] = useState(false);

	// Tabs & Modes
	const [activeTabMode, setActiveTabMode] = useState<"new_search" | "saved">(
		hasActiveThread ? "saved" : "new_search"
	);

	// Filters
	const [sourceFilter, setSourceFilter] = useState("all");
	const [statusFilter, setStatusFilter] = useState("all");
	const [searchQuery, setSearchQuery] = useState("");

	// Cleanup state on workspace switch or unmount
	useEffect(() => {
		setSelectedLeadIds([]);
		setSelectedLeadContext(null);
		setActiveDrawerLead(null);
	}, [setSelectedLeadIds, setSelectedLeadContext, setActiveDrawerLead]);

	// AC-7: Responsive layout & Auto-collapse on small viewport (<1280px)
	useEffect(() => {
		const checkViewport = () => {
			if (window.innerWidth < 1280) {
				setIsCollapsed(true);
			}
		};
		checkViewport();
		window.addEventListener("resize", checkViewport);
		return () => window.removeEventListener("resize", checkViewport);
	}, [setIsCollapsed]);

	// Automatically extract structured leads from live chat messages
	const chatExtractedLeads = useMemo(() => {
		return extractLeadsFromChatMessages(messages || [], workspaceId);
	}, [messages, workspaceId]);

	// Data Fetching
	const {
		leads: apiLeads,
		loading,
		refetch,
	} = useLeads(String(workspaceId), {
		source: sourceFilter !== "all" ? sourceFilter : undefined,
		status: statusFilter !== "all" ? statusFilter : undefined,
		search: searchQuery || undefined,
	});

	// Priority: 1. Live Chat Scraped Leads -> 2. Filtered API Leads -> 3. Clean Empty Canvas on fresh new-chat
	const displayLeads = useMemo(() => {
		if (chatExtractedLeads.length > 0 && sourceFilter === "all" && !searchQuery) {
			return chatExtractedLeads;
		}
		if (activeTabMode === "new_search" && !searchQuery && sourceFilter === "all" && !hasActiveThread) {
			return [];
		}
		return apiLeads || [];
	}, [chatExtractedLeads, activeTabMode, searchQuery, sourceFilter, hasActiveThread, apiLeads]);

	// Dragging logic for resizer
	const handleMouseDown = useCallback((e: React.MouseEvent) => {
		e.preventDefault();
		setIsDragging(true);
	}, []);

	useEffect(() => {
		if (!isDragging) return;

		const handleMouseMove = (e: MouseEvent) => {
			if (!containerRef.current) return;
			const containerRect = containerRef.current.getBoundingClientRect();
			const containerWidth = containerRef.current.clientWidth || 1200;
			const maxAllowedWidth = Math.min(MAX_LEFT_WIDTH, containerWidth - 500);

			const newWidth = Math.max(
				MIN_LEFT_WIDTH,
				Math.min(maxAllowedWidth, e.clientX - containerRect.left)
			);
			setLeftWidth(newWidth);
		};

		const handleMouseUp = () => {
			setIsDragging(false);
		};

		document.addEventListener("mousemove", handleMouseMove);
		document.addEventListener("mouseup", handleMouseUp);
		window.addEventListener("blur", handleMouseUp);

		return () => {
			document.removeEventListener("mousemove", handleMouseMove);
			document.removeEventListener("mouseup", handleMouseUp);
			window.removeEventListener("blur", handleMouseUp);
		};
	}, [isDragging, setLeftWidth]);

	// Double click divider to reset width
	const handleDoubleClickResizer = useCallback(() => {
		setLeftWidth(DEFAULT_LEFT_WIDTH);
	}, [setLeftWidth]);

	// Drawer close callback memoized
	const handleCloseDrawer = useCallback(() => {
		setActiveDrawerLead(null);
	}, [setActiveDrawerLead]);

	// Reverse ICP Callback
	const handleReverseIcpSuccess = (presets: FilterPresets) => {
		if (presets.target_industries && presets.target_industries.length > 0) {
			setSearchQuery(presets.target_industries.join(" "));
		}
		if (presets.platforms && presets.platforms.length > 0) {
			setSourceFilter(presets.platforms[0].toLowerCase());
		}
		toast.success("Đã áp dụng bộ lọc Reverse ICP vào Live Data Matrix!");
	};

	// Company Graph trigger
	const handleOpenCompanyGraph = (companyName: string) => {
		setSelectedCompanyForGraph(companyName);
		setIsGraphDrawerOpen(true);
	};

	// Bulk action handlers
	const handleUnlockPhones = () => {
		toast.success(`Đã gửi yêu cầu mở khóa ${selectedLeadIds.length} SĐT qua hệ thống Waterfall!`);
	};

	const handleExportLarkBase = () => {
		toast.success(`Đang xuất ${selectedLeadIds.length} leads sang Lark Base & CSV...`);
	};

	const handleBulkZalo = () => {
		toast.info(`Kích hoạt chiến dịch tiếp cận Zalo cho ${selectedLeadIds.length} leads.`);
	};

	return (
		<main
			ref={containerRef}
			aria-label="Không gian làm việc Origami Split-View"
			data-testid="origami-split-canvas"
			className={cn(
				"relative w-full h-full flex bg-background text-foreground overflow-hidden",
				isDragging && "select-none cursor-col-resize",
				className
			)}
		>
			{/* Left Panel: Chat Co-pilot */}
			{!isFullscreen && !isCollapsed && (
				<div
					style={{ width: `${leftWidth}px` }}
					className="h-full shrink-0 flex flex-col transition-all duration-75 border-r border-border bg-card overflow-hidden"
				>
					{chatSlot}
				</div>
			)}

			{/* Center Draggable Resizer Divider */}
			{!isFullscreen && !isCollapsed && (
				<div
					role="slider"
					tabIndex={0}
					aria-label="Điều chỉnh kích thước panel"
					aria-valuenow={leftWidth}
					aria-valuemin={MIN_LEFT_WIDTH}
					aria-valuemax={MAX_LEFT_WIDTH}
					data-testid="split-canvas-resizer"
					onMouseDown={handleMouseDown}
					onDoubleClick={handleDoubleClickResizer}
					onKeyDown={(e) => {
						if (e.key === "ArrowLeft") {
							setLeftWidth((w) => Math.max(MIN_LEFT_WIDTH, w - 20));
						} else if (e.key === "ArrowRight") {
							setLeftWidth((w) => Math.min(MAX_LEFT_WIDTH, w + 20));
						}
					}}
					title="Kéo để điều chỉnh kích thước / Nhấp đúp để đặt lại 420px"
					className={cn(
						"relative w-1.5 h-full bg-border hover:bg-emerald-500/80 cursor-col-resize flex items-center justify-center transition-colors z-20 group focus:outline-none focus:ring-1 focus:ring-emerald-500",
						isDragging && "bg-emerald-500 shadow-md shadow-emerald-500/50"
					)}
				>
					<div className="w-4 h-8 rounded-full bg-card border border-border flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-sm">
						<GripVertical className="w-3 h-3 text-muted-foreground" />
					</div>
				</div>
			)}

			{/* Collapsed Expand Trigger */}
			{!isFullscreen && isCollapsed && (
				<button
					type="button"
					onClick={() => setIsCollapsed(false)}
					title="Mở rộng AI Co-pilot"
					className="h-full w-10 bg-card border-r border-border flex flex-col items-center py-4 text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-muted transition-colors cursor-pointer z-20"
				>
					<PanelLeftOpen className="w-5 h-5 mb-2" />
					<span className="[writing-mode:vertical-rl] text-[11px] font-semibold tracking-wider uppercase font-sans">
						AI Co-pilot
					</span>
				</button>
			)}

			{/* Right Panel: Polymorphic Dynamic Mini-App Canvas */}
			<div className="flex-1 h-full min-w-[500px] flex flex-col overflow-hidden">
				<DynamicRightPanelCanvas
					leads={displayLeads}
					isLoading={loading}
					workspaceId={workspaceId}
					sourceFilter={sourceFilter}
					onSourceFilterChange={setSourceFilter}
					statusFilter={statusFilter}
					onStatusFilterChange={setStatusFilter}
					searchQuery={searchQuery}
					onSearchQueryChange={setSearchQuery}
					onRefresh={refetch}
					onOpenReverseIcp={() => setIsReverseIcpOpen(true)}
					onOpenCompanyGraph={handleOpenCompanyGraph}
				/>
			</div>

			{/* Floating Bulk Action Bar */}
			<FloatingBulkActionBar
				selectedCount={selectedLeadIds.length}
				onUnlockPhones={handleUnlockPhones}
				onExportLarkBase={handleExportLarkBase}
				onBulkZalo={handleBulkZalo}
				onClearSelection={() => setSelectedLeadIds([])}
			/>

			{/* Slide-over Detail Flyout Drawer */}
			<LeadDetailFlyoutDrawer
				lead={activeDrawerLead}
				isOpen={activeDrawerLead !== null}
				onClose={handleCloseDrawer}
				workspaceId={workspaceId}
				onOpenCompanyGraph={handleOpenCompanyGraph}
				onReportInvalidPhone={(lead) => {
					toast.info(`Đã mở báo cáo SĐT sai cho lead: ${lead.company_name}`);
				}}
			/>

			{/* Company Graph Modal / Drawer */}
			{selectedCompanyForGraph && (
				<CompanyGraphDrawer
					companyName={selectedCompanyForGraph}
					isOpen={isGraphDrawerOpen}
					onClose={() => {
						setIsGraphDrawerOpen(false);
						setSelectedCompanyForGraph(null);
					}}
					workspaceId={String(workspaceId)}
				/>
			)}

			{/* Reverse ICP Modal */}
			<ReverseIcpModal
				isOpen={isReverseIcpOpen}
				onClose={() => setIsReverseIcpOpen(false)}
				workspaceId={String(workspaceId)}
				onApplyFilterPresets={handleReverseIcpSuccess}
			/>
		</main>
	);
};
