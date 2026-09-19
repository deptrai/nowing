import { atomWithMutation } from "jotai-tanstack-query";
import { translateToast } from "@/lib/i18n-toast";
import { toast } from "sonner";
import type {
	CreateRoleRequest,
	CreateRoleResponse,
	DeleteRoleRequest,
	DeleteRoleResponse,
	UpdateRoleRequest,
	UpdateRoleResponse,
} from "@/contracts/types/roles.types";
import { rolesApiService } from "@/lib/apis/roles-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createRoleMutationAtom = atomWithMutation(() => {
	return {
		meta: { suppressGlobalErrorToast: true },
		mutationFn: async (request: CreateRoleRequest) => {
			return rolesApiService.createRole(request);
		},
		onSuccess: (_: CreateRoleResponse, request: CreateRoleRequest) => {
			toast.success(translateToast("toast.role_created"));
			if (!request?.workspace_id) return;
			const wsId = request.workspace_id.toString();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.myAccess(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(wsId),
			});
		},
		onError: () => {
			toast.error(translateToast("toast.role_create_failed"));
		},
	};
});

export const updateRoleMutationAtom = atomWithMutation(() => {
	return {
		meta: { suppressGlobalErrorToast: true },
		mutationFn: async (request: UpdateRoleRequest) => {
			return rolesApiService.updateRole(request);
		},
		onSuccess: (_: UpdateRoleResponse, request: UpdateRoleRequest) => {
			toast.success(translateToast("toast.role_updated"));
			if (!request?.workspace_id) return;
			const wsId = request.workspace_id.toString();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.byId(wsId, request.role_id.toString()),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.myAccess(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(wsId),
			});
		},
		onError: () => {
			toast.error(translateToast("toast.role_update_failed"));
		},
	};
});

export const deleteRoleMutationAtom = atomWithMutation(() => {
	return {
		meta: { suppressGlobalErrorToast: true },
		mutationFn: async (request: DeleteRoleRequest) => {
			return rolesApiService.deleteRole(request);
		},
		onSuccess: (_: DeleteRoleResponse, request: DeleteRoleRequest) => {
			toast.success(translateToast("toast.role_deleted"));
			if (!request?.workspace_id) return;
			const wsId = request.workspace_id.toString();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.myAccess(wsId),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(wsId),
			});
		},
		onError: () => {
			toast.error(translateToast("toast.role_delete_failed"));
		},
	};
});
