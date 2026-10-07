import { atomWithQuery } from "jotai-tanstack-query";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeWorkspaceIdAtom } from "../workspaces/workspace-query.atoms";

export const connectorsAtom = atomWithQuery((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.connectors.all(workspaceId ?? ""),
		enabled: Boolean(workspaceId),
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			if (workspaceId == null) {
				throw new Error("workspaceId is required to fetch connectors");
			}
			return connectorsApiService.getConnectors({
				queryParams: {
					workspace_id: workspaceId,
				},
			});
		},
	};
});
