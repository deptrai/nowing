"use client";

import { type FC, useMemo } from "react";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useScraperCapabilities } from "@/hooks/use-scraper-capabilities";
import { findPlatform, type PlaygroundPlatform } from "@/lib/playground/catalog";

/**
 * Full-color brand marks for the platform-native scraper APIs (web, Google
 * Search, Google Maps, Reddit, YouTube) available in this workspace, shown beside the
 * composer "+" so the user can see these native endpoints are connected. Laid
 * out as the same overlapping avatar group used by the connect-tools tray
 * from the composer actions. The capability registry is the source of truth;
 * icons are display-only with a status tooltip.
 */
export const ConnectedScraperIcons: FC<{ workspaceId: number }> = ({ workspaceId }) => {
	const { data: capabilities } = useScraperCapabilities(workspaceId);

	const platforms = useMemo<PlaygroundPlatform[]>(() => {
		if (!capabilities?.length) return [];
		const seen = new Set<string>();
		const result: PlaygroundPlatform[] = [];
		for (const cap of capabilities) {
			const platformId = cap.name.split(".")[0];
			if (seen.has(platformId)) continue;
			seen.add(platformId);
			const platform = findPlatform(platformId);
			if (platform) result.push(platform);
		}
		return result;
	}, [capabilities]);

	if (platforms.length === 0) return null;

	const visiblePlatforms = platforms.slice(0, 3);
	const remainingCount = platforms.length - 3;

	return (
		<div className="hidden items-center gap-1 sm:flex">
			<div aria-hidden className="h-5 w-px shrink-0 bg-border" />
			<AvatarGroup className="shrink-0">
				{visiblePlatforms.map((platform, i) => {
					const Icon = platform.icon;
					return (
						<Tooltip key={platform.id}>
							<TooltipTrigger asChild>
								<Avatar className="size-4" style={{ zIndex: visiblePlatforms.length - i }}>
									<AvatarFallback className="bg-popover text-[9px]">
										<Icon className="size-2.5" aria-hidden="true" />
									</AvatarFallback>
								</Avatar>
							</TooltipTrigger>
							<TooltipContent side="bottom">{platform.label} scraper available</TooltipContent>
						</Tooltip>
					);
				})}
				{remainingCount > 0 && (
					<Tooltip>
						<TooltipTrigger asChild>
							<Avatar className="size-4" style={{ zIndex: 0 }}>
								<AvatarFallback className="bg-muted text-[8px] font-medium text-muted-foreground font-mono">
									+{remainingCount}
								</AvatarFallback>
							</Avatar>
						</TooltipTrigger>
						<TooltipContent side="bottom">+{remainingCount} more scrapers connected</TooltipContent>
					</Tooltip>
				)}
			</AvatarGroup>
		</div>
	);
};
