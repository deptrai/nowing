"use client";

import { AlertCircle, Filter, Loader2, RefreshCw, Sparkles, UserCheck } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { LeadPipelineStage } from "@/contracts/types/lead-pipeline.types";
import type { Lead } from "@/contracts/types/leads.types";
import { leadPipelineApiService } from "@/lib/apis/lead-pipeline-api.service";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { LeadDetailFlyoutDrawer } from "../LeadDetailFlyoutDrawer";
import { PhoneCopyPill } from "../PhoneCopyPill";
import { ZaloOutreachButton } from "../zalo-outreach-button";

export interface LeadKanbanBoardProps {
	workspaceId: string | number;
}

export const LeadKanbanBoard: React.FC<LeadKanbanBoardProps> = ({ workspaceId }) => {
	const [stages, setStages] = useState<LeadPipelineStage[]>([]);
	const [leads, setLeads] = useState<Lead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isAssigning, setIsAssigning] = useState(false);
	const [conflictNotice, setConflictNotice] = useState<string | null>(null);

	const [searchQuery, setSearchQuery] = useState("");
	const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
	const [isDrawerOpen, setIsDrawerOpen] = useState(false);
	const [draggedLeadId, setDraggedLeadId] = useState<string | null>(null);

	// Fetch stages & leads
	const loadData = useCallback(async () => {
		try {
			setIsLoading(true);
			const [fetchedStages, leadListRes] = await Promise.all([
				leadPipelineApiService.listStages(workspaceId),
				leadsApiService.listLeads(workspaceId, { limit: 200 }),
			]);
			setStages(fetchedStages || []);
			setLeads(leadListRes.items || []);
		} catch (err) {
			console.error("Failed to load pipeline data", err);
		} finally {
			setIsLoading(false);
		}
	}, [workspaceId]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	// Filter leads by search query
	const filteredLeads = useMemo(() => {
		if (!searchQuery.trim()) return leads;
		const q = searchQuery.toLowerCase();
		return leads.filter(
			(l) =>
				l.company_name?.toLowerCase().includes(q) ||
				l.source?.toLowerCase().includes(q) ||
				l.phone?.includes(q) ||
				l.industry?.toLowerCase().includes(q)
		);
	}, [leads, searchQuery]);

	// Group leads by stage slug or stage_id
	const leadsByStage = useMemo(() => {
		const map: Record<string, Lead[]> = {};
		for (const stage of stages) {
			map[stage.id] = [];
		}

		for (const lead of filteredLeads) {
			// Find matching stage by stage_id or status
			const matchingStage =
				stages.find((s) => s.id === lead.stage_id) ||
				stages.find((s) => s.slug === lead.status) ||
				stages[0];

			if (matchingStage) {
				if (!map[matchingStage.id]) {
					map[matchingStage.id] = [];
				}
				map[matchingStage.id].push(lead);
			}
		}
		return map;
	}, [stages, filteredLeads]);

	// Handle Drag & Drop with OCC
	const handleDragStart = (leadId: string) => {
		setDraggedLeadId(leadId);
	};

	const handleDragOver = (e: React.DragEvent) => {
		e.preventDefault();
	};

	const handleDrop = async (targetStageId: string) => {
		if (!draggedLeadId) return;
		const leadToMove = leads.find((l) => l.id === draggedLeadId);
		if (!leadToMove) return;

		const targetStage = stages.find((s) => s.id === targetStageId);
		if (!targetStage) return;

		// If dropped into the same stage, do nothing
		if (leadToMove.stage_id === targetStageId || leadToMove.status === targetStage.slug) {
			setDraggedLeadId(null);
			return;
		}

		const previousStageId = leadToMove.stage_id;
		const previousStatus = leadToMove.status;
		const expectedVersion = leadToMove.version || 1;

		// 1. Optimistic Update in UI
		setLeads((prev) =>
			prev.map((l) =>
				l.id === draggedLeadId ? { ...l, stage_id: targetStageId, status: targetStage.slug } : l
			)
		);
		setDraggedLeadId(null);

		// 2. Call backend OCC API
		try {
			const res = await leadPipelineApiService.transitionStage(
				workspaceId,
				draggedLeadId,
				targetStageId,
				expectedVersion
			);

			// Update lead version with new version from server
			setLeads((prev) =>
				prev.map((l) =>
					l.id === draggedLeadId
						? { ...l, version: res.version, stage_id: res.stage_id, status: res.status }
						: l
				)
			);
		} catch (err: unknown) {
			// Rollback on error / 409 Conflict
			console.warn("OCC stage transition failed, rolling back", err);
			setLeads((prev) =>
				prev.map((l) =>
					l.id === draggedLeadId ? { ...l, stage_id: previousStageId, status: previousStatus } : l
				)
			);

			const is409 =
				typeof err === "object" &&
				err !== null &&
				("status" in err || "response" in err) &&
				((err as { status?: number }).status === 409 ||
					(err as { response?: { status?: number } }).response?.status === 409);
			setConflictNotice(
				is409
					? `Xung đột đồng thời (OCC): Lead "${leadToMove.company_name}" vừa được chỉnh sửa bởi thành viên khác. Đã tự động hoàn tác để đảm bảo toàn vẹn dữ liệu.`
					: `Lỗi khi chuyển trạng thái lead "${leadToMove.company_name}". Đã hoàn tác.`
			);

			setTimeout(() => {
				setConflictNotice(null);
			}, 6000);
		}
	};

	// Trigger Batch Round-Robin Assignment
	const handleBatchAutoAssign = async () => {
		const unassigned = leads.filter((l) => !l.assigned_to_user_id).map((l) => l.id);
		if (unassigned.length === 0) return;

		try {
			setIsAssigning(true);
			await leadPipelineApiService.batchAssignLeads(workspaceId, unassigned);
			await loadData();
		} catch (err) {
			console.error("Batch assignment failed", err);
		} finally {
			setIsAssigning(false);
		}
	};

	return (
		<div className="flex flex-col h-full space-y-4">
			{/* Top Control Bar */}
			<div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-card border border-border">
				<div className="flex items-center gap-3 flex-1 min-w-[240px] max-w-md">
					<div className="relative w-full">
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Tìm kiếm công ty, nguồn, SĐT..."
							className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg bg-muted/40 border border-border text-foreground placeholder:text-muted-foreground focus:outline-hidden focus:ring-1 focus:ring-primary"
						/>
						<Filter className="w-3.5 h-3.5 absolute left-3 top-2.5 text-muted-foreground" />
					</div>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={handleBatchAutoAssign}
						disabled={isAssigning || isLoading}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-xs cursor-pointer"
					>
						{isAssigning ? (
							<Loader2 className="w-3.5 h-3.5 animate-spin" />
						) : (
							<UserCheck className="w-3.5 h-3.5" />
						)}
						Phân bổ Round-Robin
					</button>

					<button
						type="button"
						onClick={loadData}
						disabled={isLoading}
						className="p-2 rounded-lg bg-muted hover:bg-muted/80 text-foreground transition-colors cursor-pointer border border-border"
						title="Làm mới bảng"
					>
						<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
					</button>
				</div>
			</div>

			{/* OCC Conflict Alert Banner */}
			{conflictNotice && (
				<div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center justify-between gap-3 animate-in fade-in duration-200">
					<div className="flex items-center gap-2">
						<AlertCircle className="w-4 h-4 shrink-0" />
						<span>{conflictNotice}</span>
					</div>
					<button
						type="button"
						onClick={() => setConflictNotice(null)}
						className="text-xs font-semibold hover:underline cursor-pointer"
					>
						Đóng
					</button>
				</div>
			)}

			{/* Kanban Board Columns Container */}
			<div className="flex-1 overflow-x-auto pb-4">
				<div className="flex gap-4 min-w-[1000px] h-full items-start">
					{stages.map((stage) => {
						const stageLeads = leadsByStage[stage.id] || [];

						return (
							<section
								key={stage.id}
								aria-label={stage.name}
								onDragOver={handleDragOver}
								onDrop={() => handleDrop(stage.id)}
								className="flex-1 min-w-[220px] max-w-[280px] rounded-xl bg-muted/30 border border-border flex flex-col max-h-[calc(100vh-210px)]"
							>
								{/* Column Header */}
								<div className="p-3.5 border-b border-border flex items-center justify-between">
									<div className="flex items-center gap-2 min-w-0">
										<div
											className="w-2.5 h-2.5 rounded-full shrink-0"
											style={{ backgroundColor: stage.color || "#3B82F6" }}
										/>
										<h3 className="text-xs font-bold text-foreground truncate">{stage.name}</h3>
									</div>
									<span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-muted text-muted-foreground border border-border">
										{stageLeads.length}
									</span>
								</div>

								{/* Cards Area */}
								<div className="flex-1 overflow-y-auto p-2.5 space-y-2.5 scrollbar-thin">
									{stageLeads.length === 0 ? (
										<div className="h-24 border border-dashed border-border/80 rounded-lg flex items-center justify-center text-[11px] text-muted-foreground">
											Kéo thả lead vào đây
										</div>
									) : (
										stageLeads.map((lead) => (
											<article
												key={lead.id}
												draggable
												onDragStart={() => handleDragStart(lead.id)}
												onClick={() => {
													setSelectedLead(lead);
													setIsDrawerOpen(true);
												}}
												onKeyDown={(e) => {
													if (e.key === "Enter" || e.key === " ") {
														e.preventDefault();
														setSelectedLead(lead);
														setIsDrawerOpen(true);
													}
												}}
												className={`p-3 rounded-lg bg-card border border-border hover:border-primary/50 shadow-xs hover:shadow-md transition-all cursor-grab active:cursor-grabbing space-y-2.5 text-left ${
													draggedLeadId === lead.id ? "opacity-40" : ""
												}`}
											>
												{/* Card Header: Source & Fit Score */}
												<div className="flex items-center justify-between gap-1">
													<span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
														{lead.source}
													</span>
													{lead.fit_score !== undefined && lead.fit_score !== null && (
														<span className="text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
															<Sparkles className="w-2.5 h-2.5" />
															{lead.fit_score}%
														</span>
													)}
												</div>

												{/* Company Name */}
												<div className="font-semibold text-xs text-foreground line-clamp-2 leading-snug">
													{lead.company_name}
												</div>

												{/* Phone & Outreach */}
												<div className="flex items-center justify-between gap-1 pt-1">
													{lead.phone ? (
														<PhoneCopyPill phone={lead.phone} />
													) : (
														<span className="text-[10px] text-muted-foreground font-mono">
															Chưa có SĐT
														</span>
													)}

													<ZaloOutreachButton
														leadId={lead.id}
														workspaceId={workspaceId}
														phone={lead.phone}
														companyName={lead.company_name}
														intent={lead.intent}
														source={lead.source}
														contentSnippet={lead.content_snippet}
														className="h-6 px-2 text-[10px]"
													/>
												</div>
											</article>
										))
									)}
								</div>
							</section>
						);
					})}
				</div>
			</div>

			{/* Detail Drawer */}
			<LeadDetailFlyoutDrawer
				lead={selectedLead}
				isOpen={isDrawerOpen}
				onClose={() => {
					setIsDrawerOpen(false);
					setSelectedLead(null);
				}}
				workspaceId={workspaceId}
			/>
		</div>
	);
};
