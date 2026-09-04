import { z } from "zod";

/**
 * Alert rule (saved search) schemas — mirror the backend
 * ``app/alerts/schemas.py`` (``AlertRuleRead`` / ``AlertSnapshot``).
 */

export const alertRuleQuery = z.record(z.string(), z.unknown());

export const alertRule = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	name: z.string(),
	capability_id: z.string(),
	query: alertRuleQuery,
	schedule: z.enum(["none", "daily", "weekly"]),
	timezone: z.string(),
	diff_strategy: z.enum(["new_items", "price_change", "threshold_cross", "trend_detect"]),
	threshold: z.record(z.string(), z.unknown()).nullable().optional(),
	target_sequence_id: z.string().uuid().nullable().optional(),
	target_step_id: z.string().uuid().nullable().optional(),
	notification_channels: z.array(z.enum(["in_app", "telegram"])),
	enabled: z.boolean(),
	cron: z.string().nullable().optional(),
	next_fire_at: z.string().nullable().optional(),
	last_fired_at: z.string().nullable().optional(),
	created_at: z.string(),
	updated_at: z.string(),
});

export const alertSnapshot = z.object({
	id: z.string().uuid(),
	alert_rule_id: z.string().uuid(),
	snapshot_json: z.record(z.string(), z.unknown()),
	run_status: z.string(),
	degradation_reasons: z.array(z.string()).nullable().optional(),
	new_items_count: z.number(),
	changed_items_count: z.number(),
	removed_items_count: z.number(),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export const alertSnapshotListResponse = z.array(alertSnapshot);

export type AlertRule = z.infer<typeof alertRule>;
export type AlertSnapshot = z.infer<typeof alertSnapshot>;
export type AlertSnapshotListResponse = z.infer<typeof alertSnapshotListResponse>;

// ============================================================================
// Story 6.11: Vertical Alert Rule Templates Types
// ============================================================================

export const alertTemplateParameter = z.object({
	name: z.string(),
	label: z.string(),
	description: z.string().nullable().optional(),
	type: z.string(),
	required: z.boolean(),
	default: z.unknown().optional(),
	options: z
		.array(z.object({ value: z.string(), label: z.string() }))
		.nullable()
		.optional(),
});

export const alertTemplateRead = z.object({
	template_id: z.string(),
	name: z.string(),
	description: z.string(),
	category: z.string(),
	required_capability: z.string(),
	diff_strategy: z.string(),
	default_schedule: z.string(),
	parameters: z.array(alertTemplateParameter),
	is_available: z.boolean(),
	unavailable_reason: z.string().nullable().optional(),
});

export const alertTemplateListResponse = z.array(alertTemplateRead);

export const createAlertFromTemplateRequest = z.object({
	template_id: z.string(),
	name: z.string(),
	parameters: z.record(z.string(), z.unknown()),
	schedule: z.enum(["none", "daily", "weekly"]).optional(),
	notification_channels: z.array(z.enum(["in_app", "telegram"])).optional(),
});

export type AlertTemplateParameter = z.infer<typeof alertTemplateParameter>;
export type AlertTemplateRead = z.infer<typeof alertTemplateRead>;
export type AlertTemplateListResponse = z.infer<typeof alertTemplateListResponse>;
export type CreateAlertFromTemplateRequest = z.infer<typeof createAlertFromTemplateRequest>;
