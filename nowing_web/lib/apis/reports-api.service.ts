import {
	type NarrativeReportCreateRequest,
	type NarrativeTemplateList,
	narrativeTemplateList,
	type ReportContentRead,
	type ReportListItem,
	reportContentRead,
	reportList,
} from "@/contracts/types/reports.types";
import { baseApiService } from "./base-api.service";

const BASE = "/workspaces";

class ReportsApiService {
	/**
	 * List all reports in the workspace.
	 */
	listReports = async (workspaceId: number): Promise<ReportListItem[]> => {
		return baseApiService.get(`${BASE}/${workspaceId}/reports`, reportList);
	};

	list = this.listReports;

	/**
	 * Fetch full report content by ID.
	 */
	getReportContent = async (workspaceId: number, reportId: number): Promise<ReportContentRead> => {
		return baseApiService.get(
			`${BASE}/${workspaceId}/reports/${reportId}/content`,
			reportContentRead
		);
	};

	/**
	 * List available narrative report templates (Story 6.12).
	 */
	listNarrativeTemplates = async (workspaceId: number): Promise<NarrativeTemplateList> => {
		return baseApiService.get(
			`${BASE}/${workspaceId}/reports/narrative/templates`,
			narrativeTemplateList
		);
	};

	/**
	 * Generate a structured narrative report on-demand (Story 6.12).
	 */
	generateNarrativeReport = async (
		workspaceId: number,
		data: NarrativeReportCreateRequest
	): Promise<ReportContentRead> => {
		return baseApiService.post(`${BASE}/${workspaceId}/reports/narrative`, reportContentRead, {
			body: data,
		});
	};
}

export const reportsApiService = new ReportsApiService();
