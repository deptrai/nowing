"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type {
	RightToDeleteRequest,
	RightToDeleteResponse,
} from "@/contracts/types/governance.types";
import { MemorySourceType } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface RightToDeletePanelProps {
	workspaceId: number;
	canEdit: boolean;
	className?: string;
}

const memorySourceTypes: MemorySourceType[] = [
	"document",
	"chat_message",
	"scraper_run",
	"manual",
	"signal",
	"lead",
	"lead_score",
	"enrichment",
	"crm_connection",
	"crm_sync",
	"sequence_event",
	"outcome_event",
];

export function RightToDeletePanel({ workspaceId, canEdit, className }: RightToDeletePanelProps) {
	const t = useTranslations("governance");
	const tCommon = useTranslations("common");
	const [mode, setMode] = useState<"single" | "bulk">("single");
	const [memoryId, setMemoryId] = useState("");
	const [sourceType, setSourceType] = useState<MemorySourceType>("manual");
	const [sourceId, setSourceId] = useState("");
	const [sourceEntityType, setSourceEntityType] = useState("");
	const [createdBefore, setCreatedBefore] = useState("");
	const [createdAfter, setCreatedAfter] = useState("");
	const [reason, setReason] = useState("");
	const [dryRunResult, setDryRunResult] = useState<RightToDeleteResponse | null>(null);
	const [activeJobId, setActiveJobId] = useState<string | null>(null);
	const [confirmOpen, setConfirmOpen] = useState(false);
	const [saving, setSaving] = useState(false);

	const buildRequest = useCallback((): RightToDeleteRequest => {
		const base = {
			reason: reason.trim() || t("right_to_delete.default_reason"),
		};
		if (mode === "single") {
			return {
				type: "single_memory",
				memory_id: Number(memoryId) || 0,
				dry_run: false,
				...base,
			};
		}
		return {
			type: "bulk",
			source_type: sourceType,
			source_id: sourceId.trim() === "" ? null : Number(sourceId),
			source_entity_type: sourceEntityType.trim() === "" ? null : sourceEntityType.trim(),
			created_before: createdBefore ? new Date(createdBefore).toISOString() : null,
			created_after: createdAfter ? new Date(createdAfter).toISOString() : null,
			dry_run: false,
			...base,
		};
	}, [
		mode,
		memoryId,
		sourceType,
		sourceId,
		sourceEntityType,
		createdBefore,
		createdAfter,
		reason,
		t,
	]);

	const handleDryRun = useCallback(async () => {
		const req = buildRequest();
		req.dry_run = true;
		setSaving(true);
		try {
			const res = await governanceApiService.rightToDelete(workspaceId, req);
			setDryRunResult(res);
		} catch (error) {
			console.error("Error during right-to-delete dry run:", error);
			toast.error(error instanceof Error ? error.message : t("errors.dry_run_failed"));
		} finally {
			setSaving(false);
		}
	}, [buildRequest, workspaceId, t]);

	const handleExecute = useCallback(async () => {
		if (!canEdit) return;
		const req = buildRequest();
		setSaving(true);
		try {
			const res = await governanceApiService.rightToDelete(workspaceId, req);
			if (res.dry_run) {
				setDryRunResult(res);
				setConfirmOpen(true);
			} else if (res.job_id) {
				setActiveJobId(res.job_id);
				toast.success(t("right_to_delete.queued", { jobId: res.job_id }));
				setDryRunResult(null);
				setConfirmOpen(false);
			} else {
				toast.success(t("right_to_delete.deleted", { count: res.affected_count }));
				setDryRunResult(null);
				setConfirmOpen(false);
			}
		} catch (error) {
			console.error("Error during right-to-delete:", error);
			toast.error(error instanceof Error ? error.message : t("errors.action_failed"));
		} finally {
			setSaving(false);
		}
	}, [buildRequest, canEdit, workspaceId, t]);

	const [jobStatus, setJobStatus] = useState<{
		status: string;
		processed: number;
		total: number;
		affected: number;
		error_count: number;
		cancelable: boolean;
	} | null>(null);

	useEffect(() => {
		if (!activeJobId) {
			setJobStatus(null);
			return;
		}
		let cancelled = false;
		const poll = async () => {
			try {
				const res = await governanceApiService.getBulkOpJob(workspaceId, activeJobId);
				if (cancelled) return;
				setJobStatus({
					status: res.status,
					processed: res.processed_count,
					total: res.total_count,
					affected: res.affected_count,
					error_count: res.error_count,
					cancelable: res.cancelable,
				});
				if (res.status === "completed" || res.status === "failed" || res.status === "cancelled") {
					if (res.status === "completed") {
						toast.success(t("right_to_delete.completed", { count: res.affected_count }));
					}
					setActiveJobId(null);
				}
			} catch (err) {
				if (cancelled) return;
				console.error("Bulk job poll failed:", err);
				setJobStatus(null);
				setActiveJobId(null);
			}
		};
		poll();
		const timer = setInterval(poll, 3000);
		return () => {
			cancelled = true;
			clearInterval(timer);
		};
	}, [activeJobId, workspaceId, t]);

	const handleCancelJob = useCallback(async () => {
		if (!activeJobId) return;
		setSaving(true);
		try {
			await governanceApiService.cancelBulkOpJob(workspaceId, activeJobId);
			toast.success(t("right_to_delete.cancelled"));
			setActiveJobId(null);
			setJobStatus(null);
		} catch (error) {
			console.error("Error cancelling bulk job:", error);
			toast.error(error instanceof Error ? error.message : t("errors.action_failed"));
		} finally {
			setSaving(false);
		}
	}, [activeJobId, workspaceId, t]);

	return (
		<section aria-label={t("right_to_delete.title")} className={cn("space-y-4", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("right_to_delete.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("right_to_delete.description")}</p>
			</div>

			<Card>
				<CardHeader>
					<CardTitle className="text-base">{t("right_to_delete.request_title")}</CardTitle>
					<CardDescription>{t("right_to_delete.request_description")}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="flex gap-2">
						<Button
							type="button"
							variant={mode === "single" ? "default" : "outline"}
							size="sm"
							onClick={() => {
								setMode("single");
								setDryRunResult(null);
							}}
						>
							{t("right_to_delete.single_memory")}
						</Button>
						<Button
							type="button"
							variant={mode === "bulk" ? "default" : "outline"}
							size="sm"
							onClick={() => {
								setMode("bulk");
								setDryRunResult(null);
							}}
						>
							{t("right_to_delete.bulk")}
						</Button>
					</div>

					{mode === "single" ? (
						<div className="space-y-2">
							<Label htmlFor="rtd-memory-id">{t("right_to_delete.memory_id")}</Label>
							<Input
								id="rtd-memory-id"
								type="number"
								value={memoryId}
								onChange={(e) => setMemoryId(e.target.value)}
								placeholder="12345"
							/>
						</div>
					) : (
						<div className="space-y-4">
							<div className="space-y-2">
								<Label htmlFor="rtd-source-type">{t("right_to_delete.source_type")}</Label>
								<select
									id="rtd-source-type"
									value={sourceType}
									onChange={(e) => setSourceType(e.target.value as MemorySourceType)}
									className={cn(
										"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
									)}
								>
									{memorySourceTypes.map((type) => (
										<option key={type} value={type}>
											{type}
										</option>
									))}
								</select>
							</div>

							<div className="space-y-2">
								<Label htmlFor="rtd-source-id">{t("right_to_delete.source_id")}</Label>
								<Input
									id="rtd-source-id"
									type="number"
									value={sourceId}
									onChange={(e) => setSourceId(e.target.value)}
									placeholder={t("right_to_delete.source_id_placeholder")}
								/>
							</div>

							<div className="space-y-2">
								<Label htmlFor="rtd-source-entity-type">
									{t("right_to_delete.source_entity_type")}
								</Label>
								<Input
									id="rtd-source-entity-type"
									value={sourceEntityType}
									onChange={(e) => setSourceEntityType(e.target.value)}
									placeholder={t("right_to_delete.source_entity_type_placeholder")}
								/>
							</div>

							<div className="grid gap-4 sm:grid-cols-2">
								<div className="space-y-2">
									<Label htmlFor="rtd-created-after">{t("right_to_delete.created_after")}</Label>
									<Input
										id="rtd-created-after"
										type="datetime-local"
										value={createdAfter}
										onChange={(e) => setCreatedAfter(e.target.value)}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="rtd-created-before">{t("right_to_delete.created_before")}</Label>
									<Input
										id="rtd-created-before"
										type="datetime-local"
										value={createdBefore}
										onChange={(e) => setCreatedBefore(e.target.value)}
									/>
								</div>
							</div>
						</div>
					)}

					<div className="space-y-2">
						<Label htmlFor="rtd-reason">{t("right_to_delete.reason")}</Label>
						<Input
							id="rtd-reason"
							value={reason}
							onChange={(e) => setReason(e.target.value)}
							placeholder={t("right_to_delete.reason_placeholder")}
						/>
					</div>

					<div className="flex gap-2">
						<Button type="button" variant="secondary" disabled={saving} onClick={handleDryRun}>
							{t("right_to_delete.dry_run")}
						</Button>
						<Button
							type="button"
							disabled={!canEdit || saving}
							onClick={() => {
								setDryRunResult(null);
								handleExecute();
							}}
							variant="destructive"
						>
							{t("right_to_delete.execute")}
						</Button>
					</div>

					{jobStatus && (
						<div className="rounded-md border p-4 space-y-2" aria-live="polite">
							<div className="flex items-center gap-2">
								<CheckCircle2 className="h-4 w-4 text-emerald-500" />
								<h4 className="text-sm font-medium">{t("right_to_delete.job_status")}</h4>
							</div>
							<p className="text-sm">
								{t("right_to_delete.job_status_text", {
									status: jobStatus.status,
									processed: jobStatus.processed,
									total: jobStatus.total,
									affected: jobStatus.affected,
									errors: jobStatus.error_count,
								})}
							</p>
							{jobStatus.cancelable && (
								<Button
									type="button"
									variant="destructive"
									size="sm"
									disabled={saving}
									onClick={handleCancelJob}
								>
									{t("right_to_delete.cancel_job")}
								</Button>
							)}
						</div>
					)}

					{dryRunResult && (
						<div className="rounded-md border p-4 space-y-2">
							<div className="flex items-center gap-2">
								<AlertTriangle className="h-4 w-4 text-amber-500" />
								<h4 className="text-sm font-medium">{t("right_to_delete.dry_run_result")}</h4>
							</div>
							<p className="text-sm">
								{t("right_to_delete.affected_count", { count: dryRunResult.affected_count })}
							</p>
							{dryRunResult.preview_memory_ids.length > 0 && (
								<div>
									<p className="text-xs text-muted-foreground">
										{t("right_to_delete.preview_ids")}
									</p>
									<p className="text-xs font-mono break-all">
										{dryRunResult.preview_memory_ids.join(", ")}
									</p>
								</div>
							)}
							<Button
								type="button"
								disabled={!canEdit || saving}
								onClick={() => setConfirmOpen(true)}
								variant="destructive"
							>
								{t("right_to_delete.confirm_execute")}
							</Button>
						</div>
					)}
				</CardContent>
			</Card>

			<Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<AlertTriangle className="h-5 w-5 text-destructive" />
							{t("right_to_delete.confirm_title")}
						</DialogTitle>
						<DialogDescription>
							{t("right_to_delete.confirm_description", {
								count: dryRunResult?.affected_count ?? 0,
							})}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="gap-2">
						<Button variant="outline" onClick={() => setConfirmOpen(false)}>
							{tCommon("cancel")}
						</Button>
						<Button variant="destructive" disabled={saving} onClick={handleExecute}>
							{saving ? tCommon("save") : t("right_to_delete.confirm_execute")}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</section>
	);
}
