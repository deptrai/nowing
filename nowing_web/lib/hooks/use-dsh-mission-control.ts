"use client";

import { useEffect, useRef, useState } from "react";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import { dshApiService } from "@/lib/apis/dsh-api.service";

const POLL_INTERVAL_MS = 3_000;

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
	const workspaceIdRef = useRef(workspaceId);

	useEffect(() => {
		if (!workspaceId) {
			setLoading(false);
			return;
		}

		// Reset stale data immediately on workspace switch to avoid
		// showing a mission from the previous workspace.
		setLatestMission(null);
		setMissionControl(null);
		setError(null);
		setLoading(true);

		let cancelled = false;
		workspaceIdRef.current = workspaceId;

		const fetchMissions = async () => {
			// If workspace changed while a previous fetch was in flight, drop it.
			if (workspaceIdRef.current !== workspaceId || cancelled) return;
			try {
				const list = await dshApiService.listMissions(workspaceId, {
					status: "running,pending",
					hours: 24,
					limit: 1,
				});
				if (workspaceIdRef.current !== workspaceId || cancelled) return;
				const mission = list.items[0] ?? null;
				setLatestMission(mission);

				if (mission) {
					const control = await dshApiService.getMissionControl(workspaceId, mission.id);
					if (workspaceIdRef.current !== workspaceId || cancelled) return;
					setMissionControl(control);
				} else {
					setMissionControl(null);
				}
				setError(null);
			} catch (err) {
				if (workspaceIdRef.current !== workspaceId || cancelled) return;
				console.error("Error fetching DSH mission control:", err);
				setError("Không thể tải trạng thái nhiệm vụ.");
			} finally {
				if (!cancelled && workspaceIdRef.current === workspaceId) {
					setLoading(false);
				}
			}
		};

		void fetchMissions();
		const interval = setInterval(() => void fetchMissions(), POLL_INTERVAL_MS);
		return () => {
			cancelled = true;
			clearInterval(interval);
		};
	}, [workspaceId]);

	return { latestMission, missionControl, loading, error };
}
