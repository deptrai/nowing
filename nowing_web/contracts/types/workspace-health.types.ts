import { z } from "zod";

export const workspaceHealthRangeSchema = z.enum(["7d", "30d", "90d", "custom"]);
export type WorkspaceHealthRange = z.infer<typeof workspaceHealthRangeSchema>;

export const metricCardSummarySchema = z.object({
	current_value: z.number().nullable().optional(),
	change_pct: z.number().nullable().optional(),
	sparkline: z.array(z.number()).default([]),
});
export type MetricCardSummary = z.infer<typeof metricCardSummarySchema>;

export const topSourceItemSchema = z.object({
	source_type: z.string(),
	memory_count: z.number().default(0),
	query_count: z.number().default(0),
	cost_micros: z.number().nullable().optional(),
});
export type TopSourceItem = z.infer<typeof topSourceItemSchema>;

export const coverageGapItemSchema = z.object({
	source_type: z.string(),
	enabled_since: z.string(),
	last_synced_at: z.string().nullable().optional(),
	remediation_action: z.string(),
	configure_url: z.string(),
});
export type CoverageGapItem = z.infer<typeof coverageGapItemSchema>;

export const coverageGapsResponseSchema = z.object({
	gaps: z.array(coverageGapItemSchema).default([]),
	total_gaps: z.number().default(0),
});
export type CoverageGapsResponse = z.infer<typeof coverageGapsResponseSchema>;

export const quotaProgressItemSchema = z.object({
	metric: z.string(),
	label: z.string(),
	current_value: z.number(),
	limit_value: z.number().nullable().optional(),
	utilization_pct: z.number().nullable().optional(),
	status: z.enum(["normal", "warning", "alert"]).or(z.string()).default("normal"),
	recommended_tier: z.string().nullable().optional(),
});
export type QuotaProgressItem = z.infer<typeof quotaProgressItemSchema>;

export const workspaceHealthDailyPointSchema = z.object({
	date: z.string(),
	active_members_dau: z.number().nullable().optional(),
	active_members_wau: z.number().nullable().optional(),
	total_members: z.number().default(0),
	total_memories: z.number().default(0),
	memory_growth_count: z.number().default(0),
	recall_queries: z.number().default(0),
	remember_queries: z.number().default(0),
	research_queries: z.number().default(0),
	query_volume: z.number().default(0),
	credits_consumed_micros: z.number().nullable().optional(),
	cost_per_turn_micros: z.number().nullable().optional(),
});
export type WorkspaceHealthDailyPoint = z.infer<typeof workspaceHealthDailyPointSchema>;

export const workspaceHealthSummaryResponseSchema = z.object({
	workspace_id: z.number(),
	date_range: z.string(),
	start_date: z.string(),
	end_date: z.string(),
	is_public_snapshot: z.boolean().default(false),
	total_members: metricCardSummarySchema,
	active_members_dau: metricCardSummarySchema.nullable().optional(),
	active_members_wau: metricCardSummarySchema.nullable().optional(),
	total_memories: metricCardSummarySchema,
	memory_growth_count: metricCardSummarySchema,
	query_volume: metricCardSummarySchema,
	credits_consumed_micros: metricCardSummarySchema.nullable().optional(),
	cost_per_turn_micros: metricCardSummarySchema.nullable().optional(),
	recall_queries: z.number().default(0),
	remember_queries: z.number().default(0),
	research_queries: z.number().default(0),
	top_sources: z.array(topSourceItemSchema).default([]),
	source_coverage_gap_count: z.number().default(0),
	quota_progress: z.array(quotaProgressItemSchema).nullable().optional(),
	daily_metrics: z.array(workspaceHealthDailyPointSchema).default([]),
});
export type WorkspaceHealthSummaryResponse = z.infer<typeof workspaceHealthSummaryResponseSchema>;

export const sourceTimelineSampleSchema = z.object({
	id: z.number(),
	content: z.string(),
	created_at: z.string(),
	confidence: z.number().default(1.0),
	tags: z.array(z.string()).default([]),
});
export type SourceTimelineSample = z.infer<typeof sourceTimelineSampleSchema>;

export const sourceBreakdownResponseSchema = z.object({
	workspace_id: z.number(),
	source_type: z.string(),
	total_memories: z.number().default(0),
	query_volume: z.number().default(0),
	cost_micros: z.number().nullable().optional(),
	recent_samples: z.array(sourceTimelineSampleSchema).default([]),
});
export type SourceBreakdownResponse = z.infer<typeof sourceBreakdownResponseSchema>;
