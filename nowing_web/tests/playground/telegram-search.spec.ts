import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end red-phase acceptance scaffold for the Telegram search capability
 * in the API Playground (Story 22.1 / AC-6).
 *
 * Skipped until the backend persistence and playground wiring are activated.
 */

test.describe("Playground Telegram search", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Telegram ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/telegram\/search(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				if (req.method() === "POST") {
					await route.fulfill({
						status: 200,
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							channel_info: {
								username: "batdongsanhanoi",
								title: "Bất Động Sản Hà Nội 2026",
								description: "Kênh BĐS chính chủ",
								subscribers_count: 25400,
							},
							messages: [
								{
									message_id: 1001,
									channel_username: "batdongsanhanoi",
									text: "Bán gấp nhà mặt phố Cầu Giấy 50m2 x 5 tầng. LH: 0988123456",
									published_at: "2026-08-15T08:30:00Z",
									views: 1500,
									has_media: true,
									author_name: "Admin BĐS",
									intent_tag: "sell",
									entities: {
										phone_numbers: ["0988123456"],
										emails: [],
										prices: ["12.5 tỷ"],
										hashtags: ["#bds"],
										intent_tag: "sell",
										raw_entities: [{ type: "phone", value: "0988123456" }],
									},
								},
							],
							total_found: 1,
							billable_units: 1,
						}),
					});
					return;
				}

				await route.continue();
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test.skip("[P0] should render Telegram search in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /telegram/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("telegram.search");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/telegram/search`);
	});

	test.skip("[P0] should run Telegram search and show billable output", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/telegram/search`);

		const channelInput = page.locator("#field-channel_username");
		await expect(channelInput).toBeVisible();
		await channelInput.fill("batdongsanhanoi");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/Bất Động Sản Hà Nội/i).first()).toBeVisible({
			timeout: 30_000,
		});
		await expect(page.getByText(/0988123456/).first()).toBeVisible({ timeout: 30_000 });
		await expect(page.getByText(/"billable_units":\s*1/).first()).toBeVisible({
			timeout: 30_000,
		});
	});
});
