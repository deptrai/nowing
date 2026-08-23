import { expect, test } from "@playwright/test";

/**
 * Story 27.1: Full-Stack Web App Builder, Instant Hosting & Design View Mark Tool
 * E2E Acceptance Test Scaffolds (TDD RED PHASE).
 *
 * AC-1: Prompt input → Live Next.js Web Preview
 * AC-2: 1-Click Publish to *.apps.nowing.net
 * AC-3: Custom CNAME Connect
 * AC-4: Design View Mark Tool DOM-to-JSX Mutation
 */

test.describe("Story 27.1 — Web App Builder & Mark Tool", () => {
	test.beforeEach(async ({ page }) => {
		// Mock authenticated session or login state
		await page.goto("/dashboard/1/web-builder");
	});

	test.skip("AC-1: generates runnable Next.js preview from natural language prompt", async ({ page }) => {
		// 1. Enter prompt in builder input
		const promptInput = page.getByPlaceholder(/Mô tả ứng dụng web|Describe your web app/i);
		await expect(promptInput).toBeVisible();
		await promptInput.fill("Create a high-converting landing page for an AI accounting tool");

		// 2. Click Generate button
		const generateBtn = page.getByRole("button", { name: /Tạo ứng dụng|Generate App/i });
		await generateBtn.click();

		// 3. Verify loading state and preview iframe appearance
		await expect(page.getByText(/Đang khởi tạo Next.js|Building Next.js project/i)).toBeVisible();
		const previewIframe = page.frameLocator('iframe[title="Web App Preview"]');
		await expect(previewIframe.locator("h1")).toContainText(/Accounting/i, { timeout: 30_000 });
	});

	test.skip("AC-2: 1-Click publish deploys app to *.apps.nowing.net with HTTPS", async ({ page }) => {
		// 1. Click Publish button
		const publishBtn = page.getByRole("button", { name: /Publish|Xuất bản/i });
		await expect(publishBtn).toBeVisible();
		await publishBtn.click();

		// 2. Verify success modal and public live link
		const publicLink = page.getByRole("link", { name: /\.apps\.nowing\.net/i });
		await expect(publicLink).toBeVisible();
		await expect(publicLink).toHaveAttribute("href", /https:\/\/.*\.apps\.nowing\.net/);
	});

	test.skip("AC-4: Mark Tool activates bounding box and allows visual text/style edits", async ({ page }) => {
		// 1. Activate Mark Tool mode
		const markToolToggle = page.getByRole("button", { name: /Mark Tool|Chỉnh sửa trực quan/i });
		await markToolToggle.click();

		// 2. Click an element inside the preview iframe
		const previewIframe = page.frameLocator('iframe[title="Web App Preview"]');
		const targetHeading = previewIframe.locator("h1").first();
		await targetHeading.click();

		// 3. Expect inspector drawer to open with element properties
		const inspectorDrawer = page.getByTestId("mark-tool-inspector");
		await expect(inspectorDrawer).toBeVisible();

		// 4. Edit headline text
		const textInput = inspectorDrawer.getByLabel(/Nội dung văn bản|Text content/i);
		await textInput.fill("Supercharged AI Accounting");
		await page.getByRole("button", { name: /Áp dụng thay đổi|Apply Changes/i }).click();

		// 5. Verify iframe live reload reflects update
		await expect(targetHeading).toHaveText("Supercharged AI Accounting");
	});
});
