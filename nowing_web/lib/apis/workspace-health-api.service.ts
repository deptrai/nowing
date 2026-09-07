import {
	type CoverageGapsResponse,
	coverageGapsResponseSchema,
	type SourceBreakdownResponse,
	sourceBreakdownResponseSchema,
	type WorkspaceHealthRange,
	type WorkspaceHealthSummaryResponse,
	workspaceHealthSummaryResponseSchema,
} from "@/contracts/types/workspace-health.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}/health`;

class WorkspaceHealthApiService {
	/**
	 * Retrieve workspace health, adoption, sparklines, and quota analytics (AC-2).
	 */
	getHealthMetrics = async (
		workspaceId: number | string,
		range: WorkspaceHealthRange = "30d",
		startDate?: string,
		endDate?: string
	): Promise<WorkspaceHealthSummaryResponse> => {
		const params = new URLSearchParams();
		params.set("range", range);
		if (startDate) params.set("start_date", startDate);
		if (endDate) params.set("end_date", endDate);

		return baseApiService.get(
			`${base(workspaceId)}?${params.toString()}`,
			workspaceHealthSummaryResponseSchema
		);
	};

	/**
	 * Retrieve source-level drilldown with volume, cost, and recent memory samples (AC-3).
	 */
	getSourceDrilldown = async (
		workspaceId: number | string,
		sourceType: string
	): Promise<SourceBreakdownResponse> => {
		return baseApiService.get(
			`${base(workspaceId)}/sources/${encodeURIComponent(sourceType)}`,
			sourceBreakdownResponseSchema
		);
	};

	/**
	 * Identify enabled knowledge/scraper sources with zero memories in trailing 30 days (AC-4).
	 */
	getCoverageGaps = async (workspaceId: number | string): Promise<CoverageGapsResponse> => {
		return baseApiService.get(`${base(workspaceId)}/coverage-gaps`, coverageGapsResponseSchema);
	};

	/**
	 * Export workspace health metrics as CSV or JSON and trigger download (AC-6).
	 */
	downloadHealthExport = async (
		workspaceId: number | string,
		format: "csv" | "json" = "csv",
		range: WorkspaceHealthRange = "30d",
		startDate?: string,
		endDate?: string
	): Promise<void> => {
		const params = new URLSearchParams();
		params.set("format", format);
		params.set("range", range);
		if (startDate) params.set("start_date", startDate);
		if (endDate) params.set("end_date", endDate);

		const blob = await baseApiService.getBlob(`${base(workspaceId)}/export?${params.toString()}`);

		if (blob.size === 0) {
			throw new Error("Export returned an empty file");
		}

		if (typeof window !== "undefined") {
			const downloadUrl = window.URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = downloadUrl;
			a.download = `workspace_${workspaceId}_health_${range}.${format}`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			window.URL.revokeObjectURL(downloadUrl);
		}
	};
}

export const workspaceHealthApiService = new WorkspaceHealthApiService();
