"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { WorkspaceStatus } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface WorkspaceStatusPanelProps {
	workspaceId: number;
	status: WorkspaceStatus | undefined;
	canEdit: boolean;
	onChanged: () => void;
	className?: string;
}

export function WorkspaceStatusPanel({
	workspaceId,
	status,
	canEdit,
	onChanged,
	className,
}: WorkspaceStatusPanelProps) {
	const t = useTranslations("governance");
	const tCommon = useTranslations("common");
	const [saving, setSaving] = useState(false);

	const isArchived = status?.archived_at !== null && status?.archived_at !== undefined;
	const scrapePaused = status?.scrape_paused_at !== null && status?.scrape_paused_at !== undefined;

	const handleArchive = useCallback(async () => {
		if (!canEdit) return;
		setSaving(true);
		try {
			await governanceApiService.archiveWorkspace(workspaceId);
			onChanged();
			toast.success(t("workspace_status.archived"));
		} catch (error) {
			console.error("Error archiving workspace:", error);
			toast.error(error instanceof Error ? error.message : t("errors.action_failed"));
		} finally {
			setSaving(false);
		}
	}, [canEdit, workspaceId, onChanged, t]);

	const handleRestore = useCallback(async () => {
		if (!canEdit) return;
		setSaving(true);
		try {
			await governanceApiService.restoreWorkspace(workspaceId);
			onChanged();
			toast.success(t("workspace_status.restored"));
		} catch (error) {
			console.error("Error restoring workspace:", error);
			toast.error(error instanceof Error ? error.message : t("errors.action_failed"));
		} finally {
			setSaving(false);
		}
	}, [canEdit, workspaceId, onChanged, t]);

	return (
		<section aria-label={t("workspace_status.title")} className={cn("space-y-4", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("workspace_status.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("workspace_status.description")}</p>
			</div>

			<div className="grid gap-4 md:grid-cols-2">
				<Card>
					<CardHeader>
						<CardTitle className="text-base flex items-center gap-2">
							{isArchived ? (
								<>
									<AlertTriangle className="h-4 w-4 text-destructive" />
									{t("workspace_status.archived_title")}
								</>
							) : (
								<>
									<CheckCircle2 className="h-4 w-4 text-emerald-500" />
									{t("workspace_status.active_title")}
								</>
							)}
						</CardTitle>
						<CardDescription>
							{isArchived
								? t("workspace_status.archived_description")
								: t("workspace_status.active_description")}
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="flex items-center gap-2">
							<span className="text-sm font-medium">{t("workspace_status.state_label")}:</span>
							<Badge variant={isArchived ? "destructive" : "default"}>
								{isArchived ? t("workspace_status.archived") : t("workspace_status.active")}
							</Badge>
						</div>
						{isArchived && (
							<p className="text-xs text-muted-foreground mt-2">
								{t("workspace_status.archived_at")}:{" "}
								{status?.archived_at
									? new Date(status.archived_at).toLocaleString()
									: "—"}
							</p>
						)}
					</CardContent>
					<CardFooter>
						<Button
							variant={isArchived ? "default" : "destructive"}
							disabled={!canEdit || saving}
							onClick={isArchived ? handleRestore : handleArchive}
						>
							{saving
								? tCommon("save")
								: isArchived
									? t("workspace_status.restore")
									: t("workspace_status.archive")}
						</Button>
					</CardFooter>
				</Card>

				<Card>
					<CardHeader>
						<CardTitle className="text-base flex items-center gap-2">
							{scrapePaused ? (
								<>
									<AlertTriangle className="h-4 w-4 text-destructive" />
									{t("workspace_status.scrape_paused_title")}
								</>
							) : (
								<>
									<CheckCircle2 className="h-4 w-4 text-emerald-500" />
									{t("workspace_status.scrape_ok_title")}
								</>
							)}
						</CardTitle>
						<CardDescription>
							{scrapePaused
								? t("workspace_status.scrape_paused_description")
								: t("workspace_status.scrape_ok_description")}
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="flex items-center gap-2">
							<span className="text-sm font-medium">{t("workspace_status.scrape_label")}:</span>
							<Badge variant={scrapePaused ? "destructive" : "secondary"}>
								{scrapePaused ? t("workspace_status.paused") : t("workspace_status.active")}
							</Badge>
						</div>
						{scrapePaused && (
							<p className="text-xs text-muted-foreground mt-2">
								{t("workspace_status.scrape_paused_at")}:{" "}
								{status?.scrape_paused_at
									? new Date(status.scrape_paused_at).toLocaleString()
									: "—"}
							</p>
						)}
					</CardContent>
				</Card>
			</div>
		</section>
	);
}
