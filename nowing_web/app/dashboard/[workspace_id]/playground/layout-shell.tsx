"use client";

import { usePathname, useSelectedLayoutSegments } from "next/navigation";
import type React from "react";
import { useMemo } from "react";
import {
	getPlaygroundNavGroups,
	getPlaygroundNavItems,
	getPlaygroundSelectedLabel,
	RoutedSectionShell,
} from "@/components/layout";

interface PlaygroundLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

function usePlaygroundBase(workspaceId: string, pathname: string | null) {
	const userSettingsBase = `/dashboard/${workspaceId}/user-settings/playground`;
	if (pathname?.startsWith(userSettingsBase)) return userSettingsBase;
	return `/dashboard/${workspaceId}/playground`;
}

export function PlaygroundLayoutShell({ workspaceId, children }: PlaygroundLayoutShellProps) {
	const pathname = usePathname();
	const base = usePlaygroundBase(workspaceId, pathname);
	const segments = useSelectedLayoutSegments();

	const topLevelItems = useMemo(() => getPlaygroundNavItems(base), [base]);
	const providerGroups = useMemo(() => getPlaygroundNavGroups(base), [base]);

	const activeValue =
		segments.length >= 2
			? `${segments[0]}/${segments[1]}`
			: segments[0] && topLevelItems.some((item) => item.value === segments[0])
				? segments[0]
				: "overview";

	const selectedLabel = getPlaygroundSelectedLabel(activeValue, topLevelItems, providerGroups);

	return (
		<RoutedSectionShell
			title="API Playground"
			items={topLevelItems}
			groups={providerGroups}
			activeValue={activeValue}
			selectedLabel={selectedLabel}
			mobileNav="drawer"
			desktopNav={false}
		>
			{children}
		</RoutedSectionShell>
	);
}
