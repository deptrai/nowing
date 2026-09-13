"use client";

import { z } from "zod";
import {
	type AuditLogFilter,
	auditLogEntrySchema,
	type AuditLogEntry,
	type GovernanceDncRecord,
	type GovernanceDncRecordCreate,
	type GovernanceOverview,
	type RetentionPolicy,
	type RetentionPolicyUpdate,
	type RightToDeleteRequest,
	type RightToDeleteResponse,
	type SourceRiskTier,
	type SourceRiskTierUpdate,
	type WorkspaceStatus,
	governanceDncRecordSchema,
	governanceOverviewSchema,
	retentionPolicySchema,
	rightToDeleteResponseSchema,
	sourceRiskTierSchema,
	workspaceStatusSchema,
} from "@/contracts/types/governance.types";
import {
	type JobStatusResponse,
	type CancelJobResponse,
	jobStatusResponseSchema,
	cancelJobResponseSchema,
} from "@/contracts/types/admin-bulk-ops.types";
import { baseApiService } from "./base-api.service";

const GOVERNANCE_PREFIX = "/api/v1/workspaces";

class GovernanceApiService {
	/**
	 * GET /workspaces/{id}/governance — combined overview.
	 */
	getOverview = async (workspaceId: number): Promise<GovernanceOverview> => {
		return baseApiService.get(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance`,
			governanceOverviewSchema
		);
	};

	/**
	 * PUT /workspaces/{id}/governance/retention — update retention policy.
	 */
	updateRetentionPolicy = async (
		workspaceId: number,
		payload: RetentionPolicyUpdate
	): Promise<RetentionPolicy> => {
		return baseApiService.put(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/retention`,
			retentionPolicySchema,
			{ body: payload }
		);
	};

	/**
	 * GET /workspaces/{id}/governance/source-risk-tiers
	 */
	listSourceRiskTiers = async (workspaceId: number): Promise<SourceRiskTier[]> => {
		return baseApiService.get(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/source-risk-tiers`,
			z.array(sourceRiskTierSchema)
		);
	};

	/**
	 * PUT /workspaces/{id}/governance/source-risk-tiers — upsert tier.
	 */
	upsertSourceRiskTier = async (
		workspaceId: number,
		payload: SourceRiskTierUpdate
	): Promise<SourceRiskTier> => {
		return baseApiService.put(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/source-risk-tiers`,
			sourceRiskTierSchema,
			{ body: payload }
		);
	};

	/**
	 * GET /workspaces/{id}/governance/dnc-records
	 */
	listDncRecords = async (workspaceId: number): Promise<GovernanceDncRecord[]> => {
		return baseApiService.get(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/dnc-records`,
			z.array(governanceDncRecordSchema)
		);
	};

	/**
	 * POST /workspaces/{id}/governance/dnc-records
	 */
	createDncRecord = async (
		workspaceId: number,
		payload: GovernanceDncRecordCreate
	): Promise<GovernanceDncRecord> => {
		return baseApiService.post(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/dnc-records`,
			governanceDncRecordSchema,
			{ body: payload }
		);
	};

	/**
	 * DELETE /workspaces/{id}/governance/dnc-records/{record_id}
	 */
	deleteDncRecord = async (workspaceId: number, recordId: string): Promise<void> => {
		return baseApiService.delete(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/dnc-records/${recordId}`
		);
	};

	/**
	 * POST /workspaces/{id}/governance/right-to-delete
	 */
	rightToDelete = async (
		workspaceId: number,
		payload: RightToDeleteRequest
	): Promise<RightToDeleteResponse> => {
		return baseApiService.post(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/right-to-delete`,
			rightToDeleteResponseSchema,
			{ body: payload }
		);
	};

	/**
	 * GET /workspaces/{id}/governance/jobs/{job_id}
	 */
	getBulkOpJob = async (workspaceId: number, jobId: string): Promise<JobStatusResponse> => {
		return baseApiService.get(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/jobs/${jobId}`,
			jobStatusResponseSchema
		);
	};

	/**
	 * POST /workspaces/{id}/governance/jobs/{job_id}/cancel
	 */
	cancelBulkOpJob = async (workspaceId: number, jobId: string): Promise<CancelJobResponse> => {
		return baseApiService.post(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/jobs/${jobId}/cancel`,
			cancelJobResponseSchema
		);
	};

	/**
	 * GET /workspaces/{id}/governance/audit-log
	 */
	listAuditLog = async (
		workspaceId: number,
		filters: AuditLogFilter = { page: 1, page_size: 50 }
	): Promise<AuditLogEntry[]> => {
		const params = new URLSearchParams();
		if (filters.action_prefix) params.set("action_prefix", filters.action_prefix);
		if (filters.created_after) params.set("created_after", filters.created_after);
		if (filters.created_before) params.set("created_before", filters.created_before);
		params.set("page", String(filters.page ?? 1));
		params.set("page_size", String(filters.page_size ?? 50));

		return baseApiService.get(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/audit-log?${params.toString()}`,
			z.array(auditLogEntrySchema)
		);
	};

	/**
	 * POST /workspaces/{id}/governance/archive
	 */
	archiveWorkspace = async (workspaceId: number): Promise<WorkspaceStatus> => {
		return baseApiService.post(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/archive`,
			workspaceStatusSchema
		);
	};

	/**
	 * POST /workspaces/{id}/governance/restore
	 */
	restoreWorkspace = async (workspaceId: number): Promise<WorkspaceStatus> => {
		return baseApiService.post(
			`${GOVERNANCE_PREFIX}/${workspaceId}/governance/restore`,
			workspaceStatusSchema
		);
	};
}

export const governanceApiService = new GovernanceApiService();
