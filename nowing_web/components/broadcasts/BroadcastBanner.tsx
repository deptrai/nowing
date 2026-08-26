"use client";

import { AlertTriangle, Info, Sparkles, Wrench, X } from "lucide-react";
import type { BannerType } from "@/contracts/types/broadcasts.types";
import { useBroadcastAnnouncements } from "@/lib/hooks/use-broadcast-announcements";

interface BroadcastBannerProps {
	workspaceId?: number | null;
}

function getBannerConfig(type: BannerType) {
	switch (type) {
		case "warning":
			return {
				icon: <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />,
				containerClass:
					"bg-amber-500/10 border-b border-amber-500/20 text-amber-900 dark:text-amber-200",
				closeClass: "text-amber-700 hover:bg-amber-500/20 dark:text-amber-300",
			};
		case "maintenance":
			return {
				icon: <Wrench className="h-4 w-4 shrink-0 text-rose-500" />,
				containerClass:
					"bg-rose-500/10 border-b border-rose-500/20 text-rose-900 dark:text-rose-200",
				closeClass: "text-rose-700 hover:bg-rose-500/20 dark:text-rose-300",
			};
		case "promo":
			return {
				icon: <Sparkles className="h-4 w-4 shrink-0 text-purple-500" />,
				containerClass:
					"bg-purple-500/10 border-b border-purple-500/20 text-purple-900 dark:text-purple-200",
				closeClass: "text-purple-700 hover:bg-purple-500/20 dark:text-purple-300",
			};
		default:
			return {
				icon: <Info className="h-4 w-4 shrink-0 text-blue-500" />,
				containerClass:
					"bg-blue-500/10 border-b border-blue-500/20 text-blue-900 dark:text-blue-200",
				closeClass: "text-blue-700 hover:bg-blue-500/20 dark:text-blue-300",
			};
	}
}

export function BroadcastBanner({ workspaceId }: BroadcastBannerProps) {
	const { broadcasts, dismiss } = useBroadcastAnnouncements(workspaceId);

	if (!broadcasts || broadcasts.length === 0) {
		return null;
	}

	return (
		<div className="w-full flex flex-col">
			{broadcasts.map((banner) => {
				const config = getBannerConfig(banner.banner_type as BannerType);
				return (
					<div
						key={banner.id}
						data-testid={`broadcast-banner-${banner.id}`}
						className={`flex items-center justify-between px-4 py-2.5 text-xs sm:text-sm font-medium transition-all ${config.containerClass}`}
					>
						<div className="flex items-center gap-2 overflow-hidden">
							{config.icon}
							<div className="flex items-baseline gap-2 truncate">
								<span className="font-semibold">{banner.title}:</span>
								<span className="truncate opacity-90">{banner.message}</span>
							</div>
						</div>

						{banner.dismissible && (
							<button
								type="button"
								onClick={() => dismiss(banner.id)}
								className={`ml-3 rounded p-1 transition ${config.closeClass}`}
								title="Dismiss"
								aria-label="Dismiss banner"
							>
								<X className="h-4 w-4" />
							</button>
						)}
					</div>
				);
			})}
		</div>
	);
}
