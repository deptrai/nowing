"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { BroadcastActiveRead } from "@/contracts/types/broadcasts.types";
import { broadcastsApiService } from "@/lib/apis/broadcasts-api.service";

const DISMISSED_KEY = "nowing_dismissed_broadcasts";

export function useBroadcastAnnouncements(workspaceId?: number | null) {
	const [dismissedIds, setDismissedIds] = useState<string[]>([]);

	useEffect(() => {
		try {
			const stored = localStorage.getItem(DISMISSED_KEY);
			if (stored) {
				const parsed = JSON.parse(stored);
				if (Array.isArray(parsed)) {
					setDismissedIds(parsed);
				}
			}
		} catch {
			// Ignore storage errors in private browsing / SSR
		}
	}, []);

	const {
		data: rawBroadcasts = [],
		isLoading,
		error,
		refetch,
	} = useQuery<BroadcastActiveRead[]>({
		queryKey: ["broadcasts", "active", workspaceId],
		queryFn: () => broadcastsApiService.listActive(workspaceId),
		refetchInterval: 60_000,
	});

	const dismiss = (id: string) => {
		setDismissedIds((prev) => {
			const next = Array.from(new Set([...prev, id]));
			try {
				localStorage.setItem(DISMISSED_KEY, JSON.stringify(next));
			} catch {
				// Ignore storage errors
			}
			return next;
		});
	};

	const activeBroadcasts = (rawBroadcasts || []).filter(
		(b) => !b.dismissible || !dismissedIds.includes(b.id)
	);

	return {
		broadcasts: activeBroadcasts,
		dismiss,
		isLoading,
		error,
		refetch,
	};
}
