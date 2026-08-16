"use client";

import {
	DndContext,
	type DragEndEvent,
	DragOverlay,
	type DragStartEvent,
	MouseSensor,
	TouchSensor,
	useDraggable,
	useDroppable,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useQuery } from "@rocicorp/zero/react";
import {
	AlertCircle,
	ExternalLink,
	Filter,
	Loader2,
	RefreshCw,
	Sparkles,
	UserCheck,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { LeadPipelineStage } from "@/contracts/types/lead-pipeline.types";
import type { Lead } from "@/contracts/types/leads.types";
import { leadPipelineApiService } from "@/lib/apis/lead-pipeline-api.service";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { queries } from "@/zero/queries";
import { LeadDetailFlyoutDrawer } from "../LeadDetailFlyoutDrawer";
import { PhoneCopyPill } from "../PhoneCopyPill";
import { ZaloOutreachButton } from "../zalo-outreach-button";

export interface LeadKanbanBoardProps {
	workspaceId: string | number;
}

interface LeadCardProps {
	lead: Lead;
	disabled?: boolean;
	isOverlay?: boolean;
	onClick?: () => void;
}

const LeadCardContent: React.FC<LeadCardProps> = ({ lead, disabled, isOverlay, onClick }) => {
	return (
		<div
			data-testid={`lead-card-${lead.id}`}
			className={`p-3 rounded-lg bg-card border border-border hover:border-primary/50 shadow-xs hover:shadow-md transition-all space-y-2.5 text-left ${
				disabled ? "cursor-grabbing" : "cursor-grab active:cursor-grabbing"
			} ${isOverlay ? "opacity-90 rotate-2 shadow-lg" : ""}`}
		>
			<div className="flex items-center justify-between gap-1">
				<span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
					{lead.source}
				</span>
				<div className="flex items-center gap-1">
					{lead.fit_score !== undefined && lead.fit_score !== null && (
						<span className="text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
							<Sparkles className="w-2.5 h-2.5" />
							{lead.fit_score}%
						</span>
					)}
					{onClick ? (
						<button
							type="button"
							className="p-1 rounded bg-muted/60 hover:bg-muted transition-colors"
							onClick={(e) => {
								e.stopPropagation();
								onClick();
							}}
							aria-label="Mở chi tiết lead"
						>
							<ExternalLink className="w-3 h-3 text-muted-foreground" />
						</button>
					) : null}
				</div>
			</div>

			<div className="font-semibold text-xs text-foreground line-clamp-2 leading-snug">
				{lead.company_name}
			</div>

			<div className="flex items-center justify-between gap-1 pt-1">
				{lead.phone ? (
					<PhoneCopyPill phone={lead.phone} />
				) : (
					<span className="text-[10px] text-muted-foreground font-mono">Chưa có SĐT</span>
				)}

				<ZaloOutreachButton
					leadId={lead.id}
					workspaceId={lead.workspace_id}
					phone={lead.phone}
					companyName={lead.company_name}
					intent={lead.intent}
					source={lead.source}
					contentSnippet={lead.content_snippet}
					className="h-6 px-2 text-[10px]"
				/>
			</div>
		</div>
	);
};

const LeadCard: React.FC<LeadCardProps> = (props) => {
	const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
		id: props.lead.id,
		disabled: props.disabled || props.isOverlay,
	});

	const style = transform
		? {
				transform: CSS.Translate.toString(transform),
			}
		: undefined;

	return (
		<div
			ref={setNodeRef}
			{...listeners}
			{...attributes}
			style={style}
			className={`${isDragging ? "opacity-40" : ""}`}
		>
			<LeadCardContent {...props} onClick={props.onClick} />
		</div>
	);
};

const DroppableColumn: React.FC<{
	stage: LeadPipelineStage;
	leads: Lead[];
	disabled?: boolean;
	onCardClick: (lead: Lead) => void;
}> = ({ stage, leads, disabled, onCardClick }) => {
	const { isOver, setNodeRef } = useDroppable({
		id: stage.id,
		disabled,
	});

	return (
		<section
			ref={setNodeRef}
			data-testid={`kanban-column-${stage.slug}`}
			aria-label={stage.name}
			className={`flex-1 min-w-[220px] max-w-[280px] rounded-xl border flex flex-col max-h-[calc(100vh-210px)] ${
				isOver ? "bg-primary/5 border-primary/50" : "bg-muted/30 border-border"
			}`}
		>
			<div className="p-3.5 border-b border-border flex items-center justify-between">
				<div className="flex items-center gap-2 min-w-0">
					<div
						className="w-2.5 h-2.5 rounded-full shrink-0"
						style={{ backgroundColor: stage.color || "#3B82F6" }}
					/>
					<h3 className="text-xs font-bold text-foreground truncate">{stage.name}</h3>
				</div>
				<span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-muted text-muted-foreground border border-border">
					{leads.length}
				</span>
			</div>

			<div className="flex-1 overflow-y-auto p-2.5 space-y-2.5 scrollbar-thin">
				{leads.length === 0 ? (
					<div className="h-24 border border-dashed border-border/80 rounded-lg flex items-center justify-center text-[11px] text-muted-foreground">
						Kéo thả lead vào đây
					</div>
				) : (
					leads.map((lead) => (
						<LeadCard key={lead.id} lead={lead} onClick={() => onCardClick(lead)} />
					))
				)}
			</div>
		</section>
	);
};

export const LeadKanbanBoard: React.FC<LeadKanbanBoardProps> = ({ workspaceId }) => {
	const [stages, setStages] = useState<LeadPipelineStage[]>([]);
	const [leads, setLeads] = useState<Lead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isAssigning, setIsAssigning] = useState(false);
	const [conflictNotice, setConflictNotice] = useState<string | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
	const [isDrawerOpen, setIsDrawerOpen] = useState(false);
	const [activeLead, setActiveLead] = useState<Lead | null>(null);

	const workspaceIdNumber = useMemo(
		() => (typeof workspaceId === "number" ? workspaceId : Number(workspaceId)) || -1,
		[workspaceId]
	);

	const [zeroLeads] = useQuery(queries.leads.bySpace({ workspaceId: workspaceIdNumber }));
	const [zeroStages] = useQuery(
		queries.leadPipelineStages.bySpace({ workspaceId: workspaceIdNumber })
	);
	type ZeroLead = NonNullable<typeof zeroLeads>[number];
	type ZeroStage = NonNullable<typeof zeroStages>[number];

	const mapZeroStage = useCallback((row: ZeroStage): LeadPipelineStage => {
		return {
			id: row.id,
			workspace_id: row.workspaceId,
			client_id: row.clientId ?? null,
			name: row.name,
			slug: row.slug,
			position: row.position,
			color: row.color ?? null,
			is_system: row.isSystem,
			created_at: new Date(row.createdAt).toISOString(),
			updated_at: row.updatedAt ? new Date(row.updatedAt).toISOString() : null,
		};
	}, []);

	const mapZeroLeadFields = useCallback((row: ZeroLead) => {
		return {
			workspace_id: row.workspaceId,
			client_id: row.clientId ?? null,
			source: row.source,
			company_name: row.companyName,
			domain: row.domain ?? null,
			industry: row.industry ?? null,
			company_size: row.companySize ?? null,
			location: row.location ?? null,
			tech_stack: (row.techStack as string[]) ?? [],
			fit_score: row.fitScore ?? null,
			intent_score: row.intentScore ?? null,
			composite_score: row.compositeScore ?? null,
			status: row.status,
			enriched: row.enriched,
			stage_id: row.stageId ?? null,
			assigned_to_user_id: row.assignedToUserId ?? null,
			version: row.version,
			updated_at: row.updatedAt ? new Date(row.updatedAt).toISOString() : null,
		} as const;
	}, []);

	const mapZeroLead = useCallback(
		(row: ZeroLead): Lead =>
			({
				id: row.id,
				...mapZeroLeadFields(row),
				created_at: new Date(row.createdAt).toISOString(),
				phone: undefined,
				intent: undefined,
				content_snippet: undefined,
				source_url: undefined,
				price_estimate: undefined,
				author: undefined,
				contact_name: undefined,
				contact_title: undefined,
				blocked_by_dnc: undefined,
				consent_status: undefined,
				dnc_reason: undefined,
				tax_id: undefined,
				legal_representative: undefined,
				charter_capital_vnd: undefined,
				company_status: undefined,
				is_zalo_active: undefined,
			}) as Lead,
		[mapZeroLeadFields]
	);

	const sensors = useSensors(
		useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
		useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } })
	);

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

	useEffect(() => {
		if (!zeroStages || zeroStages.length === 0) return;
		setStages(zeroStages.map(mapZeroStage));
	}, [zeroStages, mapZeroStage]);

	useEffect(() => {
		if (!zeroLeads) return;
		const liveIds = new Set(zeroLeads.map((l) => l.id));
		setLeads((prev) => {
			const prevIds = new Set(prev.map((l) => l.id));
			const liveById = new Map(zeroLeads.map((l) => [l.id, l] as [string, ZeroLead]));

			const newItems: Lead[] = zeroLeads.filter((l) => !prevIds.has(l.id)).map(mapZeroLead);

			const updated = prev
				.filter((l) => liveIds.has(l.id))
				.map((existing) => {
					const live = liveById.get(existing.id);
					if (!live) return existing;
					return { ...existing, ...mapZeroLeadFields(live) };
				});

			return [...newItems, ...updated];
		});
	}, [zeroLeads, mapZeroLead, mapZeroLeadFields]);

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

	const leadsByStage = useMemo(() => {
		const map: Record<string, Lead[]> = {};
		for (const stage of stages) {
			map[stage.id] = [];
		}
		for (const lead of filteredLeads) {
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

	const handleDragStart = (event: DragStartEvent) => {
		const lead = leads.find((l) => l.id === event.active.id);
		if (lead) setActiveLead(lead);
	};

	const handleDragEnd = async (event: DragEndEvent) => {
		const { active, over } = event;
		setActiveLead(null);

		if (!over) return;
		if (active.id === over.id) return;

		const leadToMove = leads.find((l) => l.id === active.id);
		if (!leadToMove) return;

		const targetStage = stages.find((s) => s.id === over.id);
		if (!targetStage) return;

		if (leadToMove.stage_id === targetStage.id || leadToMove.status === targetStage.slug) return;

		const previousStageId = leadToMove.stage_id;
		const previousStatus = leadToMove.status;
		const expectedVersion = leadToMove.version || 1;

		setLeads((prev) =>
			prev.map((l) =>
				l.id === active.id ? { ...l, stage_id: targetStage.id, status: targetStage.slug } : l
			)
		);

		try {
			const res = await leadPipelineApiService.transitionStage(
				workspaceId,
				leadToMove.id,
				targetStage.id,
				expectedVersion
			);

			setLeads((prev) =>
				prev.map((l) =>
					l.id === active.id
						? { ...l, version: res.version, stage_id: res.stage_id, status: res.status }
						: l
				)
			);
		} catch (err: unknown) {
			console.warn("OCC stage transition failed, rolling back", err);
			setLeads((prev) =>
				prev.map((l) =>
					l.id === active.id ? { ...l, stage_id: previousStageId, status: previousStatus } : l
				)
			);

			const is409 =
				typeof err === "object" &&
				err !== null &&
				("status" in err || "response" in err) &&
				((err as { status?: number }).status === 409 ||
					(err as { response?: { status?: number } }).response?.status === 409);

			if (is409 && typeof err === "object" && err !== null) {
				const data = (
					err as { response?: { data?: { current_version?: number; current_stage_id?: string } } }
				).response?.data;
				if (data?.current_version && data?.current_stage_id) {
					setLeads((prev) =>
						prev.map((l) =>
							l.id === active.id
								? {
										...l,
										version: data.current_version ?? l.version,
										stage_id: data.current_stage_id ?? l.stage_id,
									}
								: l
						)
					);
				}
			}

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

			<DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
				<div className="flex-1 overflow-x-auto pb-4">
					<div className="flex gap-4 min-w-[1000px] h-full items-start">
						{stages.map((stage) => (
							<DroppableColumn
								key={stage.id}
								stage={stage}
								leads={leadsByStage[stage.id] || []}
								disabled={isLoading}
								onCardClick={(lead) => {
									setSelectedLead(lead);
									setIsDrawerOpen(true);
								}}
							/>
						))}
					</div>
				</div>

				<DragOverlay dropAnimation={null}>
					{activeLead ? <LeadCardContent lead={activeLead} disabled isOverlay /> : null}
				</DragOverlay>
			</DndContext>

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
