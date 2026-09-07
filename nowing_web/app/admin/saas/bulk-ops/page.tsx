"use client";

import { ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ActionSelector } from "@/components/admin/bulk-ops/ActionSelector";
import { DryRunCard } from "@/components/admin/bulk-ops/DryRunCard";
import { FilterBuilder } from "@/components/admin/bulk-ops/FilterBuilder";
import { IdempotencyKeyField } from "@/components/admin/bulk-ops/IdempotencyKeyField";
import { JobProgress } from "@/components/admin/bulk-ops/JobProgress";
import { MfaConfirmDialog } from "@/components/admin/bulk-ops/MfaConfirmDialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	ACTION_METADATA,
	type BulkAction,
	type BulkOpErrorRead,
	type DryRunResponse,
	type FilterClause,
	type JobStatusResponse,
} from "@/contracts/types/admin-bulk-ops.types";
import { adminBulkOpsApiService } from "@/lib/apis/admin-bulk-ops-api.service";

export default function AdminBulkOpsPage() {
	const [action, setAction] = useState<BulkAction | "">("archive_inactive_workspaces");
	const [filters, setFilters] = useState<FilterClause[]>([
		{ field: "inactive_days", op: "gte", value: 60 },
	]);
	const [actionParams, setActionParams] = useState<Record<string, unknown>>({});
	const [idempotencyKey, setIdempotencyKey] = useState<string>("");

	// Dry run state
	const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);
	const [isDryRunning, setIsDryRunning] = useState<boolean>(false);

	// Execution state
	const [isExecuting, setIsExecuting] = useState<boolean>(false);
	const [isMfaOpen, setIsMfaOpen] = useState<boolean>(false);

	// Active job tracking
	const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null);
	const [jobErrors, setJobErrors] = useState<BulkOpErrorRead[]>([]);
	const [isCancelling, setIsCancelling] = useState<boolean>(false);

	const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

	// Generate initial idempotency key
	const generateNewKey = useCallback(() => {
		const newKey =
			typeof crypto !== "undefined" && crypto.randomUUID
				? crypto.randomUUID()
				: "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
						const r = (Math.random() * 16) | 0;
						const v = c === "x" ? r : (r & 0x3) | 0x8;
						return v.toString(16);
					});
		setIdempotencyKey(newKey);
	}, []);

	useEffect(() => {
		generateNewKey();
	}, [generateNewKey]);

	// Invalidate dry run when action or filters change
	const handleActionChange = (newAction: BulkAction) => {
		setAction(newAction);
		setDryRunResult(null);
		setActionParams({});

		// Default initial filters per action
		if (newAction === "archive_inactive_workspaces") {
			setFilters([{ field: "inactive_days", op: "gte", value: 60 }]);
		} else if (newAction === "rotate_api_keys") {
			setFilters([{ field: "plan_tier", op: "eq", value: "free" }]);
		} else if (newAction === "delete_source_type_memories") {
			setFilters([
				{ field: "workspace_id", op: "eq", value: 1 },
				{ field: "source_type", op: "eq", value: "scraper_run" },
			]);
		} else if (newAction === "apply_tier") {
			setFilters([{ field: "current_tier", op: "eq", value: "free" }]);
			setActionParams({ target_tier: "pro" });
		} else if (newAction === "assign_role") {
			setFilters([{ field: "workspace_id", op: "eq", value: 1 }]);
			setActionParams({ target_role_id: 2 });
		} else if (newAction === "revoke_membership") {
			setFilters([
				{ field: "workspace_id", op: "eq", value: 1 },
				{ field: "inactive_days", op: "gte", value: 90 },
			]);
		} else {
			setFilters([]);
		}
	};

	const handleFiltersChange = (newFilters: FilterClause[]) => {
		setFilters(newFilters);
		setDryRunResult(null);
	};

	const handleActionParamsChange = (newParams: Record<string, unknown>) => {
		setActionParams(newParams);
		setDryRunResult(null);
	};

	// Execute Dry Run
	const handleRunSimulation = async () => {
		if (!action) return;
		setIsDryRunning(true);
		try {
			const res = await adminBulkOpsApiService.dryRun({
				action,
				filter_spec: filters,
				action_params: actionParams,
			});
			setDryRunResult(res);
			toast.success(
				`Simulation completed: ${res.affected_count ?? res.total_count} target(s) affected`
			);
		} catch (error: unknown) {
			const msg = error instanceof Error ? error.message : "Failed to execute dry-run simulation";
			toast.error(msg);
		} finally {
			setIsDryRunning(false);
		}
	};

	// Start Execution Dispatch
	const handleExecuteClick = () => {
		if (!action || !dryRunResult) return;
		const meta = ACTION_METADATA[action];
		if (meta?.isHighRisk) {
			setIsMfaOpen(true);
		} else {
			void performExecution();
		}
	};

	const performExecution = async (authData?: { password?: string; mfa_token?: string }) => {
		if (!action) return;
		setIsExecuting(true);
		try {
			const res = await adminBulkOpsApiService.execute(
				{
					action,
					filter_spec: filters,
					action_params: actionParams,
					password: authData?.password,
					mfa_token: authData?.mfa_token,
				},
				idempotencyKey
			);

			toast.success(`Job queued: ${res.job_id}`);
			setIsMfaOpen(false);

			// Start tracking the job
			await pollJob(res.job_id);
		} catch (error: unknown) {
			const msg = error instanceof Error ? error.message : "Execution failed to queue";
			toast.error(msg);
		} finally {
			setIsExecuting(false);
		}
	};

	// Poll job until terminal status
	const pollJob = useCallback(async (jobId: string) => {
		try {
			const job = await adminBulkOpsApiService.getJob(jobId);
			setActiveJob(job);

			const isTerminal = ["completed", "failed", "cancelled", "partial"].includes(job.status);

			if (isTerminal) {
				if (pollTimerRef.current) {
					clearTimeout(pollTimerRef.current);
					pollTimerRef.current = null;
				}

				if (job.status === "completed") {
					toast.success(`Job ${jobId} completed successfully!`);
				} else if (job.status === "partial") {
					toast.warning(`Job ${jobId} completed with some errors.`);
				} else if (job.status === "failed") {
					toast.error(`Job ${jobId} failed: ${job.error_message || "Unknown error"}`);
				}

				// Fetch errors if any
				if (job.error_count > 0) {
					try {
						const errs = await adminBulkOpsApiService.getErrors(jobId);
						setJobErrors(errs);
					} catch (e) {
						console.error("Failed to load job errors:", e);
					}
				}
			} else {
				// Continue polling after 2 seconds
				pollTimerRef.current = setTimeout(() => {
					void pollJob(jobId);
				}, 2000);
			}
		} catch (error) {
			console.error("Error polling job:", error);
		}
	}, []);

	// Cleanup timer on unmount
	useEffect(() => {
		return () => {
			if (pollTimerRef.current) {
				clearTimeout(pollTimerRef.current);
			}
		};
	}, []);

	// Cancel Job
	const handleCancelJob = async () => {
		if (!activeJob) return;
		setIsCancelling(true);
		try {
			await adminBulkOpsApiService.cancelJob(activeJob.job_id);
			toast.success("Job cancellation requested");
			// Refresh job status
			await pollJob(activeJob.job_id);
		} catch (error: unknown) {
			const msg = error instanceof Error ? error.message : "Failed to cancel job";
			toast.error(msg);
		} finally {
			setIsCancelling(false);
		}
	};

	return (
		<div className="container mx-auto py-8 px-4 max-w-5xl space-y-6">
			{/* Page Header */}
			<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
				<div>
					<div className="flex items-center gap-2">
						<h1 className="text-2xl font-bold tracking-tight">Admin Bulk Operations</h1>
						<Badge variant="outline" className="border-blue-500/30 text-blue-600 bg-blue-500/10">
							<ShieldCheck className="h-3.5 w-3.5 mr-1" />
							Superadmin
						</Badge>
					</div>
					<p className="text-sm text-muted-foreground mt-1">
						Safely execute cross-tenant batch updates, cleanups, role assignments, and key rotations
						with dry-run simulation.
					</p>
				</div>
			</div>

			<div className="grid grid-cols-1 gap-6">
				{/* Step 1: Action and Filters Configuration */}
				<Card>
					<CardHeader className="pb-3">
						<div className="flex items-center gap-2">
							<SlidersHorizontal className="h-4 w-4 text-primary" />
							<CardTitle className="text-base font-semibold">1. Operation Parameters</CardTitle>
						</div>
						<CardDescription className="text-xs">
							Select the target action and configure parameterized filters.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6">
						<ActionSelector
							value={action}
							onChange={handleActionChange}
							isSuperadmin={true}
							disabled={isExecuting || isDryRunning}
						/>

						{action && (
							<FilterBuilder
								action={action}
								filters={filters}
								onFiltersChange={handleFiltersChange}
								actionParams={actionParams}
								onActionParamsChange={handleActionParamsChange}
								disabled={isExecuting || isDryRunning}
							/>
						)}

						<div className="pt-2 border-t">
							<IdempotencyKeyField
								idempotencyKey={idempotencyKey}
								onRegenerate={generateNewKey}
								disabled={isExecuting || isDryRunning}
							/>
						</div>
					</CardContent>
				</Card>

				{/* Step 2: Dry Run Simulation and Execution */}
				<DryRunCard
					dryRunResult={dryRunResult}
					isLoading={isDryRunning}
					onDryRun={handleRunSimulation}
					isDryRunning={isDryRunning}
					onExecute={handleExecuteClick}
					isExecuting={isExecuting}
					disabled={!action}
					isHighRisk={action ? ACTION_METADATA[action]?.isHighRisk : false}
				/>

				{/* Step 3: Active Job Progress Monitor */}
				{activeJob && (
					<JobProgress
						job={activeJob}
						errors={jobErrors}
						onCancel={handleCancelJob}
						isCancelling={isCancelling}
					/>
				)}
			</div>

			{/* Re-auth confirmation dialog for high risk actions */}
			<MfaConfirmDialog
				isOpen={isMfaOpen}
				onClose={() => setIsMfaOpen(false)}
				onConfirm={(auth) => void performExecution(auth)}
				isLoading={isExecuting}
			/>
		</div>
	);
}
