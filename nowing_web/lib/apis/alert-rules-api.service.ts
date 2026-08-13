import {
	type AlertSnapshotListResponse,
	alertRule,
	alertSnapshotListResponse,
} from "@/contracts/types/alert-rules.types";
import { baseApiService } from "./base-api.service";

const BASE = "/workspaces";

class AlertRulesApiService {
	/**
	 * Fetch a single saved search (alert rule) within a workspace.
	 */
	getAlertRule = async (workspaceId: number, alertRuleId: string) => {
		return baseApiService.get(`${BASE}/${workspaceId}/alert-rules/${alertRuleId}`, alertRule);
	};

	/**
	 * Fetch run snapshots for a saved search, newest first.
	 */
	listSnapshots = async (
		workspaceId: number,
		alertRuleId: string,
		limit: number = 20
	): Promise<AlertSnapshotListResponse> => {
		return baseApiService.get(
			`${BASE}/${workspaceId}/alert-rules/${alertRuleId}/snapshots?limit=${limit}`,
			alertSnapshotListResponse
		);
	};
}

export const alertRulesApiService = new AlertRulesApiService();
