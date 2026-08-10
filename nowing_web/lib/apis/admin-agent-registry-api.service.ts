import {
	type AdminAgentConfigCreateRequest,
	type AdminAgentConfigRead,
	type AdminAgentConfigUpdateRequest,
	adminAgentConfigCreateRequest,
	adminAgentConfigListResponse,
	adminAgentConfigRead,
	adminAgentConfigUpdateRequest,
} from "@/contracts/types/admin-agent-registry.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class AdminAgentRegistryApiService {
	listAgents = async (clientId?: string): Promise<AdminAgentConfigRead[]> => {
		const query = clientId ? `?client_id=${encodeURIComponent(clientId)}` : "";
		return baseApiService.get(`/api/v1/admin/agent-registry${query}`, adminAgentConfigListResponse);
	};

	createAgent = async (request: AdminAgentConfigCreateRequest): Promise<AdminAgentConfigRead> => {
		const parsed = adminAgentConfigCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post("/api/v1/admin/agent-registry", adminAgentConfigRead, {
			body: parsed.data,
		});
	};

	updateAgent = async (
		id: string,
		request: AdminAgentConfigUpdateRequest
	): Promise<AdminAgentConfigRead> => {
		const parsed = adminAgentConfigUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.patch(`/api/v1/admin/agent-registry/${id}`, adminAgentConfigRead, {
			body: parsed.data,
		});
	};

	deleteAgent = async (id: string): Promise<null> => {
		return baseApiService.delete(`/api/v1/admin/agent-registry/${id}`, undefined);
	};
}

export const adminAgentRegistryApiService = new AdminAgentRegistryApiService();
