"use client";

import type {
	AuditEventListResponse,
	AuditLogFilterParams,
} from "@/contracts/types/admin-audit-logs.types";
import { baseApiService } from "./base-api.service";

class AdminAuditLogsApiService {
	list = async (filters: AuditLogFilterParams = {}): Promise<AuditEventListResponse> => {
		const params = new URLSearchParams();
		if (filters.action) params.set("action", filters.action);
		if (filters.actor_id) params.set("actor_id", filters.actor_id);
		if (filters.actor_email) params.set("actor_email", filters.actor_email);
		if (filters.subject_id) params.set("subject_id", filters.subject_id);
		if (filters.subject_email) params.set("subject_email", filters.subject_email);
		if (filters.ticket_ref) params.set("ticket_ref", filters.ticket_ref);
		if (filters.start_date) params.set("start_date", filters.start_date);
		if (filters.end_date) params.set("end_date", filters.end_date);
		if (filters.limit !== undefined) params.set("limit", String(filters.limit));
		if (filters.offset !== undefined) params.set("offset", String(filters.offset));

		const query = params.toString();
		const url = `/api/v1/admin/audit-logs${query ? `?${query}` : ""}`;
		return baseApiService.get<AuditEventListResponse>(url);
	};
}

export const adminAuditLogsApiService = new AdminAuditLogsApiService();
