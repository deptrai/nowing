import type { APIRequestContext } from "@playwright/test";
import { authHeaders, BACKEND_URL } from "./auth";

export type DocumentRow = {
	id: number;
	title: string;
	content: string;
	document_type: string;
	status: { state?: string } | string;
};

type Paginated<T> = {
	items?: T[];
	total?: number;
};

export async function listDocuments(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	limit = 100
): Promise<DocumentRow[]> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/documents?workspace_id=${workspaceId}&limit=${limit}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`listDocuments failed (${response.status()}): ${await response.text()}`);
	}
	const body = (await response.json()) as Paginated<DocumentRow> | DocumentRow[];
	return Array.isArray(body) ? body : (body.items ?? []);
}

export function isDocumentReady(doc: DocumentRow): boolean {
	const state = typeof doc.status === "string" ? doc.status : doc.status?.state;
	return state === "ready" || state === "READY";
}

export type EditorContent = {
	document_id: number;
	title: string;
	document_type: string;
	source_markdown: string;
	content_size_bytes: number;
	chunk_count: number;
	viewer_mode?: "plate" | "monaco";
	editor_plate_max_bytes?: number;
};

export type ChunkRow = {
	id: number;
	content: string;
	position: number;
	document_id: number;
	created_at: string;
};

type FileUploadResponse = {
	document_ids: number[];
	total_files: number;
	pending_files: number;
};

export async function uploadMarkdown(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	filename: string,
	content: string
): Promise<FileUploadResponse> {
	const response = await request.post(`${BACKEND_URL}/api/v1/documents/fileupload`, {
		multipart: {
			workspace_id: workspaceId.toString(),
			files: {
				name: filename,
				mimeType: "text/markdown",
				buffer: Buffer.from(content, "utf-8"),
			},
		},
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!response.ok()) {
		throw new Error(`uploadMarkdown failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as FileUploadResponse;
}

export async function waitForDocumentReady(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	documentId: number,
	options: { timeoutMs?: number; pollMs?: number } = {}
): Promise<DocumentRow> {
	const { timeoutMs = 30_000, pollMs = 500 } = options;
	const deadline = Date.now() + timeoutMs;
	let lastState = "";
	while (Date.now() < deadline) {
		const docs = await listDocuments(request, token, workspaceId);
		const doc = docs.find((d) => d.id === documentId);
		if (doc && isDocumentReady(doc)) {
			return doc;
		}
		lastState = doc ? JSON.stringify(doc.status) : "not found";
		await new Promise((resolve) => setTimeout(resolve, pollMs));
	}
	throw new Error(`Document ${documentId} did not become ready in time. Last state: ${lastState}`);
}

// Same endpoint the UI hits when a user opens a document in the dashboard.
export async function getEditorContent(
	request: APIRequestContext,
	token: string,
	workspaceId: number,
	documentId: number
): Promise<EditorContent> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/documents/${documentId}/editor-content`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`getEditorContent failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as EditorContent;
}

export async function getDocumentChunks(
	request: APIRequestContext,
	token: string,
	documentId: number,
	page = 0,
	pageSize = 100
): Promise<{ items: ChunkRow[]; total: number; page: number; page_size: number; has_more: boolean }> {
	const response = await request.get(
		`${BACKEND_URL}/api/v1/documents/${documentId}/chunks?page=${page}&page_size=${pageSize}`,
		{ headers: authHeaders(token) }
	);
	if (!response.ok()) {
		throw new Error(`getDocumentChunks failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as { items: ChunkRow[]; total: number; page: number; page_size: number; has_more: boolean };
}

export async function updateDocument(
	request: APIRequestContext,
	token: string,
	documentId: number,
	updates: { document_type?: string; content?: string; workspace_id?: number }
): Promise<DocumentRow> {
	const response = await request.put(`${BACKEND_URL}/api/v1/documents/${documentId}`, {
		headers: authHeaders(token),
		data: updates,
	});
	if (!response.ok()) {
		throw new Error(`updateDocument failed (${response.status()}): ${await response.text()}`);
	}
	return (await response.json()) as DocumentRow;
}
