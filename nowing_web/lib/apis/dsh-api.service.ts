import {
	type DshMission,
	type DshMissionControl,
	type DshMissionListResponse,
	type DshMissionRequest,
	dshMissionControlResponseSchema,
	dshMissionListResponseSchema,
	dshMissionRequestSchema,
	dshMissionResponseSchema,
	type ListMissionsParams,
} from "@/contracts/types/dsh.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}`;

class DshApiService {
	listMissions = async (
		workspaceId: number | string,
		params: ListMissionsParams = {}
	): Promise<DshMissionListResponse> => {
		const qs = new URLSearchParams();
		if (params.status) qs.set("status", params.status);
		if (params.hours !== undefined) qs.set("hours", String(params.hours));
		if (params.limit !== undefined) qs.set("limit", String(params.limit));
		if (params.offset !== undefined) qs.set("offset", String(params.offset));

		const query = qs.toString();
		return baseApiService.get(
			`${base(workspaceId)}/dsh/missions${query ? `?${query}` : ""}`,
			dshMissionListResponseSchema
		);
	};

	getMissionControl = async (
		workspaceId: number | string,
		missionId: string
	): Promise<DshMissionControl> => {
		return baseApiService.get(
			`${base(workspaceId)}/dsh/missions/${missionId}/control`,
			dshMissionControlResponseSchema
		);
	};

	downloadDeliverableUrl = (
		workspaceId: number | string,
		missionId: string,
		filename: string
	): string => {
		return `${base(workspaceId)}/dsh/missions/${missionId}/deliverables/${encodeURIComponent(filename)}`;
	};

	createMission = async (
		workspaceId: number | string,
		data: DshMissionRequest
	): Promise<DshMission> => {
		return baseApiService.post(`${base(workspaceId)}/dsh/missions`, dshMissionResponseSchema, {
			body: dshMissionRequestSchema.parse(data),
		});
	};

	resumeMission = async (
		missionId: string
	): Promise<{ mission_id: string; status: string; phase: string }> => {
		return baseApiService.post(`/api/v1/dsh/missions/${missionId}/resume`);
	};

	pauseMission = async (
		missionId: string
	): Promise<{ mission_id: string; status: string; phase: string }> => {
		return baseApiService.post(`/api/v1/dsh/missions/${missionId}/pause`);
	};
}

export const dshApiService = new DshApiService();
