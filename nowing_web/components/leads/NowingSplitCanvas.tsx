"use client";

import { useAtom, useAtomValue } from "jotai";
import { GripVertical, MessageSquare, Table } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { dockExpandedAtom, dockOpenAtom } from "@/atoms/layout/dock.atom";
import {
	activeDrawerLeadAtom,
	canvasLeftWidthAtom,
	isLeftPanelCollapsedAtom,
	isMatrixFullscreenAtom,
	selectedLeadContextAtom,
	selectedLeadIdsAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import type { FilterPresets, Lead } from "@/contracts/types/leads.types";
import { ContextualDock } from "@/features/dock";
import { useSidebarContextSafe } from "@/components/layout/hooks";
import { useIsMobile } from "@/hooks/use-mobile";
import { useDshMissionControl } from "@/lib/hooks/use-dsh-mission-control";
import { useLeads } from "@/lib/hooks/use-leads";
import { cn } from "@/lib/utils";
import { CompanyGraphDrawer } from "./CompanyGraphDrawer";
import { DncManagementModal } from "./DncManagementModal";
import { DynamicRightPanelCanvas } from "./DynamicRightPanelCanvas";
import { FloatingBulkActionBar } from "./FloatingBulkActionBar";
import { LeadDetailFlyoutDrawer } from "./LeadDetailFlyoutDrawer";
import { ReverseIcpModal } from "./ReverseIcpModal";
import { parseThreadContext } from "./thread-intent-detector";

const MIN_LEFT_WIDTH = 280;
const MAX_LEFT_WIDTH = 500;
const DEFAULT_LEFT_WIDTH = 340;

export interface NowingSplitCanvasProps {
	workspaceId?: string | number;
	threadId?: string | number | null;
	chatSlot?: React.ReactNode;
	hasActiveThread?: boolean;
	messages?: Array<{ role: string; content?: unknown }>;
	onSendPrompt?: (prompt: string) => void;
	className?: string;
}

export const NowingSplitCanvas: React.FC<NowingSplitCanvasProps> = ({
	workspaceId = "1",
	threadId,
	chatSlot,
	hasActiveThread = false,
	messages = [],
	onSendPrompt: _onSendPrompt,
	className,
}) => {
	const isMobile = useIsMobile();
	const [leftWidth, setLeftWidth] = useAtom(canvasLeftWidthAtom);
	const [isCollapsed, setIsCollapsed] = useAtom(isLeftPanelCollapsedAtom);
	const isDockOpen = useAtomValue(dockOpenAtom);
	const isDockExpanded = useAtomValue(dockExpandedAtom);
	const [preExpandLeftWidth, setPreExpandLeftWidth] = useState<number | null>(null);
	const [preExpandSidebarCollapsed, setPreExpandSidebarCollapsed] = useState<boolean | null>(null);
	const sidebarContext = useSidebarContextSafe();
	const [isFullscreen] = useAtom(isMatrixFullscreenAtom);
	const [selectedLeadIds, setSelectedLeadIds] = useAtom(selectedLeadIdsAtom);
	const [, setSelectedLeadContext] = useAtom(selectedLeadContextAtom);
	const [activeDrawerLead, setActiveDrawerLead] = useAtom(activeDrawerLeadAtom);

	const containerRef = useRef<HTMLElement>(null);
	const [isDragging, setIsDragging] = useState(false);
	const [isReverseIcpOpen, setIsReverseIcpOpen] = useState(false);
	const [isDncOpen, setIsDncOpen] = useState(false);
	const [selectedCompanyForGraph, setSelectedCompanyForGraph] = useState<string | null>(null);
	const [isGraphDrawerOpen, setIsGraphDrawerOpen] = useState(false);
	const [mobileActiveTab, setMobileActiveTab] = useState<"chat" | "matrix">("chat");
	const [unlockedPhones, setUnlockedPhones] = useState<Record<string, string | null>>({});

	const handlePhoneChange = useCallback(
		(leadId: string, phone: string | null, _unlocked: boolean) => {
			setUnlockedPhones((prev) => {
				const next = { ...prev };
				if (phone == null) {
					delete next[leadId];
				} else {
					next[leadId] = phone;
				}
				return next;
			});
		},
		[]
	);

	// Tabs & Modes
	const [_activeTabMode, _setActiveTabMode] = useState<"new_search" | "saved">(
		hasActiveThread ? "saved" : "new_search"
	);

	// Filters
	const [sourceFilter, setSourceFilter] = useState("all");
	const [statusFilter, setStatusFilter] = useState("all");
	const [searchQuery, setSearchQuery] = useState("");

	// When the dock is expanded, collapse the outer sidebar and the left chat
	// panel to their minimums so the right dock can take up the whole workspace.
	// Restore previous sizes when collapsing the dock again.
	useEffect(() => {
		if (isDockOpen && isDockExpanded) {
			if (preExpandLeftWidth === null) {
				setPreExpandLeftWidth(leftWidth);
			}
			if (preExpandSidebarCollapsed === null && sidebarContext) {
				setPreExpandSidebarCollapsed(sidebarContext.isCollapsed);
				sidebarContext.setIsCollapsed(true);
			}
			setLeftWidth(0);
		} else if (!isDockExpanded && preExpandLeftWidth !== null) {
			setLeftWidth(preExpandLeftWidth);
			setPreExpandLeftWidth(null);
			if (preExpandSidebarCollapsed !== null && sidebarContext) {
				sidebarContext.setIsCollapsed(preExpandSidebarCollapsed);
				setPreExpandSidebarCollapsed(null);
			}
		}
	}, [
		isDockOpen,
		isDockExpanded,
		leftWidth,
		preExpandLeftWidth,
		preExpandSidebarCollapsed,
		sidebarContext,
		setLeftWidth,
	]);

	// Cleanup state on workspace switch or unmount
	useEffect(() => {
		setSelectedLeadIds([]);
		setSelectedLeadContext(null);
		setActiveDrawerLead(null);
		setIsCollapsed(false);
		setPreExpandLeftWidth(null);
		setPreExpandSidebarCollapsed(null);
	}, [setSelectedLeadIds, setSelectedLeadContext, setActiveDrawerLead, setIsCollapsed]);

	// Session-Scoped context parser: derives intent, leads, research, and workflows strictly for THIS thread
	const threadContext = useMemo(() => {
		return parseThreadContext(messages || [], threadId || "default", workspaceId);
	}, [messages, threadId, workspaceId]);

	// Data Fetching (for live status updates and refresh)
	const {
		leads: apiLeads,
		loading,
		refetch,
	} = useLeads(String(workspaceId), {
		source: sourceFilter !== "all" ? sourceFilter : undefined,
		status: statusFilter !== "all" ? statusFilter : undefined,
		search: searchQuery || undefined,
	});

	// Merged display leads: prioritize live parsed leads from current thread;
	// fall back to the API list when no chat thread is active so the Leads tab
	// still shows workspace leads.
	const displayLeads = useMemo(() => {
		if (threadContext.leads && threadContext.leads.length > 0) {
			return threadContext.leads;
		}
		return apiLeads;
	}, [threadContext.leads, apiLeads]);

	const selectedLeads = useMemo(() => {
		return displayLeads.filter((lead) => selectedLeadIds.includes(lead.id));
	}, [displayLeads, selectedLeadIds]);

	const {
		missionControl,
		latestMission,
		loading: missionLoading,
		error: missionError,
	} = useDshMissionControl(workspaceId);
	const shimmerCount = useMemo(() => {
		const phase = (missionControl?.phase ?? latestMission?.phase)?.toLowerCase();
		return phase && (phase === "ingestion" || phase === "ingest") ? 2 : 0;
	}, [missionControl, latestMission]);

	// Keep the flyout lead in sync when the list refreshes (e.g. after phone unlock)
	useEffect(() => {
		if (!activeDrawerLead) return;
		const updated = displayLeads.find((l) => l.id === activeDrawerLead.id);
		if (!updated) return;

		const phoneOverride = unlockedPhones[updated.id];
		const isUnlocked = Boolean(phoneOverride) || updated.is_unlocked;
		const newLead: Lead = {
			...updated,
			phone: phoneOverride ?? updated.phone,
			is_unlocked: isUnlocked,
		};
		if (
			newLead.is_unlocked !== activeDrawerLead.is_unlocked ||
			newLead.phone !== activeDrawerLead.phone
		) {
			setActiveDrawerLead(newLead);
		}
	}, [displayLeads, activeDrawerLead, unlockedPhones, setActiveDrawerLead]);

	// Resizing Handlers (Mouse Dragging)
	const handleMouseDown = useCallback((e: React.MouseEvent) => {
		e.preventDefault();
		setIsDragging(true);
	}, []);

	useEffect(() => {
		if (!isDragging) return;

		const handleMouseMove = (e: MouseEvent) => {
			if (!containerRef.current) return;
			const containerRect = containerRef.current.getBoundingClientRect();
			const newWidth = e.clientX - containerRect.left;
			const clamped = Math.min(Math.max(newWidth, MIN_LEFT_WIDTH), MAX_LEFT_WIDTH);
			setLeftWidth(clamped);
		};

		const handleMouseUp = () => {
			setIsDragging(false);
		};

		document.addEventListener("mousemove", handleMouseMove);
		document.addEventListener("mouseup", handleMouseUp);

		return () => {
			document.removeEventListener("mousemove", handleMouseMove);
			document.removeEventListener("mouseup", handleMouseUp);
		};
	}, [isDragging, setLeftWidth]);

	// Double-click resizer to reset to default 340px width
	const handleDoubleClickResizer = () => {
		setLeftWidth(DEFAULT_LEFT_WIDTH);
	};

	// Modal / Drawer interactions
	const handleCloseDrawer = () => {
		setActiveDrawerLead(null);
	};

	const handleReverseIcpSuccess = (presets: FilterPresets) => {
		setIsReverseIcpOpen(false);
		if (presets.min_fit_score) {
			toast.success(`Đã kích hoạt bộ lọc ICP: Fit Score > ${presets.min_fit_score}`);
		}
	};

	const handleOpenCompanyGraph = (companyName: string) => {
		setSelectedCompanyForGraph(companyName);
		setIsGraphDrawerOpen(true);
	};

	// Bulk action handlers

	const handleExportLarkBase = () => {
		toast.success(`Đang xuất ${selectedLeadIds.length} leads sang Lark Base & CSV...`);
	};

	const handleBulkZalo = () => {
		toast.info(`Kích hoạt chiến dịch tiếp cận Zalo cho ${selectedLeadIds.length} leads.`);
	};

	// Mobile layout (< 768px): Tabbed switcher between Chat and Dynamic Canvas
	if (isMobile && hasActiveThread) {
		return (
			<main
				ref={containerRef}
				aria-label="Không gian làm việc Nowing Mobile"
				data-testid="nowing-split-canvas-mobile"
				className={cn(
					"relative w-full h-full flex flex-col bg-background text-foreground overflow-hidden",
					className
				)}
			>
				{/* Mobile Tab Switcher */}
				<div className="h-10 px-3 bg-muted/40 border-b border-border/80 flex items-center justify-between shrink-0">
					<div className="flex items-center gap-1 bg-background/80 p-0.5 rounded-lg border border-border/80 text-xs font-medium">
						<button
							type="button"
							onClick={() => setMobileActiveTab("chat")}
							className={cn(
								"flex items-center gap-1.5 px-3 py-1 rounded-md transition-all",
								mobileActiveTab === "chat"
									? "bg-card text-foreground shadow-2xs font-semibold"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							<MessageSquare className="w-3.5 h-3.5" aria-hidden="true" />
							<span>Trò chuyện AI</span>
						</button>
						<button
							type="button"
							onClick={() => setMobileActiveTab("matrix")}
							className={cn(
								"flex items-center gap-1.5 px-3 py-1 rounded-md transition-all",
								mobileActiveTab === "matrix"
									? "bg-emerald-500 text-white shadow-2xs font-semibold"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							<Table className="w-3.5 h-3.5" aria-hidden="true" />
							<span>Bảng Leads ({displayLeads.length})</span>
						</button>
					</div>
				</div>

				{/* Mobile Tab Content */}
				<div className="flex-1 overflow-hidden relative">
					{mobileActiveTab === "chat" ? (
						<div className="w-full h-full overflow-hidden">{chatSlot}</div>
					) : (
						<div className="w-full h-full overflow-hidden">
							<DynamicRightPanelCanvas
								threadId={threadId ?? undefined}
								threadContext={threadContext}
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
								shimmerCount={shimmerCount}
								onOpenDnc={() => setIsDncOpen(true)}
								missionControl={missionControl}
								latestMission={latestMission}
								missionLoading={missionLoading}
								missionError={missionError}
								onOpenCompanyGraph={handleOpenCompanyGraph}
								unlockedPhones={unlockedPhones}
								onPhoneChange={handlePhoneChange}
							/>
						</div>
					)}
				</div>

				{/* Mobile contextual dock bottom sheet */}
				<ContextualDock
					workspaceId={workspaceId}
					threadId={threadId}
					messages={messages}
					leads={displayLeads}
					isLoading={loading}
					threadContext={threadContext}
					sourceFilter={sourceFilter}
					onSourceFilterChange={setSourceFilter}
					statusFilter={statusFilter}
					onStatusFilterChange={setStatusFilter}
					searchQuery={searchQuery}
					onSearchQueryChange={setSearchQuery}
					onRefresh={refetch}
					onOpenReverseIcp={() => setIsReverseIcpOpen(true)}
					onOpenDnc={() => setIsDncOpen(true)}
					onOpenCompanyGraph={handleOpenCompanyGraph}
					shimmerCount={shimmerCount}
					unlockedPhones={unlockedPhones}
					onPhoneChange={handlePhoneChange}
					missionControl={missionControl}
					latestMission={latestMission}
					missionLoading={missionLoading}
					missionError={missionError}
				/>

				{/* Floating Bulk Action Bar */}
				{selectedLeadIds.length > 0 && (
					<FloatingBulkActionBar
						selectedCount={selectedLeadIds.length}
						selectedLeads={selectedLeads}
						workspaceId={workspaceId}
						onExportLarkBase={handleExportLarkBase}
						onBulkZalo={handleBulkZalo}
						onClearSelection={() => setSelectedLeadIds([])}
						unlockedPhones={unlockedPhones}
						onPhoneChange={handlePhoneChange}
					/>
				)}

				{/* Lead Detail Flyout Drawer */}
				<LeadDetailFlyoutDrawer
					lead={activeDrawerLead}
					isOpen={Boolean(activeDrawerLead)}
					onClose={() => setActiveDrawerLead(null)}
					workspaceId={String(workspaceId)}
					unlockedPhone={activeDrawerLead ? unlockedPhones[activeDrawerLead.id] : undefined}
					onPhoneChange={handlePhoneChange}
				/>

				{/* 1-Click Reverse-ICP Modal */}
				<ReverseIcpModal
					isOpen={isReverseIcpOpen}
					onClose={() => setIsReverseIcpOpen(false)}
					workspaceId={String(workspaceId)}
				/>

				{/* Do-Not-Call (DNC) Management Modal */}
				<DncManagementModal
					isOpen={isDncOpen}
					onClose={() => setIsDncOpen(false)}
					workspaceId={String(workspaceId)}
				/>

				{/* Interactive 3D Company Graph Drawer */}
				<CompanyGraphDrawer
					companyName={selectedCompanyForGraph ?? ""}
					isOpen={isGraphDrawerOpen}
					workspaceId={String(workspaceId)}
					onClose={() => {
						setIsGraphDrawerOpen(false);
						setSelectedCompanyForGraph(null);
					}}
				/>
			</main>
		);
	}

	// Unified Animated Split Canvas (Morphing from 100% full-width to 340px Split-View)
	return (
		<main
			ref={containerRef}
			aria-label="Không gian làm việc Nowing Split-View"
			data-testid="nowing-split-canvas"
			className={cn(
				"relative w-full h-full flex bg-background text-foreground overflow-hidden",
				isDragging && "select-none cursor-col-resize",
				className
			)}
		>
			{/* Left Panel: Chat Co-pilot */}
			{!isFullscreen && !isCollapsed && (
				<div
					style={{
						width: hasActiveThread && isDockOpen ? `${leftWidth}px` : "100%",
					}}
					className={cn(
						"h-full shrink-0 flex flex-col transition-[width] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] bg-card overflow-hidden z-10",
						hasActiveThread && isDockOpen ? "border-r border-border/80" : "w-full"
					)}
				>
					{chatSlot}
				</div>
			)}

			{/* Center Draggable Resizer Divider */}
			{hasActiveThread && !isFullscreen && !isCollapsed && isDockOpen && (
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
					title="Kéo để điều chỉnh kích thước / Nhấp đúp để đặt lại 340px"
					className={cn(
						"relative w-1.5 h-full bg-border hover:bg-emerald-500/80 cursor-col-resize flex items-center justify-center transition-colors z-20 group focus:outline-none focus:ring-1 focus:ring-emerald-500",
						isDragging && "bg-emerald-500 shadow-md shadow-emerald-500/50"
					)}
				>
					<div className="w-4 h-8 rounded-full bg-card border border-border flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-sm">
						<GripVertical className="w-3 h-3 text-muted-foreground" aria-hidden="true" />
					</div>
				</div>
			)}

			{/* Right Panel: Contextual Dock */}
			{hasActiveThread && (
				<ContextualDock
					workspaceId={workspaceId}
					threadId={threadId}
					messages={messages}
					leads={displayLeads}
					isLoading={loading}
					threadContext={threadContext}
					sourceFilter={sourceFilter}
					onSourceFilterChange={setSourceFilter}
					statusFilter={statusFilter}
					onStatusFilterChange={setStatusFilter}
					searchQuery={searchQuery}
					onSearchQueryChange={setSearchQuery}
					onRefresh={refetch}
					onOpenReverseIcp={() => setIsReverseIcpOpen(true)}
					onOpenDnc={() => setIsDncOpen(true)}
					shimmerCount={shimmerCount}
					onOpenCompanyGraph={handleOpenCompanyGraph}
					unlockedPhones={unlockedPhones}
					onPhoneChange={handlePhoneChange}
					missionControl={missionControl}
					latestMission={latestMission}
					missionLoading={missionLoading}
					missionError={missionError}
				/>
			)}

			{/* Floating Bulk Action Bar */}
			{hasActiveThread && selectedLeadIds.length > 0 && (
				<FloatingBulkActionBar
					selectedCount={selectedLeadIds.length}
					selectedLeads={selectedLeads}
					workspaceId={workspaceId}
					onExportLarkBase={handleExportLarkBase}
					onBulkZalo={handleBulkZalo}
					onClearSelection={() => setSelectedLeadIds([])}
					unlockedPhones={unlockedPhones}
					onPhoneChange={handlePhoneChange}
				/>
			)}

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
				unlockedPhone={activeDrawerLead ? unlockedPhones[activeDrawerLead.id] : undefined}
				onPhoneChange={handlePhoneChange}
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

			{/* DNC & Compliance Modal */}
			<DncManagementModal
				isOpen={isDncOpen}
				onClose={() => setIsDncOpen(false)}
				workspaceId={String(workspaceId)}
			/>
		</main>
	);
};
