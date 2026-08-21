import type { Page, Request, Route } from "@playwright/test";
import { expect, test } from "../fixtures";

/**
 * Story 25.3: Affiliate Partner Payout Desk & Anti-Fraud Engine — E2E scaffold.
 *
 * These specs validate the admin payout desk UI without requiring a pre-seeded
 * superuser. They intercept the backend API and mock responses so the frontend
 * rendering and interaction logic can be tested in isolation.
 *
 * TODO: Replace mocked routes with real admin auth + seeded data once a
 * Playwright admin storage fixture or /__e2e__/seed endpoint is available.
 */

const MOCK_PAYOUT_ID = "payout-11111111-1111-1111-1111-111111111111";
const MOCK_PARTNER_ID = "partner-11111111-1111-1111-1111-111111111111";

const lowRiskPayout = {
	id: MOCK_PAYOUT_ID,
	partner_id: MOCK_PARTNER_ID,
	partner_name: "Nguyễn Văn Minh",
	partner_email: "minh@nowing.test",
	partner_code: "MINH-001",
	partner_tier: "standard",
	gross_amount_vnd: 2_000_000,
	pit_tax_deduction_vnd: 200_000,
	net_payout_amount_vnd: 1_800_000,
	bank_bin: "970422",
	bank_short_name: "MBBank",
	account_number: "123456789",
	account_holder: "NGUYEN VAN MINH",
	name_match_status: "100% Match",
	risk_score: 15,
	risk_level: "low",
	risk_reasons: [],
	status: "pending",
	tx_reference: null,
	created_at: new Date().toISOString(),
	processed_at: null,
};

const highRiskPayout = {
	...lowRiskPayout,
	id: "payout-22222222-2222-2222-2222-222222222222",
	partner_name: "Fraudster Ring",
	partner_email: "fraud@nowing.test",
	account_holder: "FRAUDSTER RING",
	name_match_status: "Name Mismatch",
	risk_score: 85,
	risk_level: "high",
	risk_reasons: ["Self-referral ring detected within 1 hour"],
	status: "pending",
};

async function setupPayoutMocks(page: Page) {
	// Pretend the non-admin test user is a superuser so the admin shell renders.
	await page.route(/.*\/auth\/session(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				authenticated: true,
				access_expires_at: Date.now() / 1000 + 3_600,
				is_impersonation: false,
				impersonated_by: null,
				target_user: null,
			}),
		});
	});

	await page.route(/.*\/users\/me(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				id: "admin-test-user-0000-0000-0000-000000000001",
				email: "admin-test@nowing.net",
				is_active: true,
				is_superuser: true,
				is_verified: true,
				credit_micros_balance: 0,
				display_name: "Admin Test",
				avatar_url: null,
				notification_preferences: null,
			}),
		});
	});

	await page.route(
		/\/api\/v1\/admin\/affiliates\/payouts/,
		async (route: Route, request: Request) => {
			const url = request.url();
			const method = request.method();

			if (url.includes("/evaluate")) {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						payout_id: MOCK_PAYOUT_ID,
						risk_score: lowRiskPayout.risk_score,
						risk_level: lowRiskPayout.risk_level,
						reasons: lowRiskPayout.risk_reasons,
						evaluated_at: new Date().toISOString(),
					}),
				});
				return;
			}

			if (url.includes("/approve")) {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						status: "processing",
						payout_id: MOCK_PAYOUT_ID,
						tx_reference: "NOWING-PAY-MOCK-123",
						amount_micros: 78_740_157,
						net_amount_micros: 70_866_141,
					}),
				});
				return;
			}

			if (url.includes("/reject")) {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						status: "rejected",
						payout_id: MOCK_PAYOUT_ID,
						rejection_reason: "SUSPECTED_FRAUD_RING",
						rolled_back_balance_micros: 78_740_157,
					}),
				});
				return;
			}

			if (method === "GET" && url.includes("/admin/affiliates/payouts")) {
				const total = 2;
				const offsetMatch = url.match(/offset=(\d+)/);
				const offset = offsetMatch ? Number.parseInt(offsetMatch[1], 10) : 0;
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						items: offset === 0 ? [lowRiskPayout, highRiskPayout] : [],
						total,
						limit: 100,
						offset,
					}),
				});
				return;
			}

			await route.continue();
		}
	);
}

test.describe("Admin Affiliate Payout Desk", () => {
	test.beforeEach(async ({ page }) => {
		await setupPayoutMocks(page);
		await page.goto("/admin/affiliates/payouts");
	});

	test("[P0] should render the payout list with tax and risk columns", async ({ page }) => {
		await expect(page.getByRole("heading", { name: /Bàn Phê Duyệt Payout/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /Tổng Tiền \(Gross\)/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /Thực Nhận \(Net\)/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /Rủi Ro \(Anti-Fraud\)/i })).toBeVisible();

		await expect(page.getByText("NGUYEN VAN MINH")).toBeVisible();
		await expect(page.getByText("2.000.000 đ").first()).toBeVisible();
		await expect(page.getByText("1.800.000 đ").first()).toBeVisible();
	});

	test("[P0] should open detail modal and enable Approve for low-risk / name-match payout", async ({
		page,
	}) => {
		const row = page.getByRole("row").filter({ hasText: /NGUYEN VAN MINH/ });
		await row.getByRole("button", { name: /Xử Lý/i }).click();

		const modal = page.getByRole("dialog");
		await expect(modal).toBeVisible();
		await expect(modal.getByText(/Rủi Ro Thấp|LOW/i)).toBeVisible();
		await expect(modal.getByText("100% Match")).toBeVisible();

		const approveBtn = modal.getByRole("button", { name: /Phê Duyệt & Chuyển Tiền VietQR/i });
		await expect(approveBtn).toBeEnabled();
	});

	test("[P0] should disable Approve for high-risk / name-mismatch payout", async ({ page }) => {
		const row = page.getByRole("row").filter({ hasText: /Fraudster Ring/ });
		await row.getByRole("button", { name: /Xử Lý/i }).click();

		const modal = page.getByRole("dialog");
		await expect(modal).toBeVisible();
		await expect(modal.getByText(/Cảnh Báo: Rủi Ro Gian Lận Mức Độ Cao/i)).toBeVisible();
		await expect(modal.getByText("Name Mismatch")).toBeVisible();

		const approveBtn = modal.getByRole("button", { name: /Phê Duyệt & Chuyển Tiền VietQR/i });
		await expect(approveBtn).toBeDisabled();
	});

	test("[P1] should reject payout with a reason and close modal", async ({ page }) => {
		const row = page.getByRole("row").filter({ hasText: /Fraudster Ring/ });
		await row.getByRole("button", { name: /Xử Lý/i }).click();

		const modal = page.getByRole("dialog");
		await modal.getByRole("button", { name: /Từ Chối Payout/i }).click();

		// Select a rejection reason
		await modal.getByRole("combobox").click();
		await page.getByRole("option", { name: /Nghi Vấn Gian Lận/i }).click();

		await modal.getByRole("button", { name: /Xác Nhận Từ Chối/i }).click();

		await expect(modal).not.toBeVisible();
	});

	test("[P1] should paginate the payout list", async ({ page }) => {
		await expect(page.getByText("Hiển thị 2 / 2 bản ghi")).toBeVisible();

		const loadMore = page.getByRole("button", { name: /tải thêm/i });
		await expect(loadMore).toBeDisabled();
	});
});
