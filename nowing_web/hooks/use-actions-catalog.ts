"use client";

import { useQuery } from "@tanstack/react-query";
import type { ActionCatalog } from "@/contracts/types/action.types";
import { actionsApiService } from "@/lib/apis/actions-api.service";

export function useActionsCatalog(): {
	catalog: ActionCatalog | undefined;
	isLoading: boolean;
	error: Error | null;
} {
	const { data, isLoading, error } = useQuery<ActionCatalog, Error>({
		queryKey: ["actions", "catalog"],
		queryFn: () => actionsApiService.listActions(),
		staleTime: 5 * 60 * 1000,
	});
	return { catalog: data, isLoading, error: error ?? null };
}
