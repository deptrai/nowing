import { atomWithMutation } from "jotai-tanstack-query";
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
			toast.success("Role created successfully");
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
			toast.error("Failed to create role");
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
			toast.success("Role updated successfully");
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
			toast.error("Failed to update role");
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
			toast.success("Role deleted successfully");
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
			toast.error("Failed to delete role");
		},
	};
});
