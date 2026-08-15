import { expect, test } from "@playwright/test";

test.describe("Story 21.12: Viral Social Co-pilot (Content Mode)", () => {
	test.skip(true, "ATDD Red Phase: Content Mode UI implementation pending");

	test("AC 1 & 6: should learn voice profile from sample text and display persona badge", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/content/social-copilot");

		// Open Voice Profile tab
		await page.getByRole("tab", { name: /hồ sơ giọng văn|voice profile/i }).click();

		// Fill sample text >= 100 words
		const sample =
			"Hầu hết các môi giới BĐS đang đốt tiền vô ích vào Facebook Ads. " +
			"Thực tế 90% giao dịch phân khúc cao cấp năm nay đến từ mạng lưới quan hệ ngầm " +
			"và định vị cá nhân qua nội dung chuyên sâu. " +
			"Dưới đây là quy trình 3 bước tôi dùng để chốt 4 căn biệt thự mà không tốn 1 đồng quảng cáo: " +
			"1. Xác định tệp khách hàng mua kín qua dữ liệu đăng ký doanh nghiệp. " +
			"2. Viết bài phân tích dòng tiền chuyên sâu thay vì đăng tin bán nhà rác. " +
			"3. Tiếp cận riêng tư qua tin nhắn trực tiếp kèm báo cáo định giá độc quyền. " +
			"Comment 'BÁO CÁO' để nhận file phân tích dòng tiền mẫu chi tiết nhất hôm nay. " +
			"Hãy nhớ rằng uy tín cá nhân là đòn bẩy mạnh nhất trong chu kỳ thị trường hiện tại. " +
			"Đừng chạy theo đám đông nếu bạn muốn dẫn đầu phân khúc triệu đô.";

		await page.getByLabel(/tên hồ sơ|profile name/i).fill("BĐS Chuyên Gia");
		await page.getByLabel(/mẫu bài viết|sample text/i).fill(sample);
		await page.getByRole("button", { name: /phân tích giọng văn|learn voice/i }).click();

		// Check persona card appears
		await expect(page.getByText("BĐS Chuyên Gia")).toBeVisible();
		await expect(page.getByText(/authoritative|tranh biện|chuyên sâu/i)).toBeVisible();
	});

	test("AC 2 & 3: should display outlier viral posts with engagement multiplier badge and taxonomy", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/content/social-copilot");

		// Outlier Feed
		await page.getByRole("tab", { name: /bài viết viral|outlier feed/i }).click();

		// Check multiplier badge >= 3x is visible
		const multiplierBadge = page.locator("[data-testid='outlier-multiplier']").first();
		await expect(multiplierBadge).toBeVisible();
		await expect(multiplierBadge).toContainText(/x/);

		// Check hook taxonomy badge
		const taxonomyBadge = page.locator("[data-testid='hook-taxonomy-badge']").first();
		await expect(taxonomyBadge).toBeVisible();
	});

	test("AC 4, 5: should generate 3 variations and copy to clipboard on 1-click", async ({
		page,
		context,
	}) => {
		// Grant clipboard permissions
		await context.grantPermissions(["clipboard-read", "clipboard-write"]);

		await page.goto("/dashboard/1/content/social-copilot");

		// Select a viral post card
		await page.locator("[data-testid='outlier-card']").first().click();

		// Click generate draft
		await page.getByRole("button", { name: /tạo bản thảo|generate draft/i }).click();

		// Verify 3 variations (A, B, C) tabs exist
		await expect(page.getByRole("tab", { name: /bản thảo a|variation a/i })).toBeVisible();
		await expect(page.getByRole("tab", { name: /bản thảo b|variation b/i })).toBeVisible();
		await expect(page.getByRole("tab", { name: /bản thảo c|variation c/i })).toBeVisible();

		// Click 1-click copy button
		await page.getByRole("button", { name: /sao chép|copy/i }).click();

		// Verify toast notification appears
		await expect(page.getByText(/đã sao chép vào clipboard|copied to clipboard/i)).toBeVisible();
	});
});
