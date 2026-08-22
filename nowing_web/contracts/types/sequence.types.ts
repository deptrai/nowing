import { z } from "zod";

const channelEnum = z.enum(["email", "zalo", "telegram"]);

export const sequenceStepSchema = z.object({
	id: z.string().uuid().optional(),
	workspace_id: z.number().optional(),
	client_id: z.string().nullable().optional(),
	sequence_id: z.string().uuid().optional(),
	step_order: z.number().min(1),
	step_type: z.enum([
		"send_email",
		"send_zalo",
		"send_telegram",
		"wait",
		"condition",
		"update_lead_score",
		"update_crm",
		"tag",
	]),
	channel: channelEnum.default("email"),
	template: z.record(z.string(), z.any()).default({}),
	fallback_channels: z.array(channelEnum).optional(),
	wait_duration_seconds: z.number().nullable().optional(),
	condition_config: z.record(z.string(), z.any()).default({}),
	is_enabled: z.boolean().default(true),
	created_at: z.string().optional(),
	updated_at: z.string().nullable().optional(),
});

export type SequenceStep = z.infer<typeof sequenceStepSchema>;

export const sequenceSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	name: z.string(),
	description: z.string().nullable().optional(),
	status: z.enum(["active", "paused", "archived"]).default("active"),
	shared: z.boolean().default(false),
	entry_step_order: z.number().default(1),
	created_by_user_id: z.string().uuid().nullable().optional(),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
	steps: z.array(sequenceStepSchema).default([]),
});

export type Sequence = z.infer<typeof sequenceSchema>;

export const sequenceCreateSchema = z.object({
	name: z.string().min(1, "Vui lòng nhập tên chiến dịch"),
	description: z.string().nullable().optional(),
	status: z.enum(["active", "paused", "archived"]).default("active"),
	shared: z.boolean().default(false),
	entry_step_order: z.number().default(1),
	steps: z.array(sequenceStepSchema).default([]),
});

export type SequenceCreate = z.infer<typeof sequenceCreateSchema>;

export const sequenceEnrollmentSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	sequence_id: z.string().uuid(),
	lead_id: z.string().uuid(),
	sequence_run_id: z.string().uuid().nullable().optional(),
	current_step: z.number(),
	status: z.enum([
		"scheduled",
		"executing",
		"paused",
		"responded",
		"unsubscribed",
		"failed",
		"completed",
	]),
	scheduled_at: z.string().nullable().optional(),
	version: z.number(),
	last_event_at: z.string().nullable().optional(),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export type SequenceEnrollment = z.infer<typeof sequenceEnrollmentSchema>;

export const sequenceEventSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	enrollment_id: z.string().uuid(),
	sequence_id: z.string().uuid(),
	step_id: z.string().uuid().nullable().optional(),
	event_type: z.string(),
	event_subtype: z.string().nullable().optional(),
	channel: z.string(),
	cost_micros: z.number(),
	metadata: z.record(z.string(), z.any()).nullable().optional(),
	provider_msg_id: z.string().nullable().optional(),
	created_at: z.string(),
});

export type SequenceEvent = z.infer<typeof sequenceEventSchema>;

export const channelBreakdownSchema = z.object({
	channel: channelEnum,
	sent: z.number().default(0),
	delivered: z.number().default(0),
	opened: z.number().default(0),
	replied: z.number().default(0),
	bounced: z.number().default(0),
	failed: z.number().default(0),
	skipped: z.number().default(0),
	cost_micros: z.number().default(0),
});

export const sequenceAnalyticsSchema = z.object({
	sequence_id: z.string().uuid(),
	total_enrolled: z.number().default(0),
	active_scheduled: z.number().default(0),
	delivered_count: z.number().default(0),
	responded_count: z.number().default(0),
	unsubscribed_count: z.number().default(0),
	failed_count: z.number().default(0),
	total_cost_micros: z.number().default(0),
	channel_breakdown: z.array(channelBreakdownSchema).default([]),
});

export type SequenceAnalytics = z.infer<typeof sequenceAnalyticsSchema>;
