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

		await expect(
			page.getByText("E2E fake assistant received:"),
			"assistant should respond with the E2E fake message"
		).toBeVisible({ timeout: 60_000 });
	});
});
