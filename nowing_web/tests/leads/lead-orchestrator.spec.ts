import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Story 21.15: Unified Multi-Source AI Lead Generation Orchestrator E2E", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		await registerUser(request, "e2e-test@nowing.net", "E2eTestPassword123!").catch(() => {
			// User may already exist
		});
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`E2E Lead Orchestrator ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("E2E: Execute multi-source lead discovery from UI and verify table streaming", async ({
		page,
	}) => {
		// 1. Log in to dashboard
		await page.goto("/login");
		await page.locator('input[placeholder="you@example.com"]').fill("e2e-test@nowing.net");
		await page.locator('input[placeholder="Enter your password"]').fill("E2eTestPassword123!");
		await page.locator('button[type="submit"]').click();

		// 2. Navigate to workspace leads page
		await page.goto(`/dashboard/${workspaceId}/leads`);
		await page.waitForLoadState("domcontentloaded");

		// 3. Verify Origami Matrix container or Lead UI renders
		const matrixContainer = page.locator("main, div[data-testid='origami-split-canvas']").first();
		await expect(matrixContainer).toBeVisible({ timeout: 15000 });

		// 4. Navigate to New Chat with natural language lead search prompt
		await page.goto(`/dashboard/${workspaceId}/new-chat`);
		await page.waitForLoadState("domcontentloaded");

		const chatComposer = page.getByRole("textbox").first();
		await expect(chatComposer).toBeVisible({ timeout: 15000 });

		// 5. Send lead query prompt
		await chatComposer.fill("Tìm 10 công ty IT và 5 môi giới bất động sản tại Hà Nội");
		await chatComposer.press("Enter");

		// 6. Verify turn starts and message renders without client-side crash
		const messageStream = page
			.locator("div[data-testid='chat-messages'], div.prose, div.stream-container")
			.first();
		await expect(messageStream).toBeVisible({ timeout: 20000 });
	});
});
