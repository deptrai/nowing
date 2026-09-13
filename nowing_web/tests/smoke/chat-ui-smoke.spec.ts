import { expect, test } from "../fixtures";

test.describe("Chat UI smoke", () => {
	test.setTimeout(120_000);

	test("seed account can send a message and receive an assistant response", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.getByRole("textbox");
		await expect(composer, "composer should be visible and ready").toBeVisible({ timeout: 30_000 });

		await composer.fill("E2E UI smoke test");

		const sendButton = page.getByRole("button", { name: "Send message" });
		await sendButton.click();

		// On the e2e backend (tests/e2e/run_backend.py) the assistant reply is the
		// deterministic "E2E fake assistant received: ..." string; on a plain
		// `main.py` backend the real LLM responds. Assert on the assistant message
		// container instead of the literal text so the test works in both modes.
		const assistantMessage = page.locator('[data-role="assistant"]').first();
		await expect(assistantMessage, "an assistant message should appear after sending").toBeVisible({
			timeout: 90_000,
		});
	});
});
