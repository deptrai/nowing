export type DncRecordType = "phone" | "domain" | "email" | "tax_id";

export interface GlobalDncRecordRead {
	id: string;
	record_type: DncRecordType;
	value?: string | null;
	value_hmac: string;
	reason?: string | null;
	source: string;
	created_at: string;
}

export interface GlobalDncRecordListResponse {
	items: GlobalDncRecordRead[];
	total: number;
	limit: number;
	offset: number;
}

export interface GlobalDncRecordCreate {
	record_type: DncRecordType;
	value: string;
	reason?: string;
	source?: string;
}

export interface GlobalDncCsvImportResponse {
	imported_count: number;
	skipped_count: number;
	failed_count: number;
	errors: string[];
}
