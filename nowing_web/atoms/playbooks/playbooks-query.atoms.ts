import { atomFamily } from "jotai-family";
import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { playbooksApiService } from "@/lib/apis/playbooks-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const DEFAULT_LIMIT = 50;
const DEFAULT_OFFSET = 0;

export const playbooksListAtom = atomFamily((vertical: string) =>
	atomWithQuery((get) => {
		const workspaceId = get(activeWorkspaceIdAtom);
		const effectiveVertical = vertical === "all" ? undefined : vertical;

		return {
			queryKey: cacheKeys.playbooks.list(
				Number(workspaceId ?? 0),
				DEFAULT_LIMIT,
				DEFAULT_OFFSET,
				effectiveVertical
			),
			enabled: !!workspaceId,
			staleTime: 60 * 1000,
			queryFn: async () => {
				if (!workspaceId) {
					return { items: [], total: 0 };
				}
				return playbooksApiService.listPlaybooks({
					workspace_id: Number(workspaceId),
					limit: DEFAULT_LIMIT,
					offset: DEFAULT_OFFSET,
					vertical: effectiveVertical,
				});
			},
		};
	})
);
