import { z } from "zod";

export const bulkActionSchema = z.enum([
	"archive_inactive_workspaces",
	"rotate_api_keys",
	"assign_role",
	"delete_source_type_memories",
	"apply_tier",
	"revoke_membership",
]);
export type BulkAction = z.infer<typeof bulkActionSchema>;

export const bulkOpJobStatusSchema = z.enum([
	"queued",
	"running",
	"completed",
	"failed",
	"cancelled",
	"partial",
]);
export type BulkOpJobStatus = z.infer<typeof bulkOpJobStatusSchema>;

export const filterOperatorSchema = z.enum(["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]);
export type FilterOperator = z.infer<typeof filterOperatorSchema>;

export const filterClauseSchema = z.object({
	field: z.string().min(1).max(64),
	op: filterOperatorSchema,
	value: z.any(),
});
export type FilterClause = z.infer<typeof filterClauseSchema>;

export const dryRunRequestSchema = z.object({
	action: bulkActionSchema,
	filter_spec: z.array(filterClauseSchema).default([]),
	action_params: z.record(z.string(), z.any()).default({}),
	workspace_id: z.number().nullable().optional(),
});
export type DryRunRequest = z.infer<typeof dryRunRequestSchema>;

export const dryRunResponseSchema = z.object({
	action: bulkActionSchema,
	total_count: z.number(),
	affected_count: z.number().optional(),
	sample_subjects: z.array(z.record(z.string(), z.any())).default([]),
	sample_affected: z.array(z.record(z.string(), z.any())).default([]),
	warnings: z.array(z.string()).default([]),
	conflicts: z.array(z.record(z.string(), z.any())).default([]),
	can_execute: z.boolean().default(true),
});
export type DryRunResponse = z.infer<typeof dryRunResponseSchema>;

export const executeRequestSchema = z.object({
	action: bulkActionSchema,
	filter_spec: z.array(filterClauseSchema).default([]),
	action_params: z.record(z.string(), z.any()).default({}),
	workspace_id: z.number().nullable().optional(),
	password: z.string().nullable().optional(),
	mfa_token: z.string().nullable().optional(),
});
export type ExecuteRequest = z.infer<typeof executeRequestSchema>;

export const executeResponseSchema = z.object({
	job_id: z.string().uuid(),
	status: z.string(),
	action: bulkActionSchema,
	message: z.string().default("Job queued successfully"),
});
export type ExecuteResponse = z.infer<typeof executeResponseSchema>;

export const jobStatusResponseSchema = z.object({
	job_id: z.string().uuid(),
	action: z.string(),
	status: z.string(),
	actor_id: z.string().nullable().optional(),
	workspace_id: z.number().nullable().optional(),
	filter_spec: z.array(z.record(z.string(), z.any())).default([]),
	action_params: z.record(z.string(), z.any()).default({}),
	total_count: z.number().default(0),
	processed_count: z.number().default(0),
	affected_count: z.number().default(0),
	error_count: z.number().default(0),
	started_at: z.string().nullable().optional(),
	completed_at: z.string().nullable().optional(),
	created_at: z.string(),
	error_message: z.string().nullable().optional(),
	cancelable: z.boolean().default(false),
	is_cancelable: z.boolean().optional(),
});
export type JobStatusResponse = z.infer<typeof jobStatusResponseSchema>;

export const bulkOpErrorReadSchema = z.object({
	id: z.number(),
	job_id: z.string().uuid(),
	subject_type: z.string(),
	subject_id: z.string(),
	error_message: z.string(),
	retryable: z.boolean(),
	created_at: z.string(),
});
export type BulkOpErrorRead = z.infer<typeof bulkOpErrorReadSchema>;

export const cancelJobResponseSchema = z.object({
	job_id: z.string().uuid(),
	status: z.string(),
	message: z.string(),
});
export type CancelJobResponse = z.infer<typeof cancelJobResponseSchema>;

export interface ActionFilterMeta {
	fields: Record<
		string,
		{ label: string; operators: FilterOperator[]; type: "number" | "string" | "date" }
	>;
	requiredParams?: Record<string, { label: string; type: "string" | "number" }>;
	isHighRisk?: boolean;
	cancelableWhileRunning: boolean;
	superadminOnly: boolean;
}

export const ACTION_METADATA: Record<BulkAction, ActionFilterMeta> = {
	archive_inactive_workspaces: {
		fields: {
			inactive_days: {
				label: "Inactive Days (must be > 0)",
				operators: ["gte", "gt"],
				type: "number",
			},
			plan_tier: { label: "Plan Tier", operators: ["eq", "neq", "in"], type: "string" },
			is_active: { label: "Is Active", operators: ["eq", "neq"], type: "string" },
			workspace_id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
			id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
		},
		cancelableWhileRunning: true,
		superadminOnly: true,
	},
	rotate_api_keys: {
		fields: {
			workspace_id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
			plan_tier: { label: "Plan Tier", operators: ["eq", "neq", "in"], type: "string" },
			id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
			api_access_enabled: { label: "API Access Enabled", operators: ["eq", "neq"], type: "string" },
		},
		isHighRisk: true,
		cancelableWhileRunning: false,
		superadminOnly: true,
	},
	assign_role: {
		fields: {
			workspace_id: { label: "Workspace ID", operators: ["eq"], type: "number" },
			role_id: { label: "Current Role ID", operators: ["eq", "neq", "in"], type: "number" },
			user_id: { label: "User ID", operators: ["eq", "in"], type: "string" },
			is_owner: { label: "Is Owner", operators: ["eq", "neq"], type: "string" },
		},
		requiredParams: {
			target_role_id: { label: "Target Role ID", type: "number" },
		},
		cancelableWhileRunning: false,
		superadminOnly: false,
	},
	delete_source_type_memories: {
		fields: {
			workspace_id: { label: "Workspace ID", operators: ["eq"], type: "number" },
			source_type: {
				label: "Source Type (e.g. scraper_run)",
				operators: ["eq", "in"],
				type: "string",
			},
			created_before: { label: "Created Before", operators: ["lt", "lte"], type: "date" },
			created_after: { label: "Created After", operators: ["gt", "gte"], type: "date" },
			memory_type: { label: "Memory Type", operators: ["eq", "neq", "in"], type: "string" },
		},
		cancelableWhileRunning: true,
		superadminOnly: false,
	},
	apply_tier: {
		fields: {
			workspace_id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
			plan_tier: { label: "Current Plan Tier", operators: ["eq", "neq", "in"], type: "string" },
			is_active: { label: "Is Active", operators: ["eq", "neq"], type: "string" },
			id: { label: "Workspace ID", operators: ["eq", "in"], type: "number" },
		},
		requiredParams: {
			target_tier: { label: "Target Tier (e.g. pro, enterprise)", type: "string" },
		},
		cancelableWhileRunning: false,
		superadminOnly: true,
	},
	revoke_membership: {
		fields: {
			workspace_id: { label: "Workspace ID", operators: ["eq"], type: "number" },
			role_id: { label: "Role ID", operators: ["eq", "neq", "in"], type: "number" },
			user_id: { label: "User ID", operators: ["eq", "in"], type: "string" },
			is_owner: { label: "Is Owner", operators: ["eq", "neq"], type: "string" },
		},
		cancelableWhileRunning: true,
		superadminOnly: false,
	},
};
