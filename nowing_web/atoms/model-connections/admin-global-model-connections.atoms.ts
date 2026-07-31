import { atomWithMutation, atomWithQuery } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	AdminGlobalConnectionCreateRequest,
	AdminGlobalConnectionRead,
	AdminGlobalConnectionUpdateRequest,
	AdminGlobalModelPreviewRead,
	AdminGlobalModelsBulkUpdateRequest,
	AdminGlobalModelTestPreviewRequest,
	AdminGlobalModelTestRequest,
	AdminGlobalModelUpdateRequest,
} from "@/contracts/types/admin-global-model-connections.types";
import type { VerifyConnectionResponse } from "@/contracts/types/model-connections.types";
import { adminGlobalModelsApiService } from "@/lib/apis/admin-global-models-api.service";
import { isAuthenticated } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

function invalidateAdminGlobalConnections() {
	queryClient.invalidateQueries({
		queryKey: cacheKeys.admin.globalModelConnections(),
	});
}

export const adminGlobalModelConnectionsAtom = atomWithQuery(() => ({
	queryKey: cacheKeys.admin.globalModelConnections(),
	enabled: isAuthenticated(),
	staleTime: 5 * 60 * 1000,
	queryFn: () => adminGlobalModelsApiService.getAdminGlobalConnections(),
}));

export const createAdminGlobalConnectionMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "create"],
	mutationFn: (request: AdminGlobalConnectionCreateRequest) =>
		adminGlobalModelsApiService.createAdminGlobalConnection(request),
	onSuccess: () => {
		toast.success("Global connection created");
		invalidateAdminGlobalConnections();
	},
	onError: (error: Error) => toast.error(error.message || "Failed to create global connection"),
}));

export const updateAdminGlobalConnectionMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "update"],
	mutationFn: ({ id, data }: { id: number; data: AdminGlobalConnectionUpdateRequest }) =>
		adminGlobalModelsApiService.updateAdminGlobalConnection(id, data),
	onSuccess: (connection: AdminGlobalConnectionRead) => {
		toast.success("Global connection updated");
		queryClient.setQueryData<AdminGlobalConnectionRead[]>(
			cacheKeys.admin.globalModelConnections(),
			(current = []) =>
				current.some((item) => item.id === connection.id)
					? current.map((item) => (item.id === connection.id ? connection : item))
					: [...current, connection]
		);
		invalidateAdminGlobalConnections();
	},
	onError: (error: Error) => toast.error(error.message || "Failed to update global connection"),
}));

export const deleteAdminGlobalConnectionMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "delete"],
	mutationFn: (id: number) => adminGlobalModelsApiService.deleteAdminGlobalConnection(id),
	onSuccess: () => {
		toast.success("Global connection deleted");
		invalidateAdminGlobalConnections();
	},
	onError: (error: Error) => toast.error(error.message || "Failed to delete global connection"),
}));

export const previewAdminGlobalConnectionModelsMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "discover-preview"],
	mutationFn: (request: AdminGlobalConnectionCreateRequest) =>
		adminGlobalModelsApiService.previewAdminGlobalConnectionModels(request),
	onSuccess: (models: AdminGlobalModelPreviewRead[]) => {
		toast.success(models.length ? `${models.length} models discovered` : "No models discovered");
	},
	onError: (error: Error) => toast.error(error.message || "Failed to discover models"),
}));

export const testAdminGlobalConnectionPreviewMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "test-preview"],
	mutationFn: (request: AdminGlobalModelTestPreviewRequest) =>
		adminGlobalModelsApiService.testAdminGlobalPreviewModel(request),
	onSuccess: (result: VerifyConnectionResponse) => {
		if (result.ok) {
			toast.success("Model test succeeded");
		} else {
			toast.error(result.message || "Model test failed");
		}
	},
	onError: (error: Error) => toast.error(error.message || "Failed to test model"),
}));

export const discoverAdminGlobalConnectionModelsMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "discover"],
	mutationFn: (id: number) => adminGlobalModelsApiService.discoverAdminGlobalConnectionModels(id),
	onSuccess: (models: AdminGlobalModelPreviewRead[]) => {
		toast.success(models.length ? `${models.length} models discovered` : "No models discovered");
	},
	onError: (error: Error) => toast.error(error.message || "Failed to discover models"),
}));

export const testAdminGlobalConnectionModelMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "test"],
	mutationFn: ({ id, data }: { id: number; data: AdminGlobalModelTestRequest }) =>
		adminGlobalModelsApiService.testAdminGlobalConnectionModel(id, data),
	onSuccess: (result: VerifyConnectionResponse) => {
		if (result.ok) {
			toast.success("Model test succeeded");
		} else {
			toast.error(result.message || "Model test failed");
		}
	},
	onError: (error: Error) => toast.error(error.message || "Failed to test model"),
}));

export const updateAdminGlobalModelMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "update-model"],
	mutationFn: ({ id, data }: { id: number; data: AdminGlobalModelUpdateRequest }) =>
		adminGlobalModelsApiService.updateAdminGlobalModel(id, data),
	onSuccess: () => {
		toast.success("Model updated");
		invalidateAdminGlobalConnections();
	},
	onError: (error: Error) => toast.error(error.message || "Failed to update model"),
}));

export const bulkUpdateAdminGlobalModelsMutationAtom = atomWithMutation(() => ({
	mutationKey: ["admin", "global-model-connections", "bulk-update-models"],
	mutationFn: ({
		connectionId,
		data,
	}: {
		connectionId: number;
		data: AdminGlobalModelsBulkUpdateRequest;
	}) => adminGlobalModelsApiService.bulkUpdateAdminGlobalModels(connectionId, data),
	onSuccess: (connection: AdminGlobalConnectionRead) => {
		toast.success("Models updated");
		queryClient.setQueryData<AdminGlobalConnectionRead[]>(
			cacheKeys.admin.globalModelConnections(),
			(current = []) =>
				current.some((item) => item.id === connection.id)
					? current.map((item) => (item.id === connection.id ? connection : item))
					: [...current, connection]
		);
		invalidateAdminGlobalConnections();
	},
	onError: (error: Error) => toast.error(error.message || "Failed to update models"),
}));
