"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtom } from "jotai";
import {
	Activity,
	AlertTriangle,
	ChevronDown,
	ChevronUp,
	Globe,
	Loader2,
	MapPin,
	RefreshCw,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { activeCampaignPlanAtom, activePlanSpecAtom } from "@/atoms/leads/leads-canvas.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import type { SourcePlanAllocation } from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn } from "@/lib/utils";
import { SourceCoverageBadge } from "../SourceCoverageBadge";

export interface SourceStatusPanelProps {
	workspaceId?: string | number;
	className?: string;
	onOpenPlanBuilder?: () => void;
}

export const SourceStatusPanel: React.FC<SourceStatusPanelProps> = ({
	workspaceId = 1,
	className,
	onOpenPlanBuilder,
}) => {
	const [activePlan, setActivePlan] = useAtom(activeCampaignPlanAtom);
	const [activeSpec, setActivePlanSpec] = useAtom(activePlanSpecAtom);
	const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
	const [isReplanning, setIsReplanning] = useState(false);

	// Extract active location parameters if active plan exists
	const provinceCode = activeSpec?.icp_config?.location_profile?.province_code;
	const districtCodes = useMemo(
		() => activeSpec?.icp_config?.location_profile?.district_codes ?? [],
		[activeSpec?.icp_config?.location_profile?.district_codes]
	);

	// Fetch global idle sources status if activePlan is null or for background refresh
	const {
		data: globalSources = [],
		isLoading: isLoadingGlobal,
		refetch: refetchGlobal,
		isRefetching,
	} = useQuery({
		queryKey: ["campaign-sources-status", workspaceId, provinceCode, districtCodes],
		queryFn: () =>
			leadsApiService.getSourceStatuses(workspaceId, {
				province_code: provinceCode,
				district_codes: districtCodes,
			}),
		staleTime: 60_000,
	});

	// Effective display sources: use active plan allocations if available, otherwise global statuses
	const displaySources: SourcePlanAllocation[] =
		activePlan?.source_allocations && activePlan.source_allocations.length > 0
			? activePlan.source_allocations
			: globalSources;

	// Set of currently selected sources in spec
	const currentSelectedSources: string[] =
		activeSpec?.source_budget_config?.sources ??
		activePlan?.expected_sources ??
		displaySources.map((s) => s.source_name);

	const toggleExpand = (sourceName: string) => {
		setExpandedSources((prev) => {
			const next = new Set(prev);
			if (next.has(sourceName)) next.delete(sourceName);
			else next.add(sourceName);
			return next;
		});
	};

	const handleToggleSource = async (sourceName: string, enabled: boolean) => {
		if (!activeSpec) {
			toast.info("Tạo một kế hoạch tìm kiếm để tinh chỉnh từng nguồn cào dữ liệu.");
			onOpenPlanBuilder?.();
			return;
		}

		const currentSources = activeSpec.source_budget_config.sources;
		if (!enabled && currentSources.includes(sourceName)) {
			// AC-2 Safety Guard: Minimum 1 active source
			if (currentSources.length <= 1) {
				toast.warning("Phải giữ lại ít nhất 1 nguồn thu thập dữ liệu.");
				return;
			}
			const nextSources = currentSources.filter((s) => s !== sourceName);
			await applyUpdatedSources(nextSources);
		} else if (enabled && !currentSources.includes(sourceName)) {
			const nextSources = [...currentSources, sourceName];
			await applyUpdatedSources(nextSources);
		}
	};

	const applyUpdatedSources = async (updatedSources: string[]) => {
		if (!activeSpec) return;

		const updatedSpec = {
			...activeSpec,
			source_budget_config: {
				...activeSpec.source_budget_config,
				sources: updatedSources,
			},
		};

		// Optimistically update activePlanSpecAtom
		setActivePlanSpec(updatedSpec);

		try {
			setIsReplanning(true);
			const replanned = await leadsApiService.planCampaign(workspaceId, updatedSpec);
			setActivePlan(replanned);
			toast.success(
				`Đã cập nhật kế hoạch: ${replanned.total_planned_sources} nguồn đang hoạt động.`
			);
		} catch (_err) {
			toast.error("Không thể tính toán lại kế hoạch. Đã khôi phục trạng thái cũ.");
			// Revert to original spec
			setActivePlanSpec(activeSpec);
		} finally {
			setIsReplanning(false);
		}
	};

	return (
		<div
			data-testid="source-status-panel"
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				className
			)}
		>
			{/* Header bar */}
			<div className="h-11 border-b border-border/80 bg-muted/30 flex items-center justify-between px-3.5 shrink-0">
				<div className="flex items-center gap-2 min-w-0">
					<Activity className="w-3.5 h-3.5 text-emerald-500 shrink-0" aria-hidden="true" />
					<div className="min-w-0">
						<span className="text-xs font-bold text-foreground truncate block">
							Giám Sát Độ Phủ Nguồn (Source Coverage)
						</span>
					</div>
				</div>

				<div className="flex items-center gap-1.5 shrink-0">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refetchGlobal()}
						disabled={isRefetching || isReplanning}
						className="h-7 px-2 text-[11px] gap-1"
						title="Làm mới trạng thái"
					>
						<RefreshCw
							className={cn(
								"w-3 h-3 text-emerald-500",
								(isRefetching || isReplanning) && "animate-spin"
							)}
						/>
						<span className="hidden sm:inline">Làm mới</span>
					</Button>
				</div>
			</div>

			{/* Sub-header context indicator */}
			<div className="px-3.5 py-2 border-b border-border/50 bg-card/40 flex items-center justify-between text-[11px] text-muted-foreground">
				<div className="flex items-center gap-1.5 truncate">
					<Globe className="w-3 h-3 text-sky-500 shrink-0" />
					<span className="truncate">
						{activePlan
							? `Chiến dịch: ${activePlan.campaign_name}`
							: "Chế độ xem toàn cục (Toàn bộ nguồn khả dụng)"}
					</span>
				</div>
				<span className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded text-foreground font-semibold shrink-0">
					{currentSelectedSources.length}/{displaySources.length} nguồn bật
				</span>
			</div>

			{/* Content list */}
			<div className="flex-1 overflow-y-auto p-3.5 space-y-2.5 scrollbar-thin">
				{isLoadingGlobal && displaySources.length === 0 ? (
					<div className="flex flex-col items-center justify-center h-48 space-y-2 text-muted-foreground text-xs">
						<Loader2 className="w-5 h-5 text-emerald-500 animate-spin" />
						<span>Đang tải thông tin sức khỏe và độ phủ nguồn...</span>
					</div>
				) : displaySources.length === 0 ? (
					<Card className="p-6 text-center space-y-2 bg-muted/20 border-dashed">
						<p className="text-xs text-muted-foreground">Không tìm thấy nguồn dữ liệu khả dụng.</p>
					</Card>
				) : (
					displaySources.map((source) => {
						const isExpanded = expandedSources.has(source.source_name);
						const isEnabled = currentSelectedSources.includes(source.source_name);
						const isDegraded = source.status === "degraded" || source.status === "offline";

						return (
							<div
								key={source.source_name}
								data-testid={`source-card-${source.source_name}`}
								className={cn(
									"rounded-xl border transition-all duration-150 overflow-hidden bg-card/70",
									isEnabled
										? "border-border/80 shadow-2xs"
										: "border-border/40 opacity-65 bg-muted/20"
								)}
							>
								{/* Card header row */}
								<div className="p-3 flex items-center justify-between gap-2.5">
									<div className="flex items-center gap-2.5 min-w-0">
										<Switch
											data-testid={`toggle-source-${source.source_name}`}
											checked={isEnabled}
											disabled={isReplanning}
											onCheckedChange={(checked) => handleToggleSource(source.source_name, checked)}
											aria-label={`Bật hoặc tắt nguồn ${source.source_name}`}
										/>
										<div className="min-w-0">
											<div className="flex items-center gap-1.5">
												<span className="font-bold text-xs text-foreground uppercase tracking-wide truncate">
													{source.source_name}
												</span>
												<Badge variant="secondary" className="text-[9px] py-0 px-1 font-mono">
													{source.category}
												</Badge>
												{isDegraded && (
													<Badge
														data-testid={`badge-degraded-${source.source_name}`}
														variant="outline"
														className="bg-amber-500/10 text-amber-500 border-amber-500/30 text-[9px] py-0"
													>
														Degraded
													</Badge>
												)}
											</div>
										</div>
									</div>

									{/* Badge and expand trigger */}
									<div className="flex items-center gap-2 shrink-0">
										<SourceCoverageBadge
											quality={source.location_coverage_quality}
											score={source.location_coverage_score}
											supportedProvinces={source.supported_provinces}
										/>

										<Button
											type="button"
											variant="ghost"
											size="sm"
											onClick={() => toggleExpand(source.source_name)}
											className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
											aria-label={isExpanded ? "Thu gọn chi tiết" : "Mở rộng chi tiết"}
										>
											{isExpanded ? (
												<ChevronUp className="w-3.5 h-3.5" />
											) : (
												<ChevronDown className="w-3.5 h-3.5" />
											)}
										</Button>
									</div>
								</div>

								{/* Compact summary footer */}
								<div className="px-3 pb-2.5 pt-1 text-[11px] text-muted-foreground flex items-center justify-between border-t border-border/30">
									<div className="flex items-center gap-1.5 truncate">
										<MapPin className="w-3 h-3 text-emerald-500 shrink-0" />
										<span className="truncate">
											{source.supported_provinces?.length
												? source.supported_provinces.includes("*")
													? "Toàn quốc"
													: source.supported_provinces.slice(0, 3).join(", ") +
														(source.supported_provinces.length > 3 ? "..." : "")
												: "Toàn quốc"}
										</span>
									</div>
									<span className="font-mono text-[10px] shrink-0 font-medium">
										Định mức: {source.allocated_limit} leads
									</span>
								</div>

								{/* Expandable details */}
								{isExpanded && (
									<div className="px-3 py-2.5 bg-muted/40 border-t border-border/50 text-xs space-y-2">
										<div className="flex items-center justify-between text-[11px]">
											<span className="text-muted-foreground">Điểm độ phủ chính xác:</span>
											<span className="font-mono font-bold text-foreground">
												{((source.location_coverage_score ?? 0) * 100).toFixed(0)}%
											</span>
										</div>

										<div className="text-[11px] space-y-1">
											<span className="text-muted-foreground block">Tỉnh/thành hỗ trợ:</span>
											<p className="font-mono text-[10px] text-foreground/90 bg-background/60 p-1.5 rounded border border-border/40">
												{source.supported_provinces?.length
													? source.supported_provinces.join(", ")
													: "Toàn quốc (*)"}
											</p>
										</div>

										{source.degraded_reason && (
											<div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-[11px] flex items-start gap-1.5">
												<AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
												<span>{source.degraded_reason}</span>
											</div>
										)}
									</div>
								)}
							</div>
						);
					})
				)}
			</div>

			{/* Idle state CTA if no active plan exists */}
			{!activePlan && onOpenPlanBuilder && (
				<div className="p-3 border-t border-border/80 bg-muted/20 shrink-0">
					<Button
						type="button"
						size="sm"
						onClick={onOpenPlanBuilder}
						className="w-full text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
					>
						<Sparkles className="w-3.5 h-3.5" />
						Tạo kế hoạch thu thập (Create Lead Plan)
					</Button>
				</div>
			)}
		</div>
	);
};
