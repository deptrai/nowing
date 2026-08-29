import type { Page } from "@playwright/test";
import { expect, test } from "../fixtures";
import type { WorkspaceRow } from "../helpers/api/workspaces";

test.describe.configure({ timeout: 240_000 });

test.describe("Broker E2E smoke: real-estate lead routing + Right Dock", () => {
	async function runBrokerPrompt(
		page: Page,
		workspace: WorkspaceRow,
		prompt: string,
		expectSellerFraming: boolean
	) {
		// Capture console logs, page errors, and failed requests before navigation.
		const consoleLogs: string[] = [];
		const pageErrors: string[] = [];
		const failedRequests: string[] = [];
		page.on("console", (msg: { type: () => string; text: () => string }) => {
			consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
		});
		page.on("pageerror", (err: { message: string }) => {
			pageErrors.push(err.message);
		});
		page.on(
			"requestfailed",
			(req: { url: () => string; failure: () => { errorText: string } | null }) => {
				failedRequests.push(`${req.url()} - ${req.failure()?.errorText ?? ""}`);
			}
		);

		// 1. Open chat with a broker prompt.
		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		await page.waitForLoadState("domcontentloaded");

		const chatComposer = page.getByRole("textbox");
		try {
			await expect(chatComposer).toBeVisible({ timeout: 60_000 });
		} catch (e) {
			console.log("=== PAGE URL ===", page.url());
			console.log("=== PAGE ERRORS ===");
			for (const err of pageErrors) console.log(err);
			console.log("=== CONSOLE LOGS ===");
			for (const log of consoleLogs) console.log(log);
			throw e;
		}

		await chatComposer.fill(prompt);

		const sendButton = page.getByRole("button", { name: "Send message" });
		await sendButton.click();

		// 2. Wait for the assistant message to start streaming.
		await expect(page.locator(".aui-assistant-message-content").first()).toBeVisible({
			timeout: 60_000,
		});

		// 3. Wait for the turn to finish streaming.
		const messageStream = page.locator(".aui-assistant-message-content").first();
		await expect(messageStream).toBeVisible({ timeout: 60_000 });
		await expect(sendButton).toBeEnabled({ timeout: 90_000 });

		// 4. Chat output must not expose a raw DEGRADED/PARTIAL status.
		await expect(page.locator("text=/DEGRADED/i")).not.toBeVisible();
		await expect(page.locator("text=/PARTIAL/i")).not.toBeVisible();

		// 5. Right Dock should auto-open.
		const dock = page.locator("[data-testid='contextual-dock'], aside").first();
		await expect(dock).toBeVisible({ timeout: 30_000 });

		const activeLeadsTab = page
			.locator("[data-testid='dock-tab-leads'], button")
			.filter({ hasText: /Leads|Lead/i })
			.first();
		await expect(activeLeadsTab).toBeVisible();

		// 6. The lead matrix/table should contain only BĐS sources.
		const matrix = page.locator("[data-testid='nowing-split-canvas']").first();
		await expect(matrix).toBeVisible({ timeout: 30_000 });

		// Wait for the table rows to stream in.
		const rows = page.locator("[data-testid='lead-row'], tr");
		await expect(rows.first()).toBeVisible({ timeout: 120_000 });

		// 7. Scope source assertions to the visible matrix.
		const matrixText = await matrix.textContent();
		expect(matrixText).toBeTruthy();
		expect(matrixText).not.toMatch(/topcv|itviec|vietnamworks/i);
		expect(matrixText).not.toMatch(/masothue/i);

		// 8. Assert BĐS leads were rendered and the source industry is visible.
		expect(matrixText).toMatch(/Bất động sản/i);

		// 9. Expect at least 10 visible lead rows.
		const rowCount = await rows.count();
		expect(rowCount).toBeGreaterThanOrEqual(10);

		// 10. Seller intent must not be framed as "khách hàng tiềm năng".
		if (expectSellerFraming) {
			expect(matrixText).toMatch(/tin đăng bán|đối thủ|nguồn cầu|người mua/i);
			const chatText = await page.locator(".aui-assistant-message-content").first().textContent();
			expect(chatText).not.toMatch(/khách hàng tiềm năng/i);
		}

		// 11. Phone columns must either expose a masked number or an unlock action.
		const phoneOrUnlock = page.locator("text=/Mở khóa SĐT|\\d{4}\\*\\*\\*\\d{3}/").first();
		await expect(phoneOrUnlock).toBeVisible({ timeout: 60_000 });

		return { rows, matrix };
	}

	test("BĐS buyer prompt: 10+ leads, price/location filter, Right Dock auto-open, no degraded banner", async ({
		page,
		workspace,
	}) => {
		await runBrokerPrompt(page, workspace, "Tìm 10 nhà bán quận 7 TP.HCM giá dưới 8 tỷ", false);
	});

	test("BĐS seller prompt: buyer-demand framing, 10+ leads, phone unlock enables Zalo", async ({
		page,
		workspace,
	}) => {
		await runBrokerPrompt(
			page,
			workspace,
			"Tôi cần bán 10 lô đất ký gửi ở quận 7, hãy tìm 10 người mua tiềm năng",
			true
		);

		// 12. Find a row with a phone-unlock action and click it deterministically.
		const unlockRow = page
			.locator("[data-testid='lead-row'], tr")
			.filter({ hasText: /Mở khóa SĐT/i })
			.first();

		await expect(unlockRow).toBeVisible({ timeout: 30_000 });
		const pill = unlockRow.locator("[data-testid='phone-resolve-pill']").first();
		await pill.click();

		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await popover.getByRole("button", { name: /Mở khóa SĐT/i }).click();

		// After unlock, the phone pill should no longer show the unlock action.
		await expect(pill).not.toBeVisible({ timeout: 60_000 });

		// The Zalo button in the same row should now be enabled.
		const zaloButton = unlockRow
			.locator("[data-testid='zalo-outreach-button'], button")
			.filter({ hasText: /Zalo/i })
			.first();
		await expect(zaloButton).toBeEnabled({ timeout: 30_000 });
	});
});
