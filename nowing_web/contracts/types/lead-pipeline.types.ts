import { z } from "zod";

export const leadPipelineStageSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	name: z.string(),
	slug: z.string(),
	position: z.number().default(0),
	color: z.string().nullable().optional(),
	is_system: z.boolean().default(false),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export type LeadPipelineStage = z.infer<typeof leadPipelineStageSchema>;

export const leadStageTransitionRequestSchema = z.object({
	stage_id: z.string().uuid(),
	expected_version: z.number().min(1),
	note: z.string().nullable().optional(),
});

export type LeadStageTransitionRequest = z.infer<typeof leadStageTransitionRequestSchema>;

export const leadStageTransitionResponseSchema = z.object({
	lead_id: z.string().uuid(),
	workspace_id: z.number(),
	stage_id: z.string().uuid(),
	version: z.number(),
	previous_version: z.number(),
	status: z.string(),
});

export type LeadStageTransitionResponse = z.infer<typeof leadStageTransitionResponseSchema>;

export const leadActivityLogSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	lead_id: z.string().uuid(),
	actor_user_id: z.string().uuid().nullable().optional(),
	activity_type: z.string(),
	title: z.string(),
	details: z.record(z.string(), z.any()).default({}),
	created_at: z.string(),
});

export type LeadActivityLog = z.infer<typeof leadActivityLogSchema>;

export const memberSpendStatusSchema = z.object({
	workspace_id: z.number(),
	user_id: z.string(),
	monthly_spend_cap_micros: z.number().nullable().optional(),
	monthly_spent_micros: z.number(),
	remaining_cap_micros: z.number().nullable().optional(),
	workspace_balance_micros: z.number(),
});

export type MemberSpendStatus = z.infer<typeof memberSpendStatusSchema>;
