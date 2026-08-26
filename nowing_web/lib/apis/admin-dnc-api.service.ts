"use client";

import type {
	GlobalDncCsvImportResponse,
	GlobalDncRecordCreate,
	GlobalDncRecordListResponse,
	GlobalDncRecordRead,
} from "@/contracts/types/admin-dnc.types";
import { baseApiService } from "./base-api.service";

class AdminDncApiService {
	list = async (
		params: { record_type?: string; search?: string; limit?: number; offset?: number } = {}
	): Promise<GlobalDncRecordListResponse> => {
		const searchParams = new URLSearchParams();
		if (params.record_type) searchParams.set("record_type", params.record_type);
		if (params.search) searchParams.set("search", params.search);
		if (params.limit !== undefined) searchParams.set("limit", String(params.limit));
		if (params.offset !== undefined) searchParams.set("offset", String(params.offset));

		const query = searchParams.toString();
		const url = `/api/v1/admin/dnc/global${query ? `?${query}` : ""}`;
		return baseApiService.get<GlobalDncRecordListResponse>(url);
	};

	create = async (payload: GlobalDncRecordCreate): Promise<GlobalDncRecordRead> => {
		return baseApiService.post<GlobalDncRecordRead>("/api/v1/admin/dnc/global", undefined, {
			body: payload,
		});
	};

	importCsv = async (file: File): Promise<GlobalDncCsvImportResponse> => {
		const formData = new FormData();
		formData.append("file", file);
		return baseApiService.postFormData<GlobalDncCsvImportResponse>(
			"/api/v1/admin/dnc/global/import-csv",
			undefined,
			{ body: formData }
		);
	};

	delete = async (recordId: string): Promise<void> => {
		return baseApiService.delete<void>(`/api/v1/admin/dnc/global/${recordId}`, undefined);
	};
}

export const adminDncApiService = new AdminDncApiService();
