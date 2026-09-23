"use client";

import { baseApiService } from "./base-api.service";

export interface HealthStatusItem {
	id: number;
	category: string;
	service_id: string;
	service_name: string;
	display_group: string;
	status: "healthy" | "degraded" | "unavailable" | "disabled" | "not_configured";
	last_probe_at: string | null;
	next_probe_at: string | null;
	latency_ms: number | null;
	error_rate_15m: number;
	success_rate_15m: number;
	last_error: string | null;
	suggested_action?: string | null;
	metadata_payload: Record<string, unknown>;
	alert_threshold: Record<string, unknown> | null;
	acknowledged_until: string | null;
	updated_at: string;
}

export interface HealthHistoryItem {
	id: number;
	service_id: string;
	probe_at: string;
	status: string;
	latency_ms: number | null;
	error_message: string | null;
}

export interface HealthAlertItem {
	id: number;
	rule_id: number | null;
	service_id: string;
	status: "open" | "acknowledged" | "resolved";
	severity: "info" | "warning" | "critical";
	message: string;
	triggered_at: string;
	resolved_at: string | null;
	acknowledged_at: string | null;
	acknowledged_by: string | null;
	acknowledged_until: string | null;
}

export interface HealthOverviewResponse {
	overall_status: "healthy" | "degraded" | "unavailable";
	total_monitored: number;
	status_counts: {
		healthy: number;
		degraded: number;
		unavailable: number;
		not_configured: number;
		disabled: number;
	};
	active_alerts_count: number;
	categories: Record<
		string,
		{
			total: number;
			healthy: number;
			degraded: number;
			unavailable: number;
			not_configured: number;
			disabled: number;
		}
	>;
	registered_categories: string[];
}

export interface HealthStatusesListResponse {
	items: HealthStatusItem[];
	total: number;
}

export interface HealthAlertsListResponse {
	items: HealthAlertItem[];
	total: number;
}

export interface HealthHistoryListResponse {
	service_id: string;
	items: HealthHistoryItem[];
	total: number;
}

export interface HealthProbeResultResponse {
	service_id: string;
	service_name: string;
	category: string;
	display_group: string;
	status: string;
	latency_ms: number | null;
	last_error: string | null;
	suggested_action?: string | null;
	error_rate_15m: number;
	success_rate_15m: number;
	metadata: Record<string, unknown>;
	probed_at: string;
}

class AdminHealthApiService {
	getOverview = async (): Promise<HealthOverviewResponse> => {
		return baseApiService.get("/api/v1/admin/telemetry/health/overview");
	};

	getStatuses = async (
		opts: { category?: string; service_id?: string } = {}
	): Promise<HealthStatusesListResponse> => {
		const params = new URLSearchParams();
		if (opts.category) params.set("category", opts.category);
		if (opts.service_id) params.set("service_id", opts.service_id);
		const query = params.toString();
		return baseApiService.get(`/api/v1/admin/telemetry/health/statuses${query ? `?${query}` : ""}`);
	};

	getActiveAlerts = async (): Promise<HealthAlertsListResponse> => {
		return baseApiService.get("/api/v1/admin/telemetry/health/alerts");
	};

	acknowledgeAlert = async (alertId: number, durationMinutes = 60): Promise<HealthAlertItem> => {
		return baseApiService.post(
			`/api/v1/admin/telemetry/health/alerts/${alertId}/acknowledge`,
			undefined,
			{
				body: { duration_minutes: durationMinutes },
			}
		);
	};

	getHistory = async (serviceId: string, hours = 24): Promise<HealthHistoryListResponse> => {
		return baseApiService.get(
			`/api/v1/admin/telemetry/health/history/${encodeURIComponent(serviceId)}?hours=${hours}`
		);
	};

	runProbe = async (serviceId: string): Promise<HealthProbeResultResponse> => {
		return baseApiService.post(
			`/api/v1/admin/telemetry/health/probe/${encodeURIComponent(serviceId)}`,
			undefined,
			{
				body: {},
			}
		);
	};
}

export const adminHealthApiService = new AdminHealthApiService();
