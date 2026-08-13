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
