"use client";

import {
	AlertTriangle,
	Ban,
	CheckCircle,
	ChevronDown,
	ChevronUp,
	Clock,
	Download,
	XCircle,
} from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { BulkOpErrorRead, JobStatusResponse } from "@/contracts/types/admin-bulk-ops.types";
import { useTranslations } from "next-intl";

interface JobProgressProps {
	job: JobStatusResponse | null;
	errors?: BulkOpErrorRead[];
	onCancel?: () => void;
	isCancelling?: boolean;
}

export function JobProgress({
	job,
	errors = [],
	onCancel,
	isCancelling = false,
}: JobProgressProps) {
	const t = useTranslations("bulkOps");
	const [showErrors, setShowErrors] = useState(false);

	if (!job) return null;

	const total = job.total_count || 0;
	const processed = job.processed_count || 0;
	const percentage = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
	const isCancelable =
		job.status === "queued" || (job.status === "running" && (job.cancelable || job.is_cancelable));

	const renderStatusBadge = () => {
		switch (job.status) {
			case "queued":
				return (
					<Badge
						variant="outline"
						className="border-blue-500/50 text-blue-600 bg-blue-500/10 gap-1"
					>
						<Clock className="h-3 w-3 animate-pulse" />
						{t("status_queued")}
					</Badge>
				);
			case "running":
				return (
					<Badge
						variant="outline"
						className="border-amber-500/50 text-amber-600 bg-amber-500/10 gap-1"
					>
						<div className="h-2 w-2 rounded-full bg-amber-500 animate-ping" />
						{t("status_running", { percentage })}
					</Badge>
				);
			case "completed":
				return (
					<Badge
						variant="outline"
						className="border-green-500/50 text-green-600 bg-green-500/10 gap-1"
					>
						<CheckCircle className="h-3 w-3" />
						{t("status_completed")}
					</Badge>
				);
			case "partial":
				return (
					<Badge
						variant="outline"
						className="border-amber-500/50 text-amber-600 bg-amber-500/10 gap-1"
					>
						<AlertTriangle className="h-3 w-3" />
						{t("status_partial")}
					</Badge>
				);
			case "failed":
				return (
					<Badge variant="destructive" className="gap-1">
						<XCircle className="h-3 w-3" />
						{t("status_failed")}
					</Badge>
				);
			case "cancelled":
				return (
					<Badge variant="secondary" className="gap-1">
						<Ban className="h-3 w-3" />
						{t("status_cancelled")}
					</Badge>
				);
			default:
				return <Badge variant="secondary">{job.status}</Badge>;
		}
	};

	const handleDownloadErrorsCsv = () => {
		if (errors.length === 0) return;
		const headers = [
			"ID",
			"Subject Type",
			"Subject ID",
			"Error Message",
			"Retryable",
			"Created At",
		];
		const rows = errors.map((e) => [
			e.id,
			`"${e.subject_type}"`,
			`"${e.subject_id}"`,
			`"${e.error_message.replace(/"/g, '""')}"`,
			e.retryable,
			`"${e.created_at}"`,
		]);
		const csvContent =
			"data:text/csv;charset=utf-8," +
			[headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement("a");
		link.setAttribute("href", encodedUri);
		link.setAttribute("download", `bulk_op_errors_${job.job_id}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	};

	return (
		<Card className="border-primary/20 shadow-sm">
			<CardHeader className="pb-3">
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
					<div>
						<div className="flex items-center gap-2">
							<CardTitle className="text-base font-semibold">{t("bulk_operation_job")}</CardTitle>
							{renderStatusBadge()}
						</div>
						<CardDescription className="font-mono text-xs mt-1">
							ID: {job.job_id} • Action: {job.action}
						</CardDescription>
					</div>

					{isCancelable && onCancel && (
						<Button
							type="button"
							variant="outline"
							size="sm"
							onClick={onCancel}
							disabled={isCancelling}
							className="text-xs text-destructive hover:bg-destructive/10 border-destructive/30 h-8 self-start sm:self-auto"
						>
							<Ban className="h-3.5 w-3.5 mr-1.5" />
							{isCancelling ? t("cancelling") : t("cancel_job")}
						</Button>
					)}
				</div>
			</CardHeader>

			<CardContent className="space-y-4">
				{/* Progress bar */}
				<div className="space-y-1.5">
					<div className="flex justify-between text-xs text-muted-foreground">
						<span>
							{t("progress_text", { processed, total })}
						</span>
						<span>{percentage}%</span>
					</div>
					<Progress value={percentage} className="h-2" />
				</div>

				{/* Metrics Grid */}
				<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
					<div className="p-2.5 rounded-md border bg-card text-center">
						<span className="text-[11px] text-muted-foreground block">{t("total")}</span>
						<span className="text-lg font-bold">{total}</span>
					</div>
					<div className="p-2.5 rounded-md border bg-card text-center">
						<span className="text-[11px] text-muted-foreground block">{t("processed")}</span>
						<span className="text-lg font-bold">{processed}</span>
					</div>
					<div className="p-2.5 rounded-md border bg-card text-center">
						<span className="text-[11px] text-muted-foreground block">{t("affected")}</span>
						<span className="text-lg font-bold text-green-600">{job.affected_count}</span>
					</div>
					<div className="p-2.5 rounded-md border bg-card text-center">
						<span className="text-[11px] text-muted-foreground block">{t("errors")}</span>
						<span className="text-lg font-bold text-destructive">{job.error_count}</span>
					</div>
				</div>

				{/* Timestamps */}
				<div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground pt-1 border-t">
					<div>
						{t("created")}:{" "}
						<span className="font-mono text-foreground">
							{new Date(job.created_at).toLocaleString()}
						</span>
					</div>
					{job.started_at && (
						<div>
							{t("started")}:{" "}
							<span className="font-mono text-foreground">
								{new Date(job.started_at).toLocaleString()}
							</span>
						</div>
					)}
					{job.completed_at && (
						<div>
							{t("completed")}:{" "}
							<span className="font-mono text-foreground">
								{new Date(job.completed_at).toLocaleString()}
							</span>
						</div>
					)}
				</div>

				{/* Error Message if failed */}
				{job.error_message && (
					<div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs">
						<strong>{t("error_prefix")}:</strong> {job.error_message}
					</div>
				)}

				{/* Error Log Section */}
				{job.error_count > 0 && (
					<div className="pt-2 border-t space-y-2">
						<div className="flex items-center justify-between">
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={() => setShowErrors(!showErrors)}
								className="text-xs text-destructive hover:text-destructive h-8 p-0"
							>
								{showErrors ? (
									<ChevronUp className="h-4 w-4 mr-1" />
								) : (
									<ChevronDown className="h-4 w-4 mr-1" />
								)}
								{showErrors ? t("hide_error_log") : t("view_error_log", { count: job.error_count })}
							</Button>
							{errors.length > 0 && (
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={handleDownloadErrorsCsv}
									className="text-xs h-7 gap-1"
								>
									<Download className="h-3 w-3" />
									{t("download_errors_csv")}
								</Button>
							)}
						</div>

						{showErrors && (
							<div className="rounded-md border overflow-x-auto max-h-48">
								<Table className="text-xs">
									<TableHeader>
										<TableRow className="h-8">
											<TableHead className="w-[100px]">{t("subject")}</TableHead>
											<TableHead className="w-[120px]">{t("subject_id")}</TableHead>
											<TableHead>{t("error_message")}</TableHead>
										</TableRow>
									</TableHeader>
									<TableBody>
										{errors.length === 0 ? (
											<TableRow>
												<TableCell colSpan={3} className="text-center text-muted-foreground py-4">
													{t("loading_errors")}
												</TableCell>
											</TableRow>
										) : (
											errors.map((err) => (
												<TableRow key={err.id} className="h-8">
													<TableCell className="font-mono">{err.subject_type}</TableCell>
													<TableCell className="font-mono truncate max-w-[120px]">
														{err.subject_id}
													</TableCell>
													<TableCell className="text-destructive font-mono text-[11px]">
														{err.error_message}
													</TableCell>
												</TableRow>
											))
										)}
									</TableBody>
								</Table>
							</div>
						)}
					</div>
				)}
			</CardContent>
		</Card>
	);
}
