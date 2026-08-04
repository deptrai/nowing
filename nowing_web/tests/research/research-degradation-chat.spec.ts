import { expect } from "@playwright/test";
import { test } from "../fixtures";
import { type ChatThreadFixtures, chatThreadFixtures } from "../fixtures/chat-thread.fixture";
import { streamChatToCompletion } from "../helpers/api/chat";

const researchTest = test.extend<ChatThreadFixtures>(chatThreadFixtures);

researchTest.describe("Research degradation in chat — 9.1a", () => {
	researchTest(
		"should degrade chainlens research through the chat agent without crashing",
		async ({ request, apiToken, workspace, chatThread }) => {
			test.setTimeout(120_000);

			// The fake chat LLM routes research queries to the chainlens subagent,
			// which calls chainlens_research with the sentinel query and produces
			// an engine_unavailable result.
			const chat = await streamChatToCompletion(request, apiToken, {
				workspaceId: workspace.id,
				threadId: chatThread.id,
				query: "E2E deep research self-host no key",
			});

			const eventText = JSON.stringify(chat.events);
			expect(eventText).toContain("chainlens_research");
			expect(chat.assistantText).toContain("CHAINLENS_API_KEY");
			expect(
				chat.assistantText,
				`assistant should report engine unavailability; got: ${chat.assistantText.slice(0, 200)}`
			).toMatch(/unavailable|not configured|engine unavailable/i);
		}
	);
});
