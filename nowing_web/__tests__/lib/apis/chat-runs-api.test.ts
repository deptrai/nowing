/**
 * Unit tests — lib/apis/chat-runs-api.service.ts
 * Covers: startRun, getActiveRuns, streamRun, cancelRun, resumeRun
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth-utils", () => ({
	getBearerToken: vi.fn(() => "tok_test"),
}));

import { getBearerToken } from "@/lib/auth-utils";
import {
	startRun,
	getActiveRuns,
	streamRun,
	cancelRun,
	resumeRun,
	type ChatRun,
	type StartRunRequest,
} from "@/lib/apis/chat-runs-api.service";

const MOCK_RUN: ChatRun = {
	id: "run-uuid-1",
	thread_id: 42,
	session_id: "sess-1",
	langgraph_thread_id: "lg-thread-1",
	status: "running",
	user_query: "analyze BTC",
	started_at: "2026-04-27T00:00:00Z",
	completed_at: null,
	final_message_id: null,
};

const MOCK_REQUEST: StartRunRequest = {
	search_space_id: 1,
	user_query: "analyze BTC",
};

function mockFetch(body: unknown, ok = true, status = 200) {
	return vi.fn().mockResolvedValue({
		ok,
		status,
		json: () => Promise.resolve(body),
	});
}

beforeEach(() => {
	vi.clearAllMocks();
	vi.mocked(getBearerToken).mockReturnValue("tok_test");
});

// ---------------------------------------------------------------------------
// startRun
// ---------------------------------------------------------------------------

describe("startRun", () => {
	it("sends POST with correct URL, headers, and body", async () => {
		globalThis.fetch = mockFetch(MOCK_RUN);
		const result = await startRun(42, MOCK_REQUEST);

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/v1/threads/42/runs"),
			expect.objectContaining({
				method: "POST",
				headers: expect.objectContaining({
					"Content-Type": "application/json",
					Authorization: "Bearer tok_test",
				}),
				body: JSON.stringify(MOCK_REQUEST),
			})
		);
		expect(result).toEqual(MOCK_RUN);
	});

	it("throws on non-ok response", async () => {
		globalThis.fetch = mockFetch(null, false, 500);
		await expect(startRun(42, MOCK_REQUEST)).rejects.toThrow("startRun failed: 500");
	});

	it("omits Authorization header when no token", async () => {
		vi.mocked(getBearerToken).mockReturnValue(null);
		globalThis.fetch = mockFetch(MOCK_RUN);
		await startRun(42, MOCK_REQUEST);

		const headers = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
		expect(headers).not.toHaveProperty("Authorization");
	});
});

// ---------------------------------------------------------------------------
// getActiveRuns
// ---------------------------------------------------------------------------

describe("getActiveRuns", () => {
	it("sends GET to correct URL with auth header", async () => {
		globalThis.fetch = mockFetch([MOCK_RUN]);
		const result = await getActiveRuns(42);

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/v1/threads/42/runs/active"),
			expect.objectContaining({
				headers: expect.objectContaining({
					Authorization: "Bearer tok_test",
				}),
			})
		);
		expect(result).toEqual([MOCK_RUN]);
	});

	it("returns empty array when no active runs", async () => {
		globalThis.fetch = mockFetch([]);
		const result = await getActiveRuns(99);
		expect(result).toEqual([]);
	});

	it("throws on non-ok response", async () => {
		globalThis.fetch = mockFetch(null, false, 403);
		await expect(getActiveRuns(42)).rejects.toThrow("getActiveRuns failed: 403");
	});
});

// ---------------------------------------------------------------------------
// streamRun
// ---------------------------------------------------------------------------

describe("streamRun", () => {
	// Helper: drive the generator far enough to trigger one fetch, then abort
	// to cleanly terminate the retry loop. We intercept fetch so abort happens
	// AFTER the first fetch call is recorded.
	function makeFetchAndAbort(controller: AbortController, response: unknown) {
		return vi.fn().mockImplementation(async () => {
			// Schedule abort on the next microtask so the caller has already
			// captured the fetch invocation but hasn't yet processed the body.
			queueMicrotask(() => controller.abort());
			return response;
		});
	}

	it("sends GET with Accept text/event-stream and default afterSeq", async () => {
		const controller = new AbortController();
		globalThis.fetch = makeFetchAndAbort(controller, { ok: true, body: null });

		const gen = streamRun(42, "run-uuid-1", -1, controller.signal);
		await gen.next();

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/v1/threads/42/runs/run-uuid-1/stream?after_seq=-1"),
			expect.objectContaining({
				headers: expect.objectContaining({
					Accept: "text/event-stream",
					Authorization: "Bearer tok_test",
				}),
			})
		);
	});

	it("uses custom afterSeq parameter", async () => {
		const controller = new AbortController();
		globalThis.fetch = makeFetchAndAbort(controller, { ok: true, body: null });

		const gen = streamRun(42, "run-uuid-1", 15, controller.signal);
		await gen.next();

		expect(fetch).toHaveBeenCalledWith(expect.stringContaining("after_seq=15"), expect.anything());
	});

	it("passes AbortSignal when provided", async () => {
		const controller = new AbortController();
		globalThis.fetch = makeFetchAndAbort(controller, { ok: true, body: null });
		const gen = streamRun(42, "run-uuid-1", -1, controller.signal);
		await gen.next();

		expect(fetch).toHaveBeenCalledWith(
			expect.anything(),
			expect.objectContaining({ signal: controller.signal })
		);
	});

	it("omits Authorization header when no token", async () => {
		vi.mocked(getBearerToken).mockReturnValue(null);
		const controller = new AbortController();
		globalThis.fetch = makeFetchAndAbort(controller, { ok: true, body: null });
		const gen = streamRun(42, "run-uuid-1", -1, controller.signal);
		await gen.next();

		const headers = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
		expect(headers).not.toHaveProperty("Authorization");
	});
});

// ---------------------------------------------------------------------------
// cancelRun
// ---------------------------------------------------------------------------

describe("cancelRun", () => {
	it("sends POST to cancel endpoint and returns result", async () => {
		globalThis.fetch = mockFetch({ cancelled: true });
		const result = await cancelRun(42, "run-uuid-1");

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/v1/threads/42/runs/run-uuid-1/cancel"),
			expect.objectContaining({ method: "POST" })
		);
		expect(result).toEqual({ cancelled: true });
	});

	it("throws on non-ok response", async () => {
		globalThis.fetch = mockFetch(null, false, 404);
		await expect(cancelRun(42, "run-uuid-1")).rejects.toThrow("cancelRun failed: 404");
	});
});

// ---------------------------------------------------------------------------
// resumeRun
// ---------------------------------------------------------------------------

describe("resumeRun", () => {
	it("sends POST to resume endpoint and returns new run", async () => {
		const resumed = { ...MOCK_RUN, id: "run-uuid-2", status: "running" as const };
		globalThis.fetch = mockFetch(resumed);
		const result = await resumeRun(42, "run-uuid-1");

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/v1/threads/42/runs/run-uuid-1/resume"),
			expect.objectContaining({ method: "POST" })
		);
		expect(result).toEqual(resumed);
	});

	it("throws on non-ok response", async () => {
		globalThis.fetch = mockFetch(null, false, 409);
		await expect(resumeRun(42, "run-uuid-1")).rejects.toThrow("resumeRun failed: 409");
	});
});
