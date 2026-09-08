"use client";

import { useState, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { RetentionPolicy, RetentionAction } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface RetentionPolicyPanelProps {
	workspaceId: number;
	retention: RetentionPolicy | undefined;
	canEdit: boolean;
	onSaved: () => void;
	className?: string;
}

export function RetentionPolicyPanel({
	workspaceId,
	retention,
	canEdit,
	onSaved,
	className,
}: RetentionPolicyPanelProps) {
	const t = useTranslations("governance");

	const [docAutoArchive, setDocAutoArchive] = useState(retention?.auto_archive_enabled ?? false);
	const [docDays, setDocDays] = useState(String(retention?.document_retention_days ?? ""));
	const [docAction, setDocAction] = useState<RetentionAction>(
		retention?.document_retention_action ?? "archive"
	);
	const [memAutoArchive, setMemAutoArchive] = useState(
		retention?.memory_auto_archive_enabled ?? false
	);
	const [memDays, setMemDays] = useState(String(retention?.memory_retention_days ?? ""));
	const [memAction, setMemAction] = useState<RetentionAction>(
		retention?.memory_retention_action ?? "archive"
	);
	const [saving, setSaving] = useState(false);

	const hasChanges = useMemo(() => {
		if (!retention) return false;
		const d = docDays.trim() === "" ? null : Number(docDays);
		const m = memDays.trim() === "" ? null : Number(memDays);
		return (
			docAutoArchive !== (retention.auto_archive_enabled ?? false) ||
			d !== (retention.document_retention_days ?? null) ||
			docAction !== (retention.document_retention_action ?? "archive") ||
			memAutoArchive !== (retention.memory_auto_archive_enabled ?? false) ||
			m !== (retention.memory_retention_days ?? null) ||
			memAction !== (retention.memory_retention_action ?? "archive")
		);
	}, [retention, docAutoArchive, docDays, docAction, memAutoArchive, memDays, memAction]);

	const handleSave = useCallback(
		async (e?: React.FormEvent) => {
			e?.preventDefault();
			if (!canEdit) {
				toast.error(t("errors.not_owner"));
				return;
			}

			const d = docDays.trim() === "" ? null : Number(docDays);
			if (docAutoArchive && (!Number.isInteger(d) || d! <= 0)) {
				toast.error(t("retention.doc_days_positive"));
				return;
			}

			const m = memDays.trim() === "" ? null : Number(memDays);
			if (memAutoArchive && (!Number.isInteger(m) || m! <= 0)) {
				toast.error(t("retention.mem_days_positive"));
				return;
			}

			setSaving(true);
			try {
				await governanceApiService.updateRetentionPolicy(workspaceId, {
					auto_archive_enabled: docAutoArchive,
					document_retention_days: d,
					document_retention_action: docAction,
					memory_auto_archive_enabled: memAutoArchive,
					memory_retention_days: m,
					memory_retention_action: memAction,
				});
				onSaved();
				toast.success(t("retention.saved"));
			} catch (error) {
				console.error("Error saving retention policy:", error);
				toast.error(error instanceof Error ? error.message : t("errors.save_failed"));
			} finally {
				setSaving(false);
			}
		},
		[
			canEdit,
			workspaceId,
			docAutoArchive,
			docDays,
			docAction,
			memAutoArchive,
			memDays,
			memAction,
			onSaved,
			t,
		]
	);

	return (
		<section aria-label={t("retention.title")} className={cn("space-y-6", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("retention.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("retention.description")}</p>
			</div>

			<form onSubmit={handleSave} className="space-y-6">
				<div className="rounded-lg border p-4 space-y-4">
					<h3 className="text-sm font-medium">{t("retention.document_section")}</h3>

					<div className="flex items-start justify-between gap-4">
						<div className="space-y-1">
							<Label htmlFor="doc-auto-archive">{t("retention.auto_archive_label")}</Label>
							<p className="text-xs text-muted-foreground">
								{t("retention.auto_archive_description")}
							</p>
						</div>
						<Switch
							id="doc-auto-archive"
							checked={docAutoArchive}
							disabled={!canEdit || saving}
							onCheckedChange={setDocAutoArchive}
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="doc-retention-days">{t("retention.days_label")}</Label>
						<Input
							id="doc-retention-days"
							type="number"
							value={docDays}
							disabled={!canEdit || saving}
							onChange={(e) => setDocDays(e.target.value)}
							placeholder="365"
						/>
						<p className="text-xs text-muted-foreground">{t("retention.days_description")}</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="doc-retention-action">{t("retention.action_label")}</Label>
						<select
							id="doc-retention-action"
							disabled={!canEdit || saving}
							value={docAction}
							onChange={(e) => setDocAction(e.target.value as RetentionAction)}
							className={cn(
								"flex h-9 w-[200px] rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
							)}
						>
							<option value="archive">{t("retention.action_archive")}</option>
							<option value="delete">{t("retention.action_delete")}</option>
						</select>
						<p className="text-xs text-muted-foreground">{t("retention.action_description")}</p>
					</div>
				</div>

				<div className="rounded-lg border p-4 space-y-4">
					<h3 className="text-sm font-medium">{t("retention.memory_section")}</h3>

					<div className="flex items-start justify-between gap-4">
						<div className="space-y-1">
							<Label htmlFor="mem-auto-archive">
								{t("retention.memory_auto_archive_label")}
							</Label>
							<p className="text-xs text-muted-foreground">
								{t("retention.memory_auto_archive_description")}
							</p>
						</div>
						<Switch
							id="mem-auto-archive"
							checked={memAutoArchive}
							disabled={!canEdit || saving}
							onCheckedChange={setMemAutoArchive}
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="mem-retention-days">{t("retention.memory_days_label")}</Label>
						<Input
							id="mem-retention-days"
							type="number"
							value={memDays}
							disabled={!canEdit || saving}
							onChange={(e) => setMemDays(e.target.value)}
							placeholder="365"
						/>
						<p className="text-xs text-muted-foreground">
							{t("retention.memory_days_description")}
						</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="mem-retention-action">{t("retention.memory_action_label")}</Label>
						<select
							id="mem-retention-action"
							disabled={!canEdit || saving}
							value={memAction}
							onChange={(e) => setMemAction(e.target.value as RetentionAction)}
							className={cn(
								"flex h-9 w-[200px] rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
							)}
						>
							<option value="archive">{t("retention.action_archive")}</option>
							<option value="delete">{t("retention.action_delete")}</option>
						</select>
						<p className="text-xs text-muted-foreground">
							{t("retention.memory_action_description")}
						</p>
					</div>
				</div>

				<Button type="submit" disabled={!canEdit || !hasChanges || saving}>
					{saving ? t("retention.saving") : t("retention.save")}
				</Button>
			</form>
		</section>
	);
}
