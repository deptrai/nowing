"use client";

import { useCallback, useEffect, useState } from "react";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import { dshApiService } from "@/lib/apis/dsh-api.service";

const POLL_INTERVAL_MS = 5_000;

export interface UseDshMissionControlReturn {
	latestMission: DshMission | null;
	missionControl: DshMissionControl | null;
	loading: boolean;
	error: string | null;
}

export function useDshMissionControl(workspaceId?: number | string): UseDshMissionControlReturn {
	const [latestMission, setLatestMission] = useState<DshMission | null>(null);
	const [missionControl, setMissionControl] = useState<DshMissionControl | null>(null);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	const fetchMissions = useCallback(async () => {
		if (!workspaceId) return;
		try {
			const list = await dshApiService.listMissions(workspaceId, { hours: 24, limit: 1 });
			const mission = list.items[0] ?? null;
			setLatestMission(mission);

			if (mission) {
				const control = await dshApiService.getMissionControl(workspaceId, mission.id);
				setMissionControl(control);
			} else {
				setMissionControl(null);
			}
			setError(null);
		} catch (err) {
			console.error("Error fetching DSH mission control:", err);
			setError("Không thể tải trạng thái nhiệm vụ.");
		} finally {
			setLoading(false);
		}
	}, [workspaceId]);

	useEffect(() => {
		void fetchMissions();
		const interval = setInterval(() => void fetchMissions(), POLL_INTERVAL_MS);
		return () => clearInterval(interval);
	}, [fetchMissions]);

	return { latestMission, missionControl, loading, error };
}
