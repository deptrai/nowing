import { test, expect } from "../support/merged-fixtures";

function buildSSEStream(events: Array<{ type: string; data: object }>): string {
  return events.map((e) => `data: ${JSON.stringify({ type: e.type, data: e.data })}\n`).join("\n") + "\n";
}

test.describe("Chat Journey (SSE)", () => {
  test("should send a message and verify streamed response", async ({ page, log }) => {
    const THREAD_ID = 999;
    const SESSION_ID = "chat-e2e-session";
    
    // Mock SSE Response
    await page.route(/\//, async (route) => {
       if (route.request().url().includes('chat')) {
          const events = [
            { type: "text-delta", data: { delta: "Hello! " } },
            { type: "text-delta", data: { delta: "I am " } },
            { type: "text-delta", data: { delta: "your AI assistant." } },
            { type: "done", data: { thread_id: THREAD_ID } }
          ];
          
          await route.fulfill({
            status: 200,
            headers: {
              "Content-Type": "text/event-stream",
              "Cache-Control": "no-cache",
              "Connection": "keep-alive",
            },
            body: buildSSEStream(events),
          });
       } else {
         await route.continue();
       }
    });

    // Navigate to a new chat page
    await page.goto("/dashboard/default/new-chat");

    // Step 1: Send message
    await log({ level: "step", message: "Sending chat message" });
    const chatInput = page.getByTestId("chat-input").or(page.getByRole("textbox", { name: /message|ask/i }));
    await chatInput.fill("Who are you?");
    await page.keyboard.press("Enter");

    // Step 2: Verify streaming response
    await log({ level: "step", message: "Verifying AI response is streamed" });
    
    // Verify text appears incrementally (or final result)
    const responseContainer = page.locator('[data-slot="chat-message-ai"]').or(page.getByText(/Hello!/i));
    await expect(responseContainer).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("your AI assistant.")).toBeVisible({ timeout: 5000 });
  });
});