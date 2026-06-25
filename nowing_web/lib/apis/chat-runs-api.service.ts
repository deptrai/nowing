import { getBearerToken } from "../auth-utils";
import { readSSEStream, type SSEEvent } from "../chat/streaming-state";
import { QuotaExceededError, StreamMaxRetriesError } from "../error";

export const STREAM_MAX_RETRIES = 5;

const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

/**
 * Exponential backoff delay.
 * @param attempt current attempt number (0-based)
 * @param baseDelay initial delay in ms
 * @param maxDelay maximum delay in ms
 */
export async function exponentialBackoff(
	attempt: number,
	baseDelay = 1000,
	maxDelay = 30000
): Promise<void> {
	const delay = Math.min(maxDelay, baseDelay * 2 ** attempt);
	const jitter = Math.random() * 1000;
	return new Promise((resolve) => setTimeout(resolve, delay + jitter));
}

export interface ChatRun {
	id: string;
	thread_id: number;
	session_id: string;
	/** T21: matches OrchestraSession.sessionId for resume linking. */
	langgraph_thread_id: string;
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
	mentioned_nowing_doc_ids?: number[] | null;
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

/**
 * Generic stream with retry and exponential backoff.
 * @param urlFactory function to generate URL (can include currentSeq)
 * @param options fetch options
 * @param initialSeq starting sequence number
 * @param signal optional abort signal
 */
export async function* streamWithRetry(
	urlFactory: (seq: number) => string,
	options: RequestInit,
	initialSeq = -1,
	signal?: AbortSignal,
	maxRetries = STREAM_MAX_RETRIES
): AsyncGenerator<SSEEvent> {
	let currentSeq = initialSeq;
	let attempt = 0;

	while (true) {
		if (signal?.aborted) return;

		let receivedAny = false;

		try {
			const response = await fetch(urlFactory(currentSeq), {
				...options,
				signal,
			});

			if (!response.ok) {
				if (response.status === 402) {
					throw new QuotaExceededError();
				}
				if (
					response.status === 401 ||
					response.status === 403 ||
					response.status === 404
				) {
					throw new Error(`Terminal stream error: ${response.status}`);
				}
				throw new Error(`Retriable stream error: ${response.status}`);
			}

			for await (const event of readSSEStream(response)) {
				// biome-ignore lint/suspicious/noExplicitAny: SSEEvent might have seq
				const anyEvent = event as any;
				// 11-1 AC#4: Track seq from structured payloads OR from _seq markers
				// (the latter is emitted by the backend for legacy `_raw` and `_vercel`
				// payloads where seq cannot be injected directly).
				if (anyEvent._seq != null && typeof anyEvent._seq === "number") {
					currentSeq = anyEvent._seq;
					// _seq markers are bookkeeping only — do not yield to consumer.
					continue;
				}
				if (anyEvent.seq != null && typeof anyEvent.seq === "number") {
					currentSeq = anyEvent.seq;
				}

				if (!receivedAny) {
					attempt = 0; // Only reset when we actually got a event
					receivedAny = true;
				}

				yield event;

				if (anyEvent._marker === "run-end") {
					return;
				}
			}

			// Stream closed without run-end. Treat as retriable failure (with backoff).
			console.warn("[streamWithRetry] Stream closed without run-end marker, retrying...");
			if (attempt >= maxRetries) {
				throw new StreamMaxRetriesError();
			}
			await exponentialBackoff(attempt++);
		} catch (err) {
			if (signal?.aborted) return;

			if (err instanceof Error && err.message.startsWith("Terminal")) {
				throw err;
			}
			if (err instanceof QuotaExceededError) {
				throw err;
			}
			if (err instanceof StreamMaxRetriesError) {
				throw err;
			}

			if (attempt >= maxRetries) {
				console.error(`[streamWithRetry] Max retries (${maxRetries}) exceeded`, err);
				throw new StreamMaxRetriesError();
			}

			console.warn(`[streamWithRetry] Connection lost (attempt ${attempt}), retrying...`, err);
			await exponentialBackoff(attempt++);
		}
	}
}

/**
 * SSE: replay persisted events then tail live via Redis pubsub.
 * Automatically handles reconnection with exponential backoff.
 */
export async function* streamRun(
	threadId: number,
	runId: string,
	afterSeq = -1,
	signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
	const token = getBearerToken();
	const urlFactory = (seq: number) =>
		`${backendUrl}/api/v1/threads/${threadId}/runs/${runId}/stream?after_seq=${seq}`;

	yield* streamWithRetry(
		urlFactory,
		{
			headers: {
				Accept: "text/event-stream",
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
		},
		afterSeq,
		signal
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
