import { z } from "zod";

export const dshMissionStatusSchema = z.enum([
	"pending",
	"running",
	"success",
	"error",
	"cancelled",
	"dlq",
]);

export type DshMissionStatus = z.infer<typeof dshMissionStatusSchema>;

export const dshMissionTypeSchema = z.enum(["deep_lead_research", "cdp_browser_operator", "noop"]);

export type DshMissionType = z.infer<typeof dshMissionTypeSchema>;

export const dshMissionRequestSchema = z.object({
	mission_type: dshMissionTypeSchema.default("deep_lead_research"),
	payload: z.record(z.string(), z.unknown()).default({}),
});

export type DshMissionRequest = z.infer<typeof dshMissionRequestSchema>;

export const dshMissionResponseSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	mission_type: dshMissionTypeSchema,
	status: dshMissionStatusSchema,
	phase: z.string().nullable().optional(),
	progress_percent: z.number().nullable().optional(),
	current_subtask_id: z.string().nullable().optional(),
	retry_count: z.number().default(0),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export type DshMission = z.infer<typeof dshMissionResponseSchema>;

export const tokenVelocitySchema = z.object({
	tokens_total: z.number().default(0),
	tokens_per_second: z.number().default(0),
	cost_micros: z.number().default(0),
	cost_credits: z.number().default(0),
});

export type TokenVelocity = z.infer<typeof tokenVelocitySchema>;

export const dshMissionSubtaskSchema = z.object({
	id: z.string(),
	title: z.string(),
	status: z.string(),
	phase: z.string().nullable().optional(),
	reasoning_content: z.string().nullable().optional(),
	tokens_used: z.number().default(0),
	tokens_per_second: z.number().default(0),
	run_id: z.string().nullable().optional(),
	cost_micros: z.number().default(0),
	started_at: z.string().nullable().optional(),
	completed_at: z.string().nullable().optional(),
});

export type DshMissionSubtask = z.infer<typeof dshMissionSubtaskSchema>;

export const dshMissionDeliverableSchema = z.object({
	type: z.string(),
	filename: z.string(),
	size: z.number().default(0),
	created_at: z.string().nullable().optional(),
	include_pii: z.boolean().default(false),
	sources_count: z.number().default(0),
	topics_count: z.number().default(0),
});

export type DshMissionDeliverable = z.infer<typeof dshMissionDeliverableSchema>;

export const dshMissionControlResponseSchema = dshMissionResponseSchema.extend({
	query: z.string().nullable().optional(),
	token_velocity: tokenVelocitySchema,
	subtasks: z.array(dshMissionSubtaskSchema),
	deliverables: z.array(dshMissionDeliverableSchema).default([]),
});

export type DshMissionControl = z.infer<typeof dshMissionControlResponseSchema>;

export const dshMissionListResponseSchema = z.object({
	items: z.array(dshMissionResponseSchema),
	total: z.number(),
	limit: z.number(),
	offset: z.number(),
});

export type DshMissionListResponse = z.infer<typeof dshMissionListResponseSchema>;

export interface ListMissionsParams {
	status?: string;
	hours?: number;
	limit?: number;
	offset?: number;
}
