"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { updateWorkspaceApiAccessMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

interface WorkspaceApiAccessControlProps {
	workspaceId: number;
	className?: string;
}

export function WorkspaceApiAccessControl({
	workspaceId,
	className,
}: WorkspaceApiAccessControlProps) {
	const t = useTranslations("settings");
	const {
		data: workspace,
		isLoading,
		isError,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	const { mutateAsync: updateWorkspaceApiAccess } = useAtomValue(
		updateWorkspaceApiAccessMutationAtom
	);
	const [savingApiAccess, setSavingApiAccess] = useState(false);

	const handleApiAccessToggle = useCallback(
		async (enabled: boolean) => {
			try {
				setSavingApiAccess(true);
				await updateWorkspaceApiAccess({
					id: workspaceId,
					api_access_enabled: enabled,
				});
				await refetch();
			} catch (error) {
				console.error("Error updating API access:", error);
				toast.error(error instanceof Error ? error.message : t("api_access_update_failed"));
			} finally {
				setSavingApiAccess(false);
			}
		},
		[refetch, workspaceId, updateWorkspaceApiAccess]
	);

	if (isLoading) {
		return (
			<div
				className={cn(
					"flex flex-col gap-3 md:flex-row md:items-center md:justify-between",
					className
				)}
			>
				<div className="space-y-2">
					<Skeleton className="h-4 w-32" aria-hidden="true" />
					<Skeleton className="h-3 w-56" aria-hidden="true" />
				</div>
				<Skeleton className="h-6 w-11 rounded-full" aria-hidden="true" />
			</div>
		);
	}

	if (isError) {
		return (
			<div
				className={cn(
					"flex flex-col gap-3 md:flex-row md:items-center md:justify-between",
					className
				)}
			>
				<div className="space-y-1">
					<Label>{t("api_key_access")}</Label>
					<p className="text-xs text-destructive">{t("api_access_load_failed")}</p>
				</div>
				<Button variant="outline" size="sm" onClick={() => refetch()}>
					{t("retry")}
				</Button>
			</div>
		);
	}

	return (
		<div
			className={cn(
				"flex flex-col gap-3 md:flex-row md:items-center md:justify-between",
				className
			)}
		>
			<div className="space-y-1">
				<Label htmlFor="api-access-enabled">{t("api_key_access")}</Label>
				<p className="text-xs text-muted-foreground">{t("api_access_desc")}</p>
			</div>
			<Switch
				id="api-access-enabled"
				checked={!!workspace?.api_access_enabled}
				disabled={savingApiAccess}
				onCheckedChange={handleApiAccessToggle}
			/>
		</div>
	);
}
