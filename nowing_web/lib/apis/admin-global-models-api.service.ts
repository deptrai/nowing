import {
	type AdminGlobalConnectionCreateRequest,
	type AdminGlobalConnectionRead,
	type AdminGlobalConnectionUpdateRequest,
	type AdminGlobalModelPreviewRead,
	type AdminGlobalModelRead,
	type AdminGlobalModelsBulkUpdateRequest,
	type AdminGlobalModelTestPreviewRequest,
	type AdminGlobalModelTestRequest,
	type AdminGlobalModelUpdateRequest,
	adminGlobalConnectionCreateRequest,
	adminGlobalConnectionListResponse,
	adminGlobalConnectionRead,
	adminGlobalConnectionUpdateRequest,
	adminGlobalModelPreviewListResponse,
	adminGlobalModelRead,
	adminGlobalModelsBulkUpdateRequest,
	adminGlobalModelTestPreviewRequest,
	adminGlobalModelTestRequest,
	adminGlobalModelUpdateRequest,
} from "@/contracts/types/admin-global-model-connections.types";
import {
	type VerifyConnectionResponse,
	verifyConnectionResponse,
} from "@/contracts/types/model-connections.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class AdminGlobalModelsApiService {
	getAdminGlobalConnections = async (): Promise<AdminGlobalConnectionRead[]> => {
		return baseApiService.get(
			"/api/v1/admin/global-model-connections",
			adminGlobalConnectionListResponse
		);
	};

	createAdminGlobalConnection = async (
		request: AdminGlobalConnectionCreateRequest
	): Promise<AdminGlobalConnectionRead> => {
		const parsed = adminGlobalConnectionCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			"/api/v1/admin/global-model-connections",
			adminGlobalConnectionRead,
			{
				body: parsed.data,
			}
		);
	};

	updateAdminGlobalConnection = async (
		id: number,
		request: AdminGlobalConnectionUpdateRequest
	): Promise<AdminGlobalConnectionRead> => {
		const parsed = adminGlobalConnectionUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.put(
			`/api/v1/admin/global-model-connections/${id}`,
			adminGlobalConnectionRead,
			{
				body: parsed.data,
			}
		);
	};

	deleteAdminGlobalConnection = async (id: number): Promise<null> => {
		return baseApiService.delete(`/api/v1/admin/global-model-connections/${id}`, undefined);
	};

	previewAdminGlobalConnectionModels = async (
		request: AdminGlobalConnectionCreateRequest
	): Promise<AdminGlobalModelPreviewRead[]> => {
		const parsed = adminGlobalConnectionCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			"/api/v1/admin/global-model-connections/discover-preview",
			adminGlobalModelPreviewListResponse,
			{
				body: parsed.data,
			}
		);
	};

	testAdminGlobalPreviewModel = async (
		request: AdminGlobalModelTestPreviewRequest
	): Promise<VerifyConnectionResponse> => {
		const parsed = adminGlobalModelTestPreviewRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			"/api/v1/admin/global-model-connections/test-preview",
			verifyConnectionResponse,
			{
				body: parsed.data,
			}
		);
	};

	discoverAdminGlobalConnectionModels = async (
		id: number
	): Promise<AdminGlobalModelPreviewRead[]> => {
		return baseApiService.post(
			`/api/v1/admin/global-model-connections/${id}/discover`,
			adminGlobalModelPreviewListResponse
		);
	};

	testAdminGlobalConnectionModel = async (
		id: number,
		request: AdminGlobalModelTestRequest
	): Promise<VerifyConnectionResponse> => {
		const parsed = adminGlobalModelTestRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.post(
			`/api/v1/admin/global-model-connections/${id}/test`,
			verifyConnectionResponse,
			{
				body: parsed.data,
			}
		);
	};

	updateAdminGlobalModel = async (
		modelId: number,
		request: AdminGlobalModelUpdateRequest
	): Promise<AdminGlobalModelRead> => {
		const parsed = adminGlobalModelUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.put(
			`/api/v1/admin/global-model-connections/models/${modelId}`,
			adminGlobalModelRead,
			{
				body: parsed.data,
			}
		);
	};

	bulkUpdateAdminGlobalModels = async (
		connectionId: number,
		request: AdminGlobalModelsBulkUpdateRequest
	): Promise<AdminGlobalConnectionRead> => {
		const parsed = adminGlobalModelsBulkUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(parsed.error.issues.map((issue) => issue.message).join(", "));
		}
		return baseApiService.patch(
			`/api/v1/admin/global-model-connections/${connectionId}/models`,
			adminGlobalConnectionRead,
			{
				body: parsed.data,
			}
		);
	};
}

export const adminGlobalModelsApiService = new AdminGlobalModelsApiService();
