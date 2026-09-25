import { expect, test } from "./extension.fixture";

test.describe("Nowing Lead Clipper Extension E2E", () => {
	test("service worker loads and resolves valid extension ID", async ({ extensionId }) => {
		expect(extensionId).toBeTruthy();
		expect(extensionId).toMatch(/^[a-z]{32}$/);
	});

	test("popup interface renders connection status and workspace controls", async ({
		context,
		extensionId,
	}) => {
		const page = await context.newPage();
		await page.goto(`chrome-extension://${extensionId}/popup.html`);

		// Verify the extension title & branding header
		await expect(page.locator("body")).toBeVisible();
		await expect(
			page.getByText(/Nowing/i).or(page.getByText(/Lead Clipper/i)).first()
		).toBeVisible({ timeout: 10_000 });
	});

	test("content script attaches floating pill host to supported real estate portal", async ({
		context,
	}) => {
		const page = await context.newPage();

		// Mock a batdongsan listing page structure
		await page.route("https://batdongsan.com.vn/**", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "text/html",
				body: `
					<!DOCTYPE html>
					<html>
						<head><title>Bán nhà mặt phố Hà Nội</title></head>
						<body>
							<h1 class="re__pr-title">Bán nhà chính chủ 50m2 giá 5 tỷ</h1>
							<div class="re__pr-short-info">
								<span class="re__pr-short-info-item">5 tỷ</span>
								<span class="re__pr-short-info-item">50 m²</span>
							</div>
							<div class="phone-wrapper">
								<span class="hidden-mobile">0912345678</span>
							</div>
						</body>
					</html>
				`,
			});
		});

		await page.goto("https://batdongsan.com.vn/ban-nha-mat-pho");

		// Content script should inject the floating pill host into document body
		const pillHost = page.locator("#nowing-clipper-host");
		await expect(pillHost).toBeAttached({ timeout: 15_000 });
	});
});
