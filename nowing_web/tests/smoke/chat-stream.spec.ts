import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL, isE2eBackend } from "../helpers/api/auth";
import { streamChatToCompletion } from "../helpers/api/chat";

test.describe("Chat Stream E2E Smoke", () => {
	let e2eBackend: boolean;

	test.beforeEach(async ({ request }) => {
		// Evaluate backend type once per test to gate deterministic assertions
		e2eBackend = await isE2eBackend(request);
	});

	test("chat stream completes successfully regardless of backend mode", async ({
		request,
		apiToken,
		workspace,
	}) => {
		const threadResponse = await request.post(`${BACKEND_URL}/api/v1/threads`, {
			headers: authHeaders(apiToken),
			data: {
				title: "e2e-chat-stream-dual-mode",
				workspace_id: workspace.id,
				visibility: "PRIVATE",
			},
		});
		expect(threadResponse.ok()).toBeTruthy();

		const thread = (await threadResponse.json()) as { id: number };

		// Send a benign query that works on both mock and real backends
		const query = e2eBackend ? "E2E_NO_RELEVANT_CONTENT_SMOKE" : "Hello";

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: thread.id,
			query,
		});

		// Universal stream verification
		expect(chat.events.some((event) => event.type === "done")).toBeTruthy();
		expect(chat.events.some((event) => event.type === "text-delta")).toBeTruthy();
		expect(chat.assistantText).toBeTruthy();

		// Deterministic assertion strictly for the fake e2e backend
		if (e2eBackend) {
			expect(chat.assistantText).toContain("No relevant indexed content found.");
		} else {
			// On real backend, ensure we get a sensible non-empty response instead of crashing
			expect(chat.assistantText.length).toBeGreaterThan(5);
		}
	});
});
