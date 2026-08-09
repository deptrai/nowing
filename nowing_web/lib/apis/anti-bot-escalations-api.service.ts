import { z } from "zod";

import { baseApiService } from "./base-api.service";

export const antiBotEscalation = z.object({
	id: z.number(),
	run_id: z.string(),
	workspace_id: z.number(),
	capability: z.string(),
	domain: z.string(),
	block_type: z.string(),
	screenshot_url: z.string().nullable(),
	status: z.enum(["open", "resolved", "retry"]),
	detection_count: z.number(),
	last_seen_at: z.string().nullable(),
	created_at: z.string(),
	resolved_at: z.string().nullable(),
});

export const antiBotEscalationList = z.object({
	items: z.array(antiBotEscalation),
	total: z.number(),
});

export type AntiBotEscalation = z.infer<typeof antiBotEscalation>;
export type AntiBotEscalationList = z.infer<typeof antiBotEscalationList>;

export const antiBotEscalationRetry = z.object({
	id: z.number(),
	status: z.string(),
	retry_run_id: z.string().nullable(),
	message: z.string(),
});

export type AntiBotEscalationRetry = z.infer<typeof antiBotEscalationRetry>;

export interface AntiBotEscalationFilters {
	workspace_id?: number;
	domain?: string;
	status?: "open" | "resolved" | "retry";
}

class AntiBotEscalationsApiService {
	private base = "/api/v1/admin/anti-bot-escalations";

	list = async (filters: AntiBotEscalationFilters = {}) => {
		const qs = new URLSearchParams();
		if (filters.workspace_id) qs.set("workspace_id", String(filters.workspace_id));
		if (filters.domain) qs.set("domain", filters.domain);
		if (filters.status) qs.set("status", filters.status);
		const query = qs.toString();
		const response = await baseApiService.get(
			`${this.base}${query ? `?${query}` : ""}`,
			antiBotEscalationList
		);
		return response.items;
	};

	get = async (id: number) => {
		return baseApiService.get(`${this.base}/${id}`, antiBotEscalation);
	};

	resolve = async (id: number) => {
		return baseApiService.post<AntiBotEscalation>(
			`${this.base}/${id}/resolve`,
			antiBotEscalation,
			{}
		);
	};

	retry = async (id: number) => {
		return baseApiService.post<AntiBotEscalationRetry>(
			`${this.base}/${id}/retry`,
			antiBotEscalationRetry,
			{}
		);
	};
}

export const antiBotEscalationsApiService = new AntiBotEscalationsApiService();
