import type {
	CustomDomainInput,
	CustomDomainOutput,
	MarkToolInput,
	MarkToolOutput,
	WebAppBuildInput,
	WebAppBuildOutput,
	WebAppDeployInput,
	WebAppDeployOutput,
	WebBuilderStreamEvent,
	WorkspaceApp,
} from "@/contracts/types/web-builder.types";
import { buildBackendUrl } from "@/lib/env-config";
import { baseApiService } from "./base-api.service";

class WebBuilderApiService {
	generateWebApp = async (payload: WebAppBuildInput): Promise<WebAppBuildOutput> => {
		return baseApiService.post("/api/v1/web-builder/generate", undefined, { body: payload });
	};

	generateWebAppStream = async (
		payload: WebAppBuildInput,
		onEvent: (event: WebBuilderStreamEvent) => void,
		signal?: AbortSignal
	): Promise<void> => {
		const streamUrl = buildBackendUrl("/api/v1/web-builder/generate/stream");
		const response = await fetch(streamUrl, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(payload),
			signal,
			credentials: "include",
		});

		if (!response.ok) {
			const err = await response.text();
			throw new Error(err || "Streaming failed");
		}

		if (!response.body) return;

		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";

		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split("\n\n");
			buffer = lines.pop() || "";

			for (const line of lines) {
				const trimmed = line.trim();
				if (trimmed.startsWith("data: ")) {
					try {
						const data = JSON.parse(trimmed.slice(6));
						onEvent(data);
					} catch {
						// ignore unparseable chunk
					}
				}
			}
		}
	};

	getAppFiles = async (
		appId: string,
		workspaceId: number | string
	): Promise<Record<string, string>> => {
		return baseApiService.get(
			`/api/v1/web-builder/apps/${appId}/files?workspace_id=${workspaceId}`
		);
	};

	publishWebApp = async (
		appId: string,
		payload: WebAppDeployInput
	): Promise<WebAppDeployOutput> => {
		return baseApiService.post(`/api/v1/web-builder/apps/${appId}/publish`, undefined, {
			body: payload,
		});
	};

	configureCustomDomain = async (
		appId: string,
		payload: CustomDomainInput
	): Promise<CustomDomainOutput> => {
		return baseApiService.post(`/api/v1/web-builder/apps/${appId}/custom-domain`, undefined, {
			body: payload,
		});
	};

	applyMarkToolPatch = async (appId: string, payload: MarkToolInput): Promise<MarkToolOutput> => {
		return baseApiService.post(`/api/v1/web-builder/apps/${appId}/mark`, undefined, {
			body: payload,
		});
	};

	listApps = async (workspaceId: number | string): Promise<WorkspaceApp[]> => {
		return baseApiService.get(`/api/v1/web-builder/apps?workspace_id=${workspaceId}`);
	};

	getApp = async (appId: string, workspaceId: number | string): Promise<WorkspaceApp> => {
		return baseApiService.get(`/api/v1/web-builder/apps/${appId}?workspace_id=${workspaceId}`);
	};
}

export const webBuilderApiService = new WebBuilderApiService();
