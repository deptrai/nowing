import { BACKEND_URL } from "@/lib/env-config";

function buildUrl(path: string, workspaceId: number) {
	return `${BACKEND_URL}/api/v1/presentations${path}?workspace_id=${workspaceId}`;
}

/** Marp decks are Markdown; PPTX stays `.pptx`. Never label Marp as `.marp`. */
export function presentationFileExtension(format: string | undefined | null): string {
	return format === "marp" ? "md" : "pptx";
}

/** Only a backend-provided preview URL is safe to open (never invent PPTX preview). */
export function presentationPreviewHref(previewUrl: unknown): string {
	return typeof previewUrl === "string" ? previewUrl.trim() : "";
}

export const presentationApiService = {
	downloadUrl(presentationId: string, workspaceId: number): string {
		return buildUrl(`/${presentationId}/download`, workspaceId);
	},
	previewUrl(presentationId: string, workspaceId: number): string {
		return buildUrl(`/${presentationId}/preview`, workspaceId);
	},
};
