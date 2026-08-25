import { BACKEND_URL } from "@/lib/env-config";

function buildUrl(path: string, workspaceId: number) {
	return `${BACKEND_URL}/api/v1/presentations${path}?workspace_id=${workspaceId}`;
}

export const presentationApiService = {
	downloadUrl(presentationId: string, workspaceId: number): string {
		return buildUrl(`/${presentationId}/download`, workspaceId);
	},
	previewUrl(presentationId: string, workspaceId: number): string {
		return buildUrl(`/${presentationId}/preview`, workspaceId);
	},
};
