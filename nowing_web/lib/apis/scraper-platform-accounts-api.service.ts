import { z } from "zod";

import { baseApiService } from "./base-api.service";

export const scraperPlatformAccountCredentials = z.object({
	cookies: z.string().optional().nullable(),
	token: z.string().optional().nullable(),
});

export const scraperPlatformAccount = z.object({
	id: z.number(),
	platform: z.string(),
	label: z.string().nullable(),
	is_enabled: z.boolean(),
	is_default: z.boolean(),
	credentials: scraperPlatformAccountCredentials.nullable().optional(),
	created_at: z.string(),
	updated_at: z.string(),
});

export const scraperPlatformAccountsList = z.array(scraperPlatformAccount);

export type ScraperPlatformAccount = z.infer<typeof scraperPlatformAccount>;
export type ScraperPlatformAccountCredentials = z.infer<typeof scraperPlatformAccountCredentials>;

export interface ScraperPlatformAccountCreate {
	platform: string;
	label?: string | null;
	is_enabled?: boolean;
	is_default?: boolean;
	credentials?: ScraperPlatformAccountCredentials | null;
}

export interface ScraperPlatformAccountUpdate {
	label?: string | null;
	is_enabled?: boolean;
	is_default?: boolean;
	credentials?: ScraperPlatformAccountCredentials | null;
}

class ScraperPlatformAccountsApiService {
	private base = "/api/v1/admin/scraper-platform-accounts";

	list = async (platform?: string) => {
		const qs = new URLSearchParams();
		if (platform) qs.set("platform", platform);
		const query = qs.toString();
		return baseApiService.get(
			`${this.base}${query ? `?${query}` : ""}`,
			scraperPlatformAccountsList
		);
	};

	get = async (id: number) => {
		return baseApiService.get(`${this.base}/${id}`, scraperPlatformAccount);
	};

	create = async (data: ScraperPlatformAccountCreate) => {
		return baseApiService.post<ScraperPlatformAccount>(this.base, scraperPlatformAccount, {
			body: data,
		});
	};

	update = async (id: number, data: ScraperPlatformAccountUpdate) => {
		return baseApiService.patch<ScraperPlatformAccount>(
			`${this.base}/${id}`,
			scraperPlatformAccount,
			{ body: data }
		);
	};

	delete = async (id: number) => {
		return baseApiService.delete(`${this.base}/${id}`);
	};
}

export const scraperPlatformAccountsApiService = new ScraperPlatformAccountsApiService();
