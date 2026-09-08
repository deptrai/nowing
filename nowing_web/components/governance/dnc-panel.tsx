"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { GovernanceDncRecord, GovernanceDncRecordCreate } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface DncPanelProps {
	workspaceId: number;
	records: GovernanceDncRecord[];
	canEdit: boolean;
	onChanged: () => void;
	className?: string;
}

const recordTypes = ["phone", "email", "domain", "tax_id"] as const;

export function DncPanel({ workspaceId, records, canEdit, onChanged, className }: DncPanelProps) {
	const t = useTranslations("governance");
	const tCommon = useTranslations("common");
	const [open, setOpen] = useState(false);
	const [recordType, setRecordType] = useState<(typeof recordTypes)[number]>("phone");
	const [value, setValue] = useState("");
	const [reason, setReason] = useState("");
	const [deleting, setDeleting] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	const handleAdd = useCallback(
		async (e: React.FormEvent) => {
			e.preventDefault();
			if (!canEdit) return;

			setSaving(true);
			try {
				const payload: GovernanceDncRecordCreate = {
					record_type: recordType,
					value: value.trim(),
					reason: reason.trim() || undefined,
				};
				await governanceApiService.createDncRecord(workspaceId, payload);
				onChanged();
				setOpen(false);
				setValue("");
				setReason("");
				toast.success(t("dnc.saved"));
			} catch (error) {
				console.error("Error adding DNC record:", error);
				toast.error(error instanceof Error ? error.message : t("errors.save_failed"));
			} finally {
				setSaving(false);
			}
		},
		[canEdit, workspaceId, recordType, value, reason, onChanged, t]
	);

	const handleDelete = useCallback(
		async (recordId: string) => {
			if (!canEdit) return;
			setDeleting(recordId);
			try {
				await governanceApiService.deleteDncRecord(workspaceId, recordId);
				onChanged();
				toast.success(t("dnc.deleted"));
			} catch (error) {
				console.error("Error deleting DNC record:", error);
				toast.error(error instanceof Error ? error.message : t("errors.delete_failed"));
			} finally {
				setDeleting(null);
			}
		},
		[canEdit, workspaceId, onChanged, t]
	);

	return (
		<section aria-label={t("dnc.title")} className={cn("space-y-4", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("dnc.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("dnc.description")}</p>
			</div>

			<div className="flex items-center justify-between">
				<Button size="sm" disabled={!canEdit} onClick={() => setOpen(true)}>
					{t("dnc.add")}
				</Button>
			</div>

			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>{t("dnc.record_type")}</TableHead>
						<TableHead>{t("dnc.value")}</TableHead>
						<TableHead>{t("dnc.reason")}</TableHead>
						<TableHead>{t("dnc.source")}</TableHead>
						<TableHead>{t("dnc.global")}</TableHead>
						<TableHead className="w-24">{tCommon("actions")}</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{records.length === 0 ? (
						<TableRow>
							<TableCell colSpan={6} className="text-center text-muted-foreground">
								{t("dnc.empty")}
							</TableCell>
						</TableRow>
					) : (
						records.map((record) => (
							<TableRow key={record.id}>
								<TableCell className="font-medium capitalize">{record.record_type}</TableCell>
								<TableCell>{record.value || record.value_hmac}</TableCell>
								<TableCell>{record.reason || "—"}</TableCell>
								<TableCell>{record.source}</TableCell>
								<TableCell>
									{record.superseded_by_global ? (
										<Badge variant="destructive">{t("dnc.superseded_yes")}</Badge>
									) : (
										"—"
									)}
								</TableCell>
								<TableCell>
									<Button
										variant="ghost"
										size="sm"
										disabled={!canEdit || deleting === record.id}
										onClick={() => handleDelete(record.id)}
									>
										{tCommon("delete")}
									</Button>
								</TableCell>
							</TableRow>
						))
					)}
				</TableBody>
			</Table>

			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>{t("dnc.add_title")}</DialogTitle>
						<DialogDescription>{t("dnc.add_description")}</DialogDescription>
					</DialogHeader>
					<form onSubmit={handleAdd} className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="dnc-record-type">{t("dnc.record_type")}</Label>
							<select
								id="dnc-record-type"
								value={recordType}
								onChange={(e) => setRecordType(e.target.value as (typeof recordTypes)[number])}
								className={cn(
									"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
								)}
							>
								{recordTypes.map((type) => (
									<option key={type} value={type}>
										{type}
									</option>
								))}
							</select>
						</div>

						<div className="space-y-2">
							<Label htmlFor="dnc-value">{t("dnc.value")}</Label>
							<Input
								id="dnc-value"
								value={value}
								onChange={(e) => setValue(e.target.value)}
								placeholder={t("dnc.value_placeholder")}
								required
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="dnc-reason">{t("dnc.reason")}</Label>
							<Input
								id="dnc-reason"
								value={reason}
								onChange={(e) => setReason(e.target.value)}
								placeholder={t("dnc.reason_placeholder")}
							/>
						</div>

						<DialogFooter className="gap-2">
							<Button type="button" variant="outline" onClick={() => setOpen(false)}>
								{tCommon("cancel")}
							</Button>
							<Button type="submit" disabled={saving}>
								{saving ? tCommon("save") : tCommon("save")}
							</Button>
						</DialogFooter>
					</form>
				</DialogContent>
			</Dialog>
		</section>
	);
}
