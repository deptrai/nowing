"use client";

import { baseApiService } from "./base-api.service";

export interface LlmCostBucket {
	key: string;
	total_tokens: number;
	cost_micros: number;
	input_tokens: number;
	output_tokens: number;
}

export interface LlmCostTimeSeriesPoint {
	period: string;
	total_tokens: number;
	cost_micros: number;
	input_tokens: number;
	output_tokens: number;
}

export interface LlmCostBreakdown {
	window_hours: number;
	provider: string | null;
	workspace_id: number | null;
	total_tokens: number;
	total_cost_micros: number;
	non_llm_cost_micros: number;
	billing_cost_micros: number;
	input_tokens: number;
	output_tokens: number;
	by_provider: LlmCostBucket[];
	by_model: LlmCostBucket[];
	by_workspace: LlmCostBucket[];
	by_usage_type: LlmCostBucket[];
	time_series: LlmCostTimeSeriesPoint[];
	unreported_cost_rows: number;
}

export interface GrossMarginPoint {
	period: string;
	revenue_micros: number;
	cogs_micros: number;
	gross_margin: number | null;
}

export interface GrossMarginSummary {
	window_hours: number;
	total_revenue_micros: number;
	total_cogs_micros: number;
	billing_cost_micros: number;
	non_llm_cost_micros: number;
	overall_gross_margin: number | null;
	worst_workspace_id: number | null;
	worst_workspace_margin: number | null;
	worst_model: string | null;
	points: GrossMarginPoint[];
}

export interface ProxyHealthSnapshot {
	provider: string;
	url: string | null;
	latency_ms: number | null;
	success_rate: number;
	status: string;
	last_error: string | null;
	last_probed_at: string | null;
}

export interface ProxyHealthResponse {
	status: string;
	provider: string;
	snapshots: ProxyHealthSnapshot[];
	total: number;
	healthy: number;
	degraded: number;
	dead: number;
}

export interface CeleryQueueInfo {
	name: string;
	length: number;
	workers: number;
	throughput_per_min: number;
	stalled_count: number;
	status: string;
}

export interface CeleryQueueResponse {
	status: string;
	active_workers: number;
	queues: CeleryQueueInfo[];
}

export interface PurgeDeadQueueResponse {
	queue_name: string;
	purged_count: number;
	idempotency_key: string;
}

type WindowHours = 1 | 6 | 24 | 168 | 720;

class AdminTelemetryApiService {
	llmCost = async (
		opts: { window_hours?: WindowHours; provider?: string; workspace_id?: number } = {}
	): Promise<LlmCostBreakdown> => {
		const params = new URLSearchParams();
		if (opts.window_hours !== undefined) {
			params.set("window_hours", String(opts.window_hours));
		}
		if (opts.provider) {
			params.set("provider", opts.provider);
		}
		if (opts.workspace_id !== undefined) {
			params.set("workspace_id", String(opts.workspace_id));
		}
		const query = params.toString();
		const url = `/api/v1/admin/telemetry/llm-cost${query ? `?${query}` : ""}`;
		return baseApiService.get(url);
	};

	grossMargin = async (opts: { window_hours?: WindowHours } = {}): Promise<GrossMarginSummary> => {
		const params = new URLSearchParams();
		if (opts.window_hours !== undefined) {
			params.set("window_hours", String(opts.window_hours));
		}
		const query = params.toString();
		const url = `/api/v1/admin/telemetry/gross-margin${query ? `?${query}` : ""}`;
		return baseApiService.get(url);
	};

	proxyHealth = async (): Promise<ProxyHealthResponse> => {
		return baseApiService.get("/api/v1/admin/telemetry/proxy-health");
	};

	celeryQueues = async (): Promise<CeleryQueueResponse> => {
		return baseApiService.get("/api/v1/admin/telemetry/celery-queues");
	};

	purgeDeadQueue = async (queueName: string): Promise<PurgeDeadQueueResponse> => {
		return baseApiService.post(
			`/api/v1/admin/telemetry/celery-queues/${queueName}/purge`,
			undefined,
			{
				body: {},
			}
		);
	};
}

export const adminTelemetryApiService = new AdminTelemetryApiService();
