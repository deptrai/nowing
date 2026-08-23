import { z } from "zod";

export const usageBreakdownItem = z.object({
	key: z.string(),
	total_tokens: z.number(),
	cost_micros: z.number(),
});

export const usageSummaryResponse = z.object({
	current_balance_micros: z.number(),
	reserved_micros: z.number(),
	total_tokens: z.number(),
	total_cost_micros: z.number(),
	start_date: z.string(),
	end_date: z.string(),
	by_usage_type: z.array(usageBreakdownItem),
	by_model: z.array(usageBreakdownItem),
	by_provider: z.array(usageBreakdownItem),
});

export const usageTimeSeriesPoint = z.object({
	period: z.string(),
	total_tokens: z.number(),
	cost_micros: z.number(),
});

export const usageTimeSeriesResponse = z.object({
	granularity: z.string(),
	points: z.array(usageTimeSeriesPoint),
});

export const usageTransactionItem = z.object({
	type: z.string(),
	amount_micros: z.number(),
	description: z.string().nullable(),
	status: z.string().nullable(),
	created_at: z.string(),
});

export const usageTransactionsResponse = z.object({
	transactions: z.array(usageTransactionItem),
	total: z.number(),
});

export const perTurnUsageItem = z.object({
	turn_key: z.string(),
	turn_type: z.string(),
	created_at: z.string(),
	capability: z.string(),
	resolved_model: z.string(),
	llm_tokens: z.number(),
	embedding_tokens: z.number(),
	recall_tokens: z.number(),
	cost_micros: z.number(),
	memories_created: z.number(),
	citations_generated: z.number(),
});

export const perTurnUsageResponse = z.object({
	workspace_id: z.number(),
	start_date: z.string(),
	end_date: z.string(),
	items: z.array(perTurnUsageItem),
	reconcile_warning: z.boolean(),
});

export const usageDateRange = z.object({
	start: z.string(),
	end: z.string(),
});

export type UsageDateRange = z.infer<typeof usageDateRange>;

export type UsageBreakdownItem = z.infer<typeof usageBreakdownItem>;
export type UsageSummaryResponse = z.infer<typeof usageSummaryResponse>;
export type UsageTimeSeriesPoint = z.infer<typeof usageTimeSeriesPoint>;
export type UsageTimeSeriesResponse = z.infer<typeof usageTimeSeriesResponse>;
export type UsageTransactionItem = z.infer<typeof usageTransactionItem>;
export type UsageTransactionsResponse = z.infer<typeof usageTransactionsResponse>;
export type PerTurnUsageItem = z.infer<typeof perTurnUsageItem>;
export type PerTurnUsageResponse = z.infer<typeof perTurnUsageResponse>;
