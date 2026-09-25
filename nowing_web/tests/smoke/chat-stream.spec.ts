import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL, isE2eBackend } from "../helpers/api/auth";
import { streamChatToCompletion } from "../helpers/api/chat";

test.describe("Smoke", () => {
	// This spec asserts on the deterministic fake-LLM stream ("No relevant
	// indexed content found.") emitted only by tests/e2e/run_backend.py. On a
	// plain `main.py` or production backend the real LLM answers differently,
	// so skip instead of timing out.
	test.beforeEach(async ({ request }) => {
		test.skip(
			!(await isE2eBackend(request)),
			"requires the e2e backend (tests/e2e/run_backend.py) with fake LLM stream"
		);
	});

	test("chat stream completes for an unrelated query", async ({ request, apiToken, workspace }) => {
		const threadResponse = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-chat-stream-smoke",
				workspace_id: workspace.id,
				visibility: "PRIVATE",
			},
		});
		expect(threadResponse.ok()).toBeTruthy();

		const thread = (await threadResponse.json()) as { id: number };
		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: thread.id,
			query: "E2E_NO_RELEVANT_CONTENT_SMOKE",
		});

		expect(chat.events.some((event) => event.type === "done")).toBeTruthy();
		expect(chat.events.some((event) => event.type === "text-delta")).toBeTruthy();
		expect(chat.assistantText).toContain("No relevant indexed content found.");
	});
});
