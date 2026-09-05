"use client";

import { useAtomValue } from "jotai";
import {
	AlertTriangle,
	ArrowRight,
	Bot,
	ChevronDown,
	ChevronUp,
	Loader2,
	MapPin,
	RefreshCw,
	Rocket,
	Sparkles,
	Wand2,
} from "lucide-react";
import { useState } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import type {
	CampaignPlanResponse,
	IcpConfig,
	LeadGenOrchestratorResult,
	SourcePlanAllocation,
} from "@/contracts/types/campaign.types";
import type { Lead } from "@/contracts/types/leads.types";
import {
	buildLocationSummary,
	computeLocationDiff,
	type LocationDiffResult,
} from "@/lib/geo/vietnam-divisions";
import { cn } from "@/lib/utils";
import { SourceCoverageBadge } from "./SourceCoverageBadge";

export interface PlanSummaryCardProps {
	plan: CampaignPlanResponse | null;
	icpConfig?: IcpConfig | null;
	isLoading?: boolean;
	onRequestPlan?: () => void;
	onApplyPlan?: (plan: CampaignPlanResponse) => void;
	onSmokeTest?: () => void;
	smokeTestResult?: LeadGenOrchestratorResult | null;
	previousLocationProfile?: import("@/contracts/types/leads.types").LocationProfile | null;
	onRefineLocation?: (action: "narrow" | "expand" | "switch-source" | "custom") => void;
	onConfirmFullRun?: () => void;
	className?: string;
	inRightCanvas?: boolean;
}

export function PlanSummaryCard({
	plan,
	icpConfig,
	isLoading = false,
	onRequestPlan,
	onApplyPlan,
	onSmokeTest,
	smokeTestResult,
	previousLocationProfile,
	onRefineLocation,
	onConfirmFullRun,
	className,
	inRightCanvas = false,
}: PlanSummaryCardProps) {
	const userQuery = useAtomValue(currentUserAtom);
	const [expanded, setExpanded] = useState<Set<string>>(new Set());

	const creditBalance =
		typeof userQuery.data?.credit_micros_balance === "number"
			? userQuery.data.credit_micros_balance
			: 0;
	const estimatedCost = plan?.estimated_cost_micros ?? 0;
	const isInsufficient = plan ? estimatedCost > creditBalance : false;

	const toggleExpand = (sourceName: string) => {
		setExpanded((prev) => {
			const next = new Set(prev);
			if (next.has(sourceName)) next.delete(sourceName);
			else next.add(sourceName);
			return next;
		});
	};

	const renderQualityBadge = (quality: string, score?: number, supportedProvinces?: string[]) => {
		return (
			<SourceCoverageBadge
				quality={quality}
				score={score}
				supportedProvinces={supportedProvinces}
			/>
		);
	};

	const effectiveIcp =
		icpConfig ?? (plan as (CampaignPlanResponse & { icp_config?: IcpConfig }) | null)?.icp_config;
	const locationProfile = effectiveIcp?.location_profile;
	const locationText = locationProfile ? buildLocationSummary(locationProfile) : null;

	const locationType = effectiveIcp?.location_profile?.location_type ?? "both";
	const currentLocationProfile = effectiveIcp?.location_profile ?? null;
	const locationDiff: LocationDiffResult | null =
		previousLocationProfile && currentLocationProfile
			? computeLocationDiff(previousLocationProfile, currentLocationProfile)
			: null;

	const smokeLeads: Lead[] = smokeTestResult?.leads?.slice(0, 5) ?? [];
	const locationMetadata = smokeTestResult?.location_match_metadata;

	const hasZeroLeads = smokeTestResult && smokeTestResult.total_discovered === 0;

	if (isLoading) {
		return (
			<Card
				data-testid="plan-summary-loading"
				className={cn(
					"bg-zinc-900/60 border-zinc-800 p-6 flex flex-col items-center justify-center min-h-[220px]",
					className
				)}
			>
				<Loader2 className="w-6 h-6 text-emerald-400 animate-spin mb-2" />
				<p className="text-xs text-zinc-400 font-medium">
					Đang tính toán Pre-Flight Plan & phân bổ nguồn...
				</p>
			</Card>
		);
	}

	if (!plan) {
		return (
			<Card
				data-testid="plan-summary-empty"
				className={cn(
					"bg-zinc-900/40 border-dashed border-zinc-800 p-6 text-center space-y-3",
					className
				)}
			>
				<div className="mx-auto w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
					<Sparkles className="w-5 h-5 text-emerald-400" />
				</div>
				<div>
					<h4 className="text-xs font-semibold text-zinc-200">
						Chưa có Kế hoạch Thu thập (Pre-Flight Plan)
					</h4>
					<p className="text-[11px] text-zinc-400 mt-1 max-w-sm mx-auto">
						Xem trước phân bổ số lượng lead theo từng adapter, độ phủ địa bàn, và ước tính chi phí
						trước khi bấm chạy.
					</p>
				</div>
				{onRequestPlan && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={onRequestPlan}
						data-testid="btn-generate-plan"
						className="text-xs border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10"
					>
						<RefreshCw className="w-3.5 h-3.5 mr-1.5" />
						Xem trước kế hoạch phân bổ (Pre-Flight Plan)
					</Button>
				)}
			</Card>
		);
	}

	const hasCoverageWarning =
		plan.warnings.length > 0 ||
		plan.source_allocations.some(
			(a) => a.location_coverage_quality === "low" || a.location_coverage_quality === "none"
		);

	return (
		<Card
			data-testid="plan-summary-card"
			className={cn("bg-zinc-900/80 border-emerald-500/30 shadow-xl overflow-hidden", className)}
		>
			<CardHeader className={cn("pb-3 border-b border-zinc-800", inRightCanvas && "py-3")}>
				<div className="flex items-start justify-between gap-2">
					<div className="space-y-1.5 min-w-0">
						<CardTitle
							className={cn(
								"text-sm font-bold text-zinc-100 flex items-center gap-2",
								inRightCanvas && "text-xs"
							)}
						>
							<Bot className="w-4 h-4 text-emerald-400 shrink-0" />
							<span className="truncate">Pre-Flight Lead Plan: {plan.campaign_name}</span>
						</CardTitle>
						<CardDescription className="text-[11px] text-zinc-400">
							Tổng hợp phân bổ {plan.total_planned_sources} nguồn thu thập tín hiệu & tối ưu địa bàn
						</CardDescription>

						{/* Intents */}
						{effectiveIcp?.intents && effectiveIcp.intents.length > 0 && (
							<div className="flex flex-wrap gap-1 pt-1">
								{effectiveIcp.intents.map((intent) => (
									<Badge
										key={intent}
										variant="secondary"
										className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20"
									>
										{intent}
									</Badge>
								))}
							</div>
						)}
					</div>

					{onRequestPlan && !inRightCanvas && (
						<Button
							type="button"
							variant="ghost"
							size="sm"
							onClick={onRequestPlan}
							className="text-[11px] h-7 px-2 text-zinc-400 hover:text-zinc-200 shrink-0"
							title="Cập nhật lại kế hoạch"
						>
							<RefreshCw className="w-3 h-3" />
						</Button>
					)}
				</div>

				{/* Location Profile Section */}
				{locationText && (
					<div className="mt-3 p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/80 flex items-start gap-2">
						<MapPin className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
						<div className="min-w-0">
							<p className="text-[11px] text-zinc-300 font-medium truncate">{locationText}</p>
							<Badge
								variant="outline"
								className="text-[9px] mt-1 bg-zinc-800 text-zinc-400 border-zinc-700"
							>
								{locationType}
							</Badge>
						</div>
					</div>
				)}
			</CardHeader>

			<CardContent className={cn("space-y-4 pt-4 text-xs", inRightCanvas && "pt-3 space-y-3")}>
				{/* Warnings Banner */}
				{(plan.warnings.length > 0 || hasCoverageWarning) && (
					<div
						data-testid="plan-warnings-banner"
						className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/40 text-amber-300 space-y-1"
					>
						<div className="flex items-center gap-1.5 font-semibold text-[11px]">
							<AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
							<span>Cảnh báo độ phủ & Fallback</span>
						</div>
						<ul className="list-disc list-inside text-[11px] text-amber-300/90 pl-1 space-y-0.5">
							{plan.warnings.map((w) => (
								<li key={w}>{w}</li>
							))}
						</ul>
					</div>
				)}

				{/* High-level KPIs */}
				<div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-center">
					<div>
						<span className="text-zinc-500 text-[10px] block">Nguồn Dự Kiến</span>
						<span className="font-bold text-zinc-200 text-sm">{plan.total_planned_sources}</span>
					</div>
					<div className="border-x border-zinc-800">
						<span className="text-zinc-500 text-[10px] block">Ước Tính Lead</span>
						<span className="font-bold text-emerald-400 text-sm">
							~{plan.estimated_reachable_leads}
						</span>
					</div>
					<div>
						<span className="text-zinc-500 text-[10px] block">Dự Toán Chi Phí</span>
						<span className="font-mono font-bold text-amber-400 text-sm">
							{plan.estimated_cost_vnd.toLocaleString("vi-VN")} đ
						</span>
					</div>
				</div>

				{/* Insufficient Credits Warning */}
				{isInsufficient && (
					<div
						data-testid="plan-insufficient-credits"
						className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 space-y-1"
					>
						<div className="flex items-center gap-1.5 font-semibold text-[11px]">
							<AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-400" />
							<span>Không đủ tín dụng</span>
						</div>
						<p className="text-[11px] text-rose-300/90">
							Dự toán {plan.estimated_cost_micros.toLocaleString("vi-VN")} micros vượt quá số dư{" "}
							{creditBalance.toLocaleString("vi-VN")} micros. Vui lòng nạp thêm hoặc giảm số lượng
							lead.
						</p>
					</div>
				)}

				{/* Source Allocations Breakdown */}
				<div className="space-y-2">
					<span className="text-zinc-400 font-semibold text-[11px] block">
						Phân bổ nguồn thu thập ({plan.source_allocations.length}):
					</span>
					<div className="space-y-2" data-testid="source-allocations-list">
						{plan.source_allocations.map((alloc: SourcePlanAllocation) => {
							const isExpanded = expanded.has(alloc.source_name);
							return (
								<div
									key={alloc.source_name}
									data-testid={`source-allocation-${alloc.source_name}`}
									className="rounded-lg bg-zinc-950/40 border border-zinc-800/80 overflow-hidden"
								>
									<button
										type="button"
										onClick={() => toggleExpand(alloc.source_name)}
										className="w-full p-2.5 flex items-center justify-between text-left"
									>
										<div className="flex items-center gap-2">
											<span className="font-bold text-zinc-200 uppercase tracking-wide text-xs">
												{alloc.source_name}
											</span>
											<Badge
												variant="secondary"
												className="text-[9px] bg-zinc-800 text-zinc-400 py-0"
											>
												{alloc.category}
											</Badge>
											{alloc.status === "degraded" && (
												<Badge
													data-testid={`badge-degraded-${alloc.source_name}`}
													variant="outline"
													className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-[9px] py-0"
												>
													Degraded
												</Badge>
											)}
										</div>
										<div className="flex items-center gap-2">
											{renderQualityBadge(
												alloc.location_coverage_quality,
												alloc.location_coverage_score,
												alloc.supported_provinces
											)}
											<span className="font-mono font-bold text-zinc-300 text-xs">
												{alloc.allocated_limit} leads
											</span>
											{isExpanded ? (
												<ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
											) : (
												<ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
											)}
										</div>
									</button>

									{/* Coverage details */}
									<div className="px-2.5 pb-2.5 flex items-center justify-between text-[11px] text-zinc-400 border-t border-zinc-800/40 pt-1.5">
										<div className="flex items-center gap-1.5">
											<MapPin className="w-3 h-3 text-emerald-400" />
											<span>
												Độ phủ: {((alloc.location_coverage_score ?? 0) * 100).toFixed(0)}%
											</span>
											<span className="text-zinc-600">•</span>
											<span className="text-zinc-500">
												Tỉnh/thành:{" "}
												{alloc.supported_provinces?.length
													? alloc.supported_provinces.slice(0, 3).join(", ")
													: "Toàn quốc"}
												{alloc.supported_provinces?.length > 3 ? "..." : ""}
											</span>
										</div>
										<span className="text-zinc-500">Ưu tiên: P{alloc.priority}</span>
									</div>

									{/* Expanded details */}
									{isExpanded && (
										<div className="px-2.5 pb-2.5 space-y-1.5 border-t border-zinc-800/40 pt-2">
											<div className="text-[11px] text-zinc-400">
												<span className="text-zinc-500">Nguồn hỗ trợ:</span>{" "}
												{alloc.supported_provinces?.length
													? alloc.supported_provinces.join(", ")
													: "Toàn quốc"}
											</div>
											{alloc.degraded_reason && (
												<p className="text-[10px] text-amber-400/90 italic bg-amber-950/20 px-2 py-0.5 rounded">
													{alloc.degraded_reason}
												</p>
											)}
										</div>
									)}
								</div>
							);
						})}
					</div>
				</div>
			</CardContent>

			{/* Smoke Test Preview & Feedback Loop (Story 26.29) */}
			{smokeTestResult && !inRightCanvas && (
				<div className="px-4 pb-4 space-y-3">
					{/* AC-1: Compact lead matrix preview */}
					{smokeLeads.length > 0 && (
						<div className="rounded-lg border border-emerald-800/40 bg-emerald-950/10 overflow-hidden">
							<div className="px-3 py-2 border-b border-emerald-800/30 flex items-center justify-between">
								<span className="text-[11px] font-semibold text-emerald-300">
									Preview {smokeLeads.length} lead
								</span>
								{locationMetadata && (
									<span className="text-[10px] text-zinc-400">
										Đúng địa bàn: {locationMetadata.matched_count} / Ngoài:{" "}
										{locationMetadata.outside_count}
									</span>
								)}
							</div>
							<div className="divide-y divide-zinc-800/60">
								{smokeLeads.map((lead, idx) => {
									const matched =
										(lead as { location_match_score?: number }).location_match_score ?? 0;
									const isOutside = matched < 65;
									return (
										<div
											key={lead.id ?? `smoke-${idx}`}
											data-testid={`smoke-lead-${idx}`}
											className="px-3 py-2 text-[11px] space-y-1"
										>
											<div className="flex items-center justify-between gap-2">
												<span className="font-medium text-zinc-200 truncate">
													{lead.company_name || lead.name || "Lead"}
												</span>
												<Badge
													variant={isOutside ? "destructive" : "default"}
													className={cn(
														"text-[9px] h-5",
														isOutside
															? "bg-rose-950/40 text-rose-300 border-rose-800/40"
															: "bg-emerald-950/40 text-emerald-300 border-emerald-800/40"
													)}
												>
													{isOutside ? "Ngoài địa bàn" : "Đúng địa bàn"}
												</Badge>
											</div>
											<div className="flex items-center gap-1.5 text-zinc-400">
												<MapPin className="w-3 h-3 shrink-0" />
												<span className="truncate">{lead.location || "—"}</span>
											</div>
											<div className="flex items-center justify-between gap-2">
												<Badge variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-300">
													{lead.source}
												</Badge>
												<span className="text-zinc-500 truncate max-w-[60%]">
													{lead.content_snippet || ""}
												</span>
											</div>
										</div>
									);
								})}
							</div>
						</div>
					)}

					{/* AC-4: Diff summary on re-run */}
					{locationDiff?.provinceChanged && (
						<div
							data-testid="smoke-test-diff-summary"
							className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-800 text-[11px]"
						>
							<div className="font-semibold text-zinc-200 mb-1.5">Thay đổi địa bàn</div>
							{locationDiff.provinceChanged && (
								<div className="text-zinc-300">
									Đổi tỉnh <span className="text-rose-400">{locationDiff.prevProvinceName}</span>{" "}
									sang <span className="text-emerald-400">{locationDiff.nextProvinceName}</span>
								</div>
							)}
							{locationDiff.addedDistricts.length > 0 && (
								<div className="mt-1">
									<span className="text-emerald-400">
										+ {locationDiff.addedDistricts.map((d) => d.name).join(", ")}
									</span>
								</div>
							)}
							{locationDiff.removedDistricts.length > 0 && (
								<div className="mt-1">
									<span className="text-rose-400">
										- {locationDiff.removedDistricts.map((d) => d.name).join(", ")}
									</span>
								</div>
							)}
						</div>
					)}

					{/* AC-6: Zero-leads diagnostic card */}
					{hasZeroLeads && (
						<div
							data-testid="zero-leads-diagnostic"
							className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 space-y-2"
						>
							<div className="flex items-center gap-1.5 font-semibold text-[11px]">
								<AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-400" />
								<span>Không tìm thấy lead nào</span>
							</div>
							<p className="text-[11px] text-rose-300/90">
								{locationMetadata?.zero_leads_reason === "NO_DATA_IN_LOCATION"
									? "Không có dữ liệu tại địa bàn đã chọn."
									: locationMetadata?.zero_leads_reason === "SOURCE_DEGRADED"
										? "Nguồn cào suy giảm hoặc ngoại tuyến."
										: "Bộ lọc quá hẹp."}
							</p>
							<div className="flex flex-wrap gap-2">
								{locationProfile && (
									<Button
										type="button"
										variant="outline"
										size="sm"
										onClick={() => onRefineLocation?.("expand")}
										className="text-[10px] h-7 border-rose-700 text-rose-300 hover:bg-rose-950/40"
									>
										Mở rộng ra toàn {locationProfile.province_name}
									</Button>
								)}
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={() => onRefineLocation?.("switch-source")}
									className="text-[10px] h-7 border-rose-700 text-rose-300 hover:bg-rose-950/40"
								>
									Bật thêm nguồn toàn quốc
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={() => onRefineLocation?.("narrow")}
									className="text-[10px] h-7 border-rose-700 text-rose-300 hover:bg-rose-950/40"
								>
									Giảm ngưỡng lọc tương đồng
								</Button>
							</div>
						</div>
					)}

					{/* AC-2: Location feedback banner */}
					{smokeLeads.length > 0 && (
						<div
							data-testid="location-feedback-banner"
							className="p-3 rounded-lg bg-sky-950/20 border border-sky-800/40 text-sky-100"
						>
							<div className="text-[11px] font-medium mb-2">Địa điểm có đúng không?</div>
							<div className="flex flex-wrap gap-2">
								<Button
									type="button"
									size="sm"
									data-testid="btn-confirm-full-run"
									onClick={onConfirmFullRun}
									className="text-[10px] h-7 bg-emerald-500 hover:bg-emerald-400 text-black"
								>
									Đúng — chạy đầy đủ
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									data-testid="btn-refine-narrow"
									onClick={() => onRefineLocation?.("narrow")}
									className="text-[10px] h-7 border-sky-500/40 text-sky-300 hover:bg-sky-500/10"
								>
									Thu hẹp khu vực
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									data-testid="btn-refine-expand"
									onClick={() => onRefineLocation?.("expand")}
									className="text-[10px] h-7 border-sky-500/40 text-sky-300 hover:bg-sky-500/10"
								>
									Mở rộng khu vực
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									data-testid="btn-refine-switch-source"
									onClick={() => onRefineLocation?.("switch-source")}
									className="text-[10px] h-7 border-sky-500/40 text-sky-300 hover:bg-sky-500/10"
								>
									Đổi nguồn
								</Button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									data-testid="btn-refine-custom-location"
									onClick={() => onRefineLocation?.("custom")}
									className="text-[10px] h-7 border-sky-500/40 text-sky-300 hover:bg-sky-500/10"
								>
									Chỉnh vị trí chi tiết
								</Button>
							</div>
						</div>
					)}
				</div>
			)}

			{!inRightCanvas && onSmokeTest && (
				<CardFooter className="pt-2 pb-4 px-4 border-t border-zinc-800 flex flex-col gap-2">
					<div className="flex gap-2 w-full">
						<Button
							type="button"
							variant="outline"
							size="sm"
							onClick={onSmokeTest}
							disabled={isLoading}
							data-testid="btn-smoke-test"
							className="flex-1 text-xs border-sky-500/40 text-sky-400 hover:bg-sky-500/10"
						>
							{isLoading ? (
								<Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
							) : (
								<Wand2 className="w-3.5 h-3.5 mr-1.5" />
							)}
							Chạy thử 5 lead
						</Button>
						{onApplyPlan && (
							<Button
								type="button"
								size="sm"
								onClick={() => onApplyPlan(plan)}
								disabled={isInsufficient}
								data-testid="btn-apply-plan"
								className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-semibold"
							>
								<Rocket className="w-3.5 h-3.5 mr-1.5" />
								Chạy chiến dịch đầy đủ
							</Button>
						)}
					</div>
					<p className="text-[10px] text-zinc-500 text-center">
						Hoặc bạn có thể chỉnh sửa kế hoạch trước khi chạy.
					</p>
				</CardFooter>
			)}

			{!inRightCanvas && !onSmokeTest && onApplyPlan && (
				<CardFooter className="pt-2 pb-4 px-4 border-t border-zinc-800 flex justify-end">
					<Button
						type="button"
						size="sm"
						onClick={() => onApplyPlan(plan)}
						disabled={isInsufficient}
						data-testid="btn-apply-plan"
						className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-semibold"
					>
						Áp dụng kế hoạch này
						<ArrowRight className="w-3.5 h-3.5 ml-1.5" />
					</Button>
				</CardFooter>
			)}
		</Card>
	);
}
