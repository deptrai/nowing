"use client";

import { useQuery } from "@tanstack/react-query";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export function useWorkspaceVertical(workspaceId: number): string {
	const { data: workspace } = useQuery({
		queryKey: [...cacheKeys.workspaces.detail(String(workspaceId))],
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});
	return workspace?.vertical ?? "general";
}
