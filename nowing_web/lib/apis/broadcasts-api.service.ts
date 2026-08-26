"use client";

import type {
	BroadcastActiveRead,
	BroadcastCreate,
	BroadcastListResponse,
	BroadcastRead,
	BroadcastUpdate,
} from "@/contracts/types/broadcasts.types";
import { baseApiService } from "./base-api.service";

class BroadcastsApiService {
	// Superadmin endpoints
	listAdmin = async (): Promise<BroadcastListResponse> => {
		return baseApiService.get<BroadcastListResponse>("/api/v1/admin/broadcasts", undefined);
	};

	create = async (payload: BroadcastCreate): Promise<BroadcastRead> => {
		return baseApiService.post<BroadcastRead>("/api/v1/admin/broadcasts", undefined, {
			body: payload,
		});
	};

	update = async (broadcastId: string, payload: BroadcastUpdate): Promise<BroadcastRead> => {
		return baseApiService.patch<BroadcastRead>(
			`/api/v1/admin/broadcasts/${broadcastId}`,
			undefined,
			{ body: payload }
		);
	};

	delete = async (broadcastId: string): Promise<void> => {
		return baseApiService.delete<void>(`/api/v1/admin/broadcasts/${broadcastId}`, undefined);
	};

	// Public active broadcast feed
	listActive = async (workspaceId?: number | null): Promise<BroadcastActiveRead[]> => {
		const params = new URLSearchParams();
		if (workspaceId !== undefined && workspaceId !== null) {
			params.set("workspace_id", String(workspaceId));
		}
		const query = params.toString();
		const url = `/api/v1/broadcasts/active${query ? `?${query}` : ""}`;
		return baseApiService.get<BroadcastActiveRead[]>(url);
	};
}

export const broadcastsApiService = new BroadcastsApiService();
