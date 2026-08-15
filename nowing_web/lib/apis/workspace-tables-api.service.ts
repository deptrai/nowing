import { z } from "zod";
import {
	type ExportJobResponse,
	type ExportRequestPayload,
	exportJobResponseSchema,
	type WorkspaceTable,
	type WorkspaceTableCreate,
	type WorkspaceTableUpdate,
	workspaceTableSchema,
} from "@/contracts/types/workspace-table.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}`;

class WorkspaceTablesApiService {
	listTables = async (workspaceId: number | string): Promise<WorkspaceTable[]> => {
		return baseApiService.get(`${base(workspaceId)}/tables`, z.array(workspaceTableSchema));
	};

	getTable = async (workspaceId: number | string, tableId: string): Promise<WorkspaceTable> => {
		return baseApiService.get(`${base(workspaceId)}/tables/${tableId}`, workspaceTableSchema);
	};

	createTable = async (
		workspaceId: number | string,
		payload: WorkspaceTableCreate
	): Promise<WorkspaceTable> => {
		return baseApiService.post(`${base(workspaceId)}/tables`, workspaceTableSchema, {
			body: payload,
		});
	};

	updateTable = async (
		workspaceId: number | string,
		tableId: string,
		payload: WorkspaceTableUpdate
	): Promise<WorkspaceTable> => {
		return baseApiService.patch(`${base(workspaceId)}/tables/${tableId}`, workspaceTableSchema, {
			body: payload,
		});
	};

	deleteTable = async (workspaceId: number | string, tableId: string): Promise<void> => {
		await baseApiService.delete(`${base(workspaceId)}/tables/${tableId}`);
	};

	assignLeads = async (
		workspaceId: number | string,
		tableId: string,
		leadIds: string[]
	): Promise<{ assigned_count: number; table_id: string }> => {
		return baseApiService.post(
			`${base(workspaceId)}/tables/${tableId}/assign-leads`,
			z.object({
				assigned_count: z.number(),
				table_id: z.string(),
			}),
			{ body: { lead_ids: leadIds, table_id: tableId } }
		);
	};

	triggerExport = async (
		workspaceId: number | string,
		payload: ExportRequestPayload
	): Promise<ExportJobResponse> => {
		return baseApiService.post(`${base(workspaceId)}/leads/export`, exportJobResponseSchema, {
			body: payload,
		});
	};

	downloadCsv = async (
		workspaceId: number | string,
		tableId?: string | null,
		leadIds?: string[],
		maskPii = true
	): Promise<void> => {
		const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
		const res = await fetch(`${backendUrl}/workspaces/${workspaceId}/leads/export`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			credentials: "include",
			body: JSON.stringify({
				export_type: "csv",
				table_id: tableId || null,
				lead_ids: leadIds || null,
				mask_pii: maskPii,
			}),
		});

		if (!res.ok) {
			throw new Error(`Export CSV failed: ${res.statusText}`);
		}

		const blob = await res.blob();
		const downloadUrl = window.URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = downloadUrl;
		a.download = `leads_export_${new Date().toISOString().slice(0, 10)}.csv`;
		document.body.appendChild(a);
		a.click();
		a.remove();
		window.URL.revokeObjectURL(downloadUrl);
	};

	getExportJobStatus = async (
		workspaceId: number | string,
		jobId: string
	): Promise<ExportJobResponse> => {
		return baseApiService.get(
			`${base(workspaceId)}/leads/export/jobs/${jobId}`,
			exportJobResponseSchema
		);
	};
}

export const workspaceTablesApiService = new WorkspaceTablesApiService();
