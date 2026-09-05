"use client";

import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type CoverageQualityTier = "high" | "medium" | "low" | "none";

export interface CoverageVariantConfig {
	label: string;
	class: string;
	description: string;
}

export const COVERAGE_BADGE_VARIANTS: Record<CoverageQualityTier, CoverageVariantConfig> = {
	high: {
		label: "High Coverage",
		class: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
		description: "Nguồn có dữ liệu trực tiếp tại tỉnh/thành mục tiêu",
	},
	medium: {
		label: "Medium Coverage",
		class: "bg-sky-500/10 text-sky-500 border-sky-500/30",
		description: "Nguồn có độ phủ khu vực hoặc hỗ trợ toàn quốc",
	},
	low: {
		label: "Low Coverage",
		class: "bg-amber-500/10 text-amber-500 border-amber-500/30",
		description: "Độ phủ hạn chế hoặc phụ thuộc từ khóa fallback",
	},
	none: {
		label: "No Coverage",
		class: "bg-rose-500/10 text-rose-500 border-rose-500/30",
		description: "Không có dữ liệu tại khu vực địa lý đã chọn",
	},
};

export function getCoverageQualityTier(score: number | null | undefined): CoverageQualityTier {
	if (score === null || score === undefined) return "none";
	if (score >= 0.9) return "high";
	if (score >= 0.6) return "medium";
	if (score >= 0.3) return "low";
	return "none";
}

export function formatCoveragePercentage(score: number | null | undefined): string {
	if (score === null || score === undefined) return "Độ phủ: 0%";
	return `Độ phủ: ${Math.round(score * 100)}%`;
}

export interface SourceCoverageBadgeProps {
	quality?: CoverageQualityTier | string;
	score?: number | null;
	supportedProvinces?: string[];
	className?: string;
	showTooltip?: boolean;
}

export const SourceCoverageBadge: React.FC<SourceCoverageBadgeProps> = ({
	quality,
	score,
	supportedProvinces = [],
	className,
	showTooltip = true,
}) => {
	const validTier: CoverageQualityTier =
		quality && quality in COVERAGE_BADGE_VARIANTS
			? (quality as CoverageQualityTier)
			: getCoverageQualityTier(score);

	const variant = COVERAGE_BADGE_VARIANTS[validTier] ?? COVERAGE_BADGE_VARIANTS.none;
	const pctText = formatCoveragePercentage(score);

	const tierTextColor: Record<CoverageQualityTier, string> = {
		high: "text-emerald-400",
		medium: "text-sky-400",
		low: "text-amber-400",
		none: "text-rose-400",
	};

	const badgeElement = (
		<Badge
			data-testid={`coverage-quality-badge-${validTier}`}
			variant="outline"
			className={cn(
				"text-[10px] uppercase font-mono border cursor-default select-none transition-colors",
				variant.class,
				className
			)}
		>
			{variant.label}
		</Badge>
	);

	if (!showTooltip) {
		return badgeElement;
	}

	const provincesText =
		supportedProvinces.length > 0
			? supportedProvinces.includes("*")
				? "Toàn quốc"
				: supportedProvinces.slice(0, 4).join(", ") + (supportedProvinces.length > 4 ? "..." : "")
			: "Toàn quốc";

	return (
		<TooltipProvider delayDuration={150}>
			<Tooltip>
				<TooltipTrigger asChild>{badgeElement}</TooltipTrigger>
				<TooltipContent
					side="top"
					className="max-w-xs text-xs space-y-1 bg-zinc-900 border-zinc-700 text-zinc-200"
				>
					<p className={cn("font-semibold", tierTextColor[validTier])}>{pctText}</p>
					<p className="text-zinc-300">{variant.description}</p>
					<p className="text-[10px] text-zinc-400">Tỉnh/thành: {provincesText}</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
