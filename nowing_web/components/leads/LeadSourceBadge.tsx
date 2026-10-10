"use client";

import { Briefcase, Globe, Home, Landmark, Send, Share2, ShoppingBag, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface LeadSourceBadgeProps {
	source: string;
	className?: string;
	showTooltip?: boolean;
}

interface SourceVisualConfig {
	key: string;
	label: string;
	icon: React.ComponentType<{ className?: string }>;
	className: string;
	fallbackTooltip: string;
}

export function resolveSourceConfig(source: string): SourceVisualConfig {
	const s = (source || "").toLowerCase();

	if (s.includes("webset")) {
		return {
			key: "websets",
			label: "Websets",
			icon: Globe,
			className:
				"bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
			fallbackTooltip: "ChainLens Websets (Trích xuất từ web)",
		};
	}
	if (s.includes("facebook")) {
		return {
			key: "facebook",
			label: "Facebook",
			icon: Users,
			className:
				"bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
			fallbackTooltip: "Facebook Groups",
		};
	}
	if (s.includes("telegram")) {
		return {
			key: "telegram",
			label: "Telegram",
			icon: Send,
			className:
				"bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800",
			fallbackTooltip: "Telegram Channels",
		};
	}
	if (s.includes("bds") || s.includes("batdongsan")) {
		return {
			key: "batdongsan",
			label: "Batdongsan",
			icon: Home,
			className:
				"bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
			fallbackTooltip: "Batdongsan.com.vn",
		};
	}
	if (s.includes("topcv") || s.includes("itviec") || s.includes("job")) {
		return {
			key: "topcv",
			label: "Jobs",
			icon: Briefcase,
			className:
				"bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
			fallbackTooltip: "TopCV / ITviec Jobs",
		};
	}
	if (s.includes("tender") || s.includes("muasamcong")) {
		return {
			key: "tender",
			label: "Đấu Thầu",
			icon: Landmark,
			className:
				"bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800",
			fallbackTooltip: "Cổng Đấu Thầu (Mua Sắm Công)",
		};
	}
	if (s.includes("shopee") || s.includes("tiktok")) {
		return {
			key: "ecommerce",
			label: "E-commerce",
			icon: ShoppingBag,
			className:
				"bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-300 dark:border-orange-800",
			fallbackTooltip: "E-commerce Platform",
		};
	}
	if (s.includes("linkedin")) {
		return {
			key: "linkedin",
			label: "LinkedIn",
			icon: Share2,
			className:
				"bg-blue-50 text-blue-800 border-blue-300 dark:bg-blue-950/50 dark:text-blue-200 dark:border-blue-700",
			fallbackTooltip: "LinkedIn Search",
		};
	}

	return {
		key: "other",
		label: source || "Nguồn khác",
		icon: Globe,
		className:
			"bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700",
		fallbackTooltip: "Nguồn dữ liệu khác",
	};
}

export const LeadSourceBadge: React.FC<LeadSourceBadgeProps> = ({
	source,
	className,
	showTooltip = true,
}) => {
	const t = useTranslations("leads");
	const config = resolveSourceConfig(source);
	const Icon = config.icon;

	let tooltipText = config.fallbackTooltip;
	try {
		// Attempt reading leads.sourceBadge.{key} if translated
		const translated = t(`sourceBadge.${config.key}`);
		if (translated && !translated.startsWith("leads.sourceBadge.")) {
			tooltipText = translated;
		}
	} catch {
		// Fallback to configured string
	}

	let label = config.label;
	try {
		const translatedLabel = t(`sourceBadgeLabel.${config.key}`);
		if (translatedLabel && !translatedLabel.startsWith("leads.sourceBadgeLabel.")) {
			label = translatedLabel;
		}
	} catch {
		// Fallback to configured label
	}

	const badgeContent = (
		<span
			data-testid="lead-source-badge"
			data-source-key={config.key}
			className={cn(
				"inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border uppercase tracking-wider transition-colors",
				config.className,
				className
			)}
		>
			<Icon className="w-3 h-3 shrink-0" aria-hidden="true" />
			<span>{label}</span>
		</span>
	);

	if (!showTooltip) {
		return badgeContent;
	}

	return (
		<TooltipProvider delayDuration={200}>
			<Tooltip>
				<TooltipTrigger asChild>{badgeContent}</TooltipTrigger>
				<TooltipContent side="top" className="text-xs">
					{tooltipText}
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
