import { getBearerToken } from "../auth-utils";

const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

export interface ChatRun {
	id: string;
	thread_id: number;
	session_id: string;
	status: "running" | "completed" | "failed" | "cancelled" | "abandoned";
	user_query: string | null;
	started_at: string;
	completed_at: string | null;
	final_message_id: number | null;
}

export interface StartRunRequest {
	search_space_id: number;
	user_query: string;
	mentioned_document_ids?: number[] | null;
	disabled_tools?: string[] | null;
	model_id?: number | null;
}

function _authHeaders(): HeadersInit {
	const token = getBearerToken();
	return {
		"Content-Type": "application/json",
		...(token ? { Authorization: `Bearer ${token}` } : {}),
	};
}

export async function startRun(threadId: number, request: StartRunRequest): Promise<ChatRun> {
	const response = await fetch(`${backendUrl}/api/v1/threads/${threadId}/runs`, {
		method: "POST",
		headers: _authHeaders(),
		body: JSON.stringify(request),
	});
	if (!response.ok) {
		throw new Error(`startRun failed: ${response.status}`);
	}
	return response.json();
}

export async function getActiveRuns(threadId: number): Promise<ChatRun[]> {
	const response = await fetch(`${backendUrl}/api/v1/threads/${threadId}/runs/active`, {
		headers: _authHeaders(),
	});
	if (!response.ok) {
		throw new Error(`getActiveRuns failed: ${response.status}`);
	}
	return response.json();
}

export function streamRun(
	threadId: number,
	runId: string,
	afterSeq = -1,
	signal?: AbortSignal
): Promise<Response> {
	const token = getBearerToken();
	return fetch(
		`${backendUrl}/api/v1/threads/${threadId}/runs/${runId}/stream?after_seq=${afterSeq}`,
		{
			headers: {
				Accept: "text/event-stream",
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
			signal,
		}
	);
}

export async function cancelRun(threadId: number, runId: string): Promise<{ cancelled: boolean }> {
	const response = await fetch(`${backendUrl}/api/v1/threads/${threadId}/runs/${runId}/cancel`, {
		method: "POST",
		headers: _authHeaders(),
	});
	if (!response.ok) {
		throw new Error(`cancelRun failed: ${response.status}`);
	}
	return response.json();
}

export async function resumeRun(threadId: number, runId: string): Promise<ChatRun> {
	const response = await fetch(`${backendUrl}/api/v1/threads/${threadId}/runs/${runId}/resume`, {
		method: "POST",
		headers: _authHeaders(),
	});
	if (!response.ok) {
		throw new Error(`resumeRun failed: ${response.status}`);
	}
	return response.json();
}
