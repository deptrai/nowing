import {
	type DncCsvImportResponse,
	type DncListResponse,
	type DncRecord,
	type DncRecordCreate,
	dncCsvImportResponseSchema,
	dncListResponseSchema,
	dncRecordSchema,
	type PiiPurgeResponse,
	piiPurgeResponseSchema,
} from "@/contracts/types/dnc.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}`;

class DncApiService {
	listDncRecords = async (
		workspaceId: number | string,
		params: {
			record_type?: string;
			search?: string;
			page?: number;
			page_size?: number;
		} = {}
	): Promise<DncListResponse> => {
		const qs = new URLSearchParams();
		if (params.record_type) qs.set("record_type", params.record_type);
		if (params.search) qs.set("search", params.search);
		if (params.page) qs.set("page", String(params.page));
		if (params.page_size) qs.set("page_size", String(params.page_size));

		const query = qs.toString();
		return baseApiService.get(
			`${base(workspaceId)}/dnc${query ? `?${query}` : ""}`,
			dncListResponseSchema
		);
	};

	createDncRecord = async (
		workspaceId: number | string,
		payload: DncRecordCreate
	): Promise<DncRecord> => {
		return baseApiService.post(`${base(workspaceId)}/dnc`, dncRecordSchema, { body: payload });
	};

	deleteDncRecord = async (workspaceId: number | string, recordId: string): Promise<void> => {
		await baseApiService.delete(`${base(workspaceId)}/dnc/${recordId}`);
	};

	importDncCsv = async (
		workspaceId: number | string,
		file: File
	): Promise<DncCsvImportResponse> => {
		const formData = new FormData();
		formData.append("file", file);

		return baseApiService.post(`${base(workspaceId)}/dnc/import-csv`, dncCsvImportResponseSchema, {
			body: formData,
		});
	};

	purgeLeadPii = async (leadId: string): Promise<PiiPurgeResponse> => {
		return baseApiService.delete(`/api/v1/leads/${leadId}/pii`, piiPurgeResponseSchema);
	};
}

export const dncApiService = new DncApiService();
