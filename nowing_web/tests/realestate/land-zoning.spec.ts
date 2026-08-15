import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * E2E gate for Story 10.8: Spatial Planning & Land Zoning GIS.
 *
 * Verifies the Land Zoning Modal on `/dashboard/{workspaceId}/realestate/land-zoning`
 * handles the new `realestate.zoning` API response shapes without crashing:
 * - successful `ZoningCheckResult` with zones and risk notes
 * - quota/credit exhausted (402)
 * - authentication expiry (401 -> /login redirect)
 *
 * Tests rely on the shared `chromium` storageState from `tests/auth.setup.ts`.
 */

test.describe("Land Zoning Modal", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Land Zoning ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("renders the modal and displays a successful zoning check", async ({ page }) => {
		const payload = {
			has_road_expansion_risk: true,
			latitude: 21.0285,
			longitude: 105.8542,
			query_latency_ms: 5.42,
			risk_notes: ["Thửa đất nằm trong chỉ giới mở rộng đường Dương Đình Nghệ"],
			summary: "CẢNH BÁO: Phát hiện rủi ro mở rộng đường giao thông.",
			zones: [
				{
					id: 1,
					district: "Cầu Giấy",
					polarity: "danger",
					polarity_color: "#ef4444",
					province: "Hà Nội",
					ward: "Yên Hòa",
					zone_code: "DGT",
					zone_name: "Đất giao thông",
				},
			],
		};

		await page.route(`**/api/v1/workspaces/${workspaceId}/scrapers/realestate/zoning`, (route) => {
			void route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(payload),
			});
		});

		await page.goto(`/dashboard/${workspaceId}/realestate/land-zoning`);

		// Modal should open automatically on page load
		const dialog = page.getByRole("dialog", { name: /thẩm định quy hoạch đất đai/i });
		await expect(dialog).toBeVisible();

		await page.getByRole("button", { name: /kiểm tra quy hoạch/i }).click();

		// Wait for the mocked result to render
		await expect(page.getByText(/cảnh báo.*rủi ro/i)).toBeVisible();
		await expect(page.getByText(/đất giao thông.*dgt/i)).toBeVisible();
		await expect(page.getByText(/mở rộng đường/i)).toBeVisible();

		// No Next.js crash overlay
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("shows an error toast when the workspace has no credits", async ({ page }) => {
		await page.route(`**/api/v1/workspaces/${workspaceId}/scrapers/realestate/zoning`, (route) => {
			void route.fulfill({
				status: 402,
				contentType: "application/json",
				body: JSON.stringify({
					error: {
						code: "insufficient_credits",
						message: "Không đủ credits để tra cứu quy hoạch.",
						request_id: "e2e-402",
						status: 402,
						timestamp: new Date().toISOString(),
					},
					detail: "Không đủ credits để tra cứu quy hoạch.",
				}),
			});
		});

		await page.goto(`/dashboard/${workspaceId}/realestate/land-zoning`);

		await page.getByRole("button", { name: /kiểm tra quy hoạch/i }).click();

		await expect(page.getByText(/không đủ credits/i)).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("redirects to /login when the session cookie is cleared", async ({ page, context }) => {
		await page.goto(`/dashboard/${workspaceId}/realestate/land-zoning`);

		await expect(page.getByRole("dialog", { name: /thẩm định quy hoạch đất đai/i })).toBeVisible();

		await context.clearCookies();
		await page.reload();

		await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
		await expect(page.getByRole("heading", { name: /log in|sign in|đăng nhập/i })).toBeVisible();
	});
});
