"use client";

import { z } from "zod";

const WebAppBuildResultSchema = z.object({
	app_id: z.string().optional(),
	workspace_id: z.number().optional(),
	name: z.string().optional(),
	slug: z.string().optional(),
	status: z.string().optional(),
	preview_url: z.string().nullish(),
	public_url: z.string().nullish(),
	message: z.string().nullish(),
	files: z.array(z.string()).nullish(),
	error: z.string().nullish(),
});

export type WebAppBuildResult = z.infer<typeof WebAppBuildResultSchema>;

export function parseWebAppResult(raw: unknown): Partial<WebAppBuildResult> {
	if (typeof raw === "object" && raw !== null) {
		const parsed = WebAppBuildResultSchema.safeParse(raw);
		if (parsed.success) return parsed.data;
	}
	if (typeof raw === "string") {
		try {
			const parsed = JSON.parse(raw);
			if (typeof parsed === "object" && parsed !== null) {
				const safe = WebAppBuildResultSchema.safeParse(parsed);
				if (safe.success) return safe.data;
			}
		} catch {
			return { message: raw, error: raw, status: "error" };
		}
	}
	return {};
}

export function isWebAppResultReady(result: Partial<WebAppBuildResult>): boolean {
	return Boolean(result.app_id && !result.error && result.status !== "error");
}
