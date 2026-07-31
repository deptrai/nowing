"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { updateWorkspaceMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { workspacesAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

interface DataRetentionManagerProps {
	workspaceId: number;
	isOwner?: boolean;
	className?: string;
}

export function DataRetentionManager({
	workspaceId,
	isOwner: isOwnerProp,
	className,
}: DataRetentionManagerProps) {
	const t = useTranslations("workspaceSettings");
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

	const { data: workspacesData } = useAtomValue(workspacesAtom);
	const { mutateAsync: updateWorkspace } = useAtomValue(updateWorkspaceMutationAtom);

	const isOwner = useMemo(
		() =>
			isOwnerProp ??
			workspace?.is_owner ??
			workspacesData?.some((w) => w.id === workspaceId && w.is_owner) ??
			undefined,
		[isOwnerProp, workspace, workspacesData, workspaceId]
	);

	const [autoArchive, setAutoArchive] = useState(false);
	const [retentionDays, setRetentionDays] = useState<string>("");
	const [action, setAction] = useState<"archive" | "delete">("archive");
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (workspace) {
			setAutoArchive(workspace.auto_archive_enabled ?? false);
			setRetentionDays(
				workspace.document_retention_days ? String(workspace.document_retention_days) : ""
			);
			setAction((workspace.document_retention_action as "archive" | "delete") ?? "archive");
		}
	}, [workspace]);

	const hasChanges = useMemo(() => {
		if (!workspace) return false;
		const days = retentionDays.trim() === "" ? null : Number(retentionDays);
		return (
			autoArchive !== (workspace.auto_archive_enabled ?? false) ||
			days !== (workspace.document_retention_days ?? null) ||
			action !== (workspace.document_retention_action ?? "archive")
		);
	}, [workspace, autoArchive, retentionDays, action]);

	const handleSave = useCallback(
		async (e?: React.FormEvent) => {
			e?.preventDefault();
			if (!isOwner) {
				toast.error("Only workspace owners can change data retention settings");
				return;
			}

			const days = retentionDays.trim() === "" ? null : Number(retentionDays);
			if (autoArchive && (!Number.isInteger(days) || (days as number) <= 0)) {
				toast.error("Retention days must be a positive integer when auto-archive is enabled");
				return;
			}

			setSaving(true);
			try {
				await updateWorkspace({
					id: workspaceId,
					data: {
						auto_archive_enabled: autoArchive,
						document_retention_days: days,
						document_retention_action: action,
					},
				});
				await refetch();
			} catch (error) {
				console.error("Error saving data retention settings:", error);
				toast.error(error instanceof Error ? error.message : "Failed to save settings");
			} finally {
				setSaving(false);
			}
		},
		[isOwner, workspaceId, autoArchive, retentionDays, action, updateWorkspace, refetch]
	);

	if (isLoading || isOwner === undefined) {
		return (
			<div className={cn("space-y-6", className)}>
				<Skeleton className="h-6 w-48" />
				<Skeleton className="h-4 w-full" />
				<div className="space-y-4">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-10 w-32" />
				</div>
			</div>
		);
	}

	if (isError) {
		return (
			<div className={cn("space-y-2", className)}>
				<p className="text-sm text-destructive">{t("data_retention_description")}</p>
				<Button variant="outline" size="sm" onClick={() => refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	return (
		<section aria-label={t("data_retention_title")} className={cn("space-y-6", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("data_retention_title")}</h2>
				<p className="text-sm text-muted-foreground">{t("data_retention_description")}</p>
			</div>
			<form onSubmit={handleSave} className="space-y-6">
				<div className="flex items-start justify-between gap-4 rounded-lg border p-4">
					<div className="space-y-1">
						<Label htmlFor="auto-archive-enabled">{t("data_retention_auto_archive_label")}</Label>
						<p className="text-xs text-muted-foreground">
							{t("data_retention_auto_archive_description")}
						</p>
					</div>
					<Switch
						id="auto-archive-enabled"
						data-testid="data-retention-auto-archive-switch"
						checked={autoArchive}
						disabled={!isOwner || saving}
						onCheckedChange={setAutoArchive}
					/>
				</div>

				<div className="space-y-2">
					<Label htmlFor="data-retention-days">{t("data_retention_days_label")}</Label>
					<Input
						id="data-retention-days"
						data-testid="data-retention-days-input"
						type="number"
						min={1}
						value={retentionDays}
						disabled={!isOwner || saving}
						onChange={(e) => setRetentionDays(e.target.value)}
						placeholder="30"
					/>
					<p className="text-xs text-muted-foreground">{t("data_retention_days_description")}</p>
				</div>

				<div className="space-y-2">
					<Label htmlFor="data-retention-action">{t("data_retention_action_label")}</Label>
					{/* ponytail: native select keeps options in the DOM so Playwright/assistive tech can read the selected label without depending on Radix Select content mounting. */}
					<select
						id="data-retention-action"
						data-testid="data-retention-action-select"
						disabled={!isOwner || saving}
						value={action}
						onChange={(e) => setAction(e.target.value as "archive" | "delete")}
						className={cn(
							"flex h-9 w-[200px] rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
						)}
					>
						<option value="archive">{t("data_retention_action_archive")}</option>
						<option value="delete">{t("data_retention_action_delete")}</option>
					</select>
					<p className="text-xs text-muted-foreground">{t("data_retention_action_description")}</p>
				</div>

				<div className="flex justify-end">
					<Button
						type="submit"
						disabled={!hasChanges || saving || !isOwner}
						data-testid="data-retention-save-button"
					>
						{saving ? "Saving..." : t("data_retention_save")}
					</Button>
				</div>
			</form>
		</section>
	);
}
