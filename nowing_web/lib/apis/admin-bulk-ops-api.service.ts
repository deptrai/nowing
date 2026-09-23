"use client";

import { z } from "zod";
import {
	type BulkOpErrorRead,
	bulkOpErrorReadSchema,
	type CancelJobResponse,
	cancelJobResponseSchema,
	type DryRunRequest,
	type DryRunResponse,
	dryRunResponseSchema,
	type ExecuteRequest,
	type ExecuteResponse,
	executeResponseSchema,
	type JobStatusResponse,
	jobStatusResponseSchema,
} from "@/contracts/types/admin-bulk-ops.types";
import { baseApiService } from "./base-api.service";

class AdminBulkOpsApiService {
	/**
	 * Run a dry-run simulation for bulk operations.
	 */
	dryRun = async (payload: DryRunRequest, workspaceId?: number | null): Promise<DryRunResponse> => {
		const url = workspaceId
			? `/api/v1/workspaces/${workspaceId}/bulk-ops/dry-run`
			: "/api/v1/admin/saas/bulk-ops/dry-run";
		return baseApiService.post(url, dryRunResponseSchema, {
			body: payload,
		});
	};

	/**
	 * Execute a bulk operation job with required Idempotency-Key header.
	 */
	execute = async (
		payload: ExecuteRequest,
		idempotencyKey: string,
		workspaceId?: number | null
	): Promise<ExecuteResponse> => {
		const url = workspaceId
			? `/api/v1/workspaces/${workspaceId}/bulk-ops`
			: "/api/v1/admin/saas/bulk-ops/execute";
		return baseApiService.post(url, executeResponseSchema, {
			body: payload,
			headers: {
				"Idempotency-Key": idempotencyKey,
			},
		});
	};

	/**
	 * Poll job status by UUID.
	 */
	getJob = async (jobId: string, workspaceId?: number | null): Promise<JobStatusResponse> => {
		const url = workspaceId
			? `/api/v1/workspaces/${workspaceId}/bulk-ops/${jobId}`
			: `/api/v1/admin/saas/bulk-ops/${jobId}`;
		return baseApiService.get(url, jobStatusResponseSchema);
	};

	/**
	 * Retrieve error log items for a specific job.
	 */
	getErrors = async (jobId: string, workspaceId?: number | null): Promise<BulkOpErrorRead[]> => {
		const url = workspaceId
			? `/api/v1/workspaces/${workspaceId}/bulk-ops/${jobId}/errors`
			: `/api/v1/admin/saas/bulk-ops/${jobId}/errors`;
		return baseApiService.get(url, z.array(bulkOpErrorReadSchema));
	};

	/**
	 * Cancel a queued or running job if permitted.
	 */
	cancelJob = async (jobId: string, workspaceId?: number | null): Promise<CancelJobResponse> => {
		const url = workspaceId
			? `/api/v1/workspaces/${workspaceId}/bulk-ops/${jobId}/cancel`
			: `/api/v1/admin/saas/bulk-ops/${jobId}/cancel`;
		return baseApiService.post(url, cancelJobResponseSchema);
	};
}

export const adminBulkOpsApiService = new AdminBulkOpsApiService();
