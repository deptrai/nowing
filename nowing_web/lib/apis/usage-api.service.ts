import {
	type PerTurnUsageResponse,
	perTurnUsageResponse,
	type UsageDateRange,
	type UsageSummaryResponse,
	type UsageTimeSeriesResponse,
	type UsageTransactionsResponse,
	usageSummaryResponse,
	usageTimeSeriesResponse,
	usageTransactionsResponse,
} from "@/contracts/types/usage.types";
import { baseApiService } from "./base-api.service";

export type { UsageDateRange };

class UsageApiService {
	getSummary = async (
		workspaceId: number,
		range: UsageDateRange
	): Promise<UsageSummaryResponse> => {
		const params = new URLSearchParams({
			workspace_id: String(workspaceId),
			start_date: range.start,
			end_date: range.end,
		});
		return baseApiService.get(`/api/v1/usage/summary?${params.toString()}`, usageSummaryResponse);
	};

	getTimeSeries = async (
		workspaceId: number,
		granularity: "day" | "week" | "month",
		range: UsageDateRange
	): Promise<UsageTimeSeriesResponse> => {
		const params = new URLSearchParams({
			workspace_id: String(workspaceId),
			granularity,
			start_date: range.start,
			end_date: range.end,
		});
		return baseApiService.get(
			`/api/v1/usage/time-series?${params.toString()}`,
			usageTimeSeriesResponse
		);
	};

	getTransactions = async (limit = 50, offset = 0): Promise<UsageTransactionsResponse> => {
		const params = new URLSearchParams({
			limit: String(limit),
			offset: String(offset),
		});
		return baseApiService.get(
			`/api/v1/usage/transactions?${params.toString()}`,
			usageTransactionsResponse
		);
	};

	getPerTurn = async (
		workspaceId: number,
		range: UsageDateRange
	): Promise<PerTurnUsageResponse> => {
		const params = new URLSearchParams({
			workspace_id: String(workspaceId),
			start_date: range.start,
			end_date: range.end,
		});
		return baseApiService.get(`/api/v1/usage/per-turn?${params.toString()}`, perTurnUsageResponse);
	};
}

export const usageApiService = new UsageApiService();
