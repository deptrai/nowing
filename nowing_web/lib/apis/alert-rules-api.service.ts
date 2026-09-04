import {
	type AlertRule,
	type AlertSnapshotListResponse,
	type AlertTemplateListResponse,
	alertRule,
	alertSnapshotListResponse,
	alertTemplateListResponse,
	type CreateAlertFromTemplateRequest,
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

	/**
	 * Fetch vertical alert rule templates for 1-click instantiation (Story 6.11).
	 */
	listTemplates = async (workspaceId: number): Promise<AlertTemplateListResponse> => {
		return baseApiService.get(`${BASE}/${workspaceId}/alerts/templates`, alertTemplateListResponse);
	};

	/**
	 * Instantiate a new alert rule from a vertical template in 1 click (Story 6.11).
	 */
	createFromTemplate = async (
		workspaceId: number,
		data: CreateAlertFromTemplateRequest
	): Promise<AlertRule> => {
		return baseApiService.post(`${BASE}/${workspaceId}/alerts/from-template`, alertRule, {
			body: data,
		});
	};
}

export const alertRulesApiService = new AlertRulesApiService();
