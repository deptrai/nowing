import type {
	CustomDomainInput,
	CustomDomainOutput,
	MarkToolInput,
	MarkToolOutput,
	WebAppBuildInput,
	WebAppBuildOutput,
	WebAppDeployInput,
	WebAppDeployOutput,
	WorkspaceApp,
} from "@/contracts/types/web-builder.types";
import { baseApiService } from "./base-api.service";

class WebBuilderApiService {
	generateWebApp = async (payload: WebAppBuildInput): Promise<WebAppBuildOutput> => {
		return baseApiService.post("/api/v1/web-builder/generate", undefined, { body: payload });
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
