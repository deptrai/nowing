import type {
	RuleSchema,
	ScraperRuleListResponse,
	ScraperRuleRead,
} from "@/contracts/types/scraper-rules.types";
import { buildBackendUrl } from "@/lib/env-config";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(buildBackendUrl(path), {
		...options,
		credentials: "include",
		headers: {
			"Content-Type": "application/json",
			...options?.headers,
		},
	});
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw Object.assign(new Error("API error"), { response: { status: res.status, data: body } });
	}
	return res.json() as Promise<T>;
}

export const scraperRulesApi = {
	list: async (): Promise<ScraperRuleListResponse> => {
		return request<ScraperRuleListResponse>("/api/v1/admin/scraper-rules");
	},
	get: async (platform: string): Promise<ScraperRuleRead> => {
		return request<ScraperRuleRead>(`/api/v1/admin/scraper-rules/${platform}`);
	},
	save: async (platform: string, rule_schema: RuleSchema): Promise<ScraperRuleRead> => {
		return request<ScraperRuleRead>(`/api/v1/admin/scraper-rules/${platform}`, {
			method: "POST",
			body: JSON.stringify({ rule_schema }),
		});
	},
	trip: async (platform: string): Promise<ScraperRuleRead> => {
		return request<ScraperRuleRead>(
			`/api/v1/admin/scraper-rules/${platform}/circuit-breaker/trip`,
			{
				method: "POST",
			}
		);
	},
	reset: async (platform: string): Promise<ScraperRuleRead> => {
		return request<ScraperRuleRead>(
			`/api/v1/admin/scraper-rules/${platform}/circuit-breaker/reset`,
			{
				method: "POST",
			}
		);
	},
};
