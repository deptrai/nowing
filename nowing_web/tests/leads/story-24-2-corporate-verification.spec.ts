import { expect, test } from "@playwright/test";
import { acquireTestToken, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Story 24.2 — Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine
 *
 * These E2E journeys verify the `NowingLeadMatrix` surface does not crash when the
 * backend returns the new 24.2 corporate/Zalo fields and that auth expiry is handled
 * correctly.
 *
 * NOTE: as of the current `develop` branch, `LeadRead` and `leads_routes.py` do NOT
 * yet serialize `tax_id`, `legal_representative`, etc. (see review finding
 * `LeadRead API schema and mapper do not expose the new corporate/Zalo fields`).
 * The badge rendering test therefore augments the real lead-list response via
 * `page.route()` so we can still exercise the UI path. Once the backend mapper is
 * fixed, the route override can be removed and the test will naturally run against
 * real data.
 */

async function createLeadViaClip(
	request: import("@playwright/test").APIRequestContext,
	token: string,
	workspaceId: number,
	body: Record<string, unknown>
): Promise<{ lead_id: string }> {
	const response = await request.post(
		`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/clip`,
		{
			headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
			data: body,
		}
	);
	expect([200, 201], `Expected lead clip to succeed, got ${response.status()}`).toContain(
		response.status()
	);
	return (await response.json()) as { lead_id: string };
}

test.describe("Story 24.2: Waterfall Phone & MST Corporate Verification Engine", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E 24.2 MST ${Date.now()}`);
		workspaceId = workspace.id;

		await createLeadViaClip(request, ownerToken, workspaceId, {
			source_canonical_url: `https://e2e-24-2.test/listing-${Date.now()}`,
			source_platform: "batdongsan",
			company_name: "Công ty Thăng Long E2E",
			contact_name: "Nguyễn Văn A",
			phone: "0908123456",
			location: "Cầu Giấy, Hà Nội",
			post_content: "Bán nhà mặt phố Cầu Giấy",
		});
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("lead matrix renders MST and Zalo badges without crashing", async ({ page }) => {
		// Intercept the list call whether it goes directly to the backend or through
		// the Next.js proxy (`/api/v1/[...path]`).
		const listUrlRegex = new RegExp(
			`^https?://[^/]+/api/v1/workspaces/${workspaceId}/leads(\\?.*)?$`
		);

		await page.route(listUrlRegex, async (route) => {
			const response = await route.fetch();
			const body = (await response.json()) as { items: Record<string, unknown>[] };

			const lead = body.items?.[0] ?? {
				id: "00000000-0000-0000-0000-000000000001",
				workspace_id: workspaceId,
				source: "batdongsan",
				company_name: "Công ty Thăng Long E2E",
				domain: "thanglong-e2e.vn",
				industry: "Bất động sản",
				fit_score: 92,
				status: "new",
				phone: "0908123456",
				enriched: true,
				created_at: new Date().toISOString(),
				updated_at: new Date().toISOString(),
			};

			lead.tax_id = "0123456789";
			lead.legal_representative = "Nguyễn Văn A";
			lead.charter_capital_vnd = 50_000_000_000;
			lead.company_status = "Đang hoạt động";
			lead.is_zalo_active = true;

			body.items = [lead];

			await route.fulfill({
				status: response.status(),
				headers: { "content-type": "application/json" },
				body: JSON.stringify(body),
			});
		});

		await page.goto(`/dashboard/${workspaceId}/leads`);

		// Matrix should load the lead
		await expect(page.getByText("Công ty Thăng Long E2E")).toBeVisible();

		// New 24.2 badges should render
		await expect(page.getByText("MST Verified")).toBeVisible();
		await expect(page.getByText("Zalo Active")).toBeVisible();

		// Hover MST badge and verify tooltip content
		const mstBadge = page.getByText("MST Verified").first();
		await mstBadge.hover();
		await expect(page.getByText("MST: 0123456789").last()).toBeVisible();
		await expect(page.getByText("Đại diện: Nguyễn Văn A").last()).toBeVisible();
		await expect(page.getByText(/Vốn điều lệ: 50 tỷ VNĐ/).last()).toBeVisible();

		// No runtime crash/NaN rendering
		await expect(page.getByText("NaN")).toHaveCount(0);
		await expect(page.getByText(/Application error/i)).toHaveCount(0);

		await page.unroute(listUrlRegex);
	});

	test("session expiry redirects to login without an infinite loop", async ({ page, context }) => {
		await page.goto(`/dashboard/${workspaceId}/leads`);
		await context.clearCookies();
		await page.reload();
		await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
		await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
	});
});
