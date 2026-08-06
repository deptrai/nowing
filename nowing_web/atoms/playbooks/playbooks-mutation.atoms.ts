import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	PlaybookCreateRequest,
	PlaybookInstantiateRequest,
} from "@/contracts/types/playbook.types";
import { playbooksApiService } from "@/lib/apis/playbooks-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

function _invalidateList(workspaceId: number) {
	queryClient.invalidateQueries({ queryKey: ["playbooks", "list", workspaceId] });
}

function invalidateAutomationsList(workspaceId: number) {
	queryClient.invalidateQueries({ queryKey: ["automations", "list", workspaceId] });
}

export const createPlaybookMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (request: PlaybookCreateRequest) => {
		return playbooksApiService.createPlaybook(request);
	},
	onSuccess: (_, _variables) => {
		// Playbooks are workspace-scoped; refresh the list.
		queryClient.invalidateQueries({ queryKey: ["playbooks", "list"] });
		toast.success("Saved as playbook");
	},
	onError: (error: Error) => {
		console.error("Error creating playbook:", error);
		toast.error("Failed to save playbook");
	},
}));

export const instantiatePlaybookMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { playbookId: number; request: PlaybookInstantiateRequest }) => {
		return playbooksApiService.instantiatePlaybook(vars.playbookId, vars.request);
	},
	onSuccess: (automation, variables) => {
		invalidateAutomationsList(variables.request.workspace_id);
		queryClient.invalidateQueries({
			queryKey: cacheKeys.automations.detail(automation.id),
		});
		toast.success("Automation created from playbook");
	},
	onError: (error: Error) => {
		console.error("Error instantiating playbook:", error);
		toast.error("Failed to instantiate playbook");
	},
}));
