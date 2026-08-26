import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";

/**
 * Story 25.6: Security Audit Trail Logs & In-App Broadcast Announcements.
 *
 * Red-phase E2E scaffolds for `/admin/audit-logs`. Tests are skipped until
 * frontend and backend are implemented.
 */

const mockAuditLogs = {
	items: [
		{
			id: "a1111111-1111-4111-8111-111111111111",
			action: "user.impersonate_start",
			actor_id: "11111111-1111-4111-8111-111111111111",
			actor_email: "superadmin@nowing.net",
			subject_id: "22222222-2222-4222-8222-222222222222",
			subject_email: "client@example.com",
			ip_address: "192.168.1.100",
			user_agent: "Mozilla/5.0 Chrome/120.0",
			ticket_ref: "SUPPORT-4040",
			diff_payload: {
				reason: "Investigating data export error",
				endpoint: "/api/v1/admin/users/impersonate",
			},
			created_at: "2026-08-26T14:30:00Z",
		},
		{
			id: "b2222222-2222-4222-8222-222222222222",
			action: "global_dnc.add",
			actor_id: "11111111-1111-4111-8111-111111111111",
			actor_email: "superadmin@nowing.net",
			subject_id: null,
			subject_email: null,
			ip_address: "192.168.1.100",
			user_agent: "Mozilla/5.0 Chrome/120.0",
			ticket_ref: null,
			diff_payload: {
				record_type: "phone",
				masked_value: "0908 *** 456",
				value_hmac: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
				reason: "Decree 13 opt-out request",
				endpoint: "/api/v1/admin/dnc/global",
			},
			created_at: "2026-08-26T12:00:00Z",
		},
	],
	total: 2,
	limit: 50,
	offset: 0,
};

const CORS_HEADERS = {
	"Access-Control-Allow-Origin": "http://localhost:3000",
	"Access-Control-Allow-Credentials": "true",
	"Access-Control-Allow-Headers":
		"Content-Type, Authorization, X-Requested-With, X-E2E-Mint-Secret, x-playwright-test",
	"Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
};

async function fulfillJson(route: Route, status: number, body: unknown) {
	if (route.request().method() === "OPTIONS") {
		await route.fulfill({ status: 204, headers: CORS_HEADERS });
		return;
	}
	await route.fulfill({
		status,
		contentType: "application/json",
		headers: CORS_HEADERS,
		body: JSON.stringify(body),
	});
}

test.describe("Admin Audit Logs Timeline (Story 25.6 ATDD)", () => {
	test.beforeEach(async ({ page }: { page: Page }) => {
		await page.route("**/auth/session*", async (route: Route) => {
			await fulfillJson(route, 200, {
				authenticated: true,
				access_expires_at: Date.now() / 1000 + 3_600,
				is_impersonation: false,
				impersonated_by: null,
				target_user: null,
			});
		});

		await page.route("**/zero/context*", async (route: Route) => {
			await fulfillJson(route, 200, {
				user_id: "11111111-1111-4111-8111-111111111111",
				workspace_id: 1,
				is_superuser: true,
			});
		});

		await page.route("**/users/me*", async (route: Route) => {
			await fulfillJson(route, 200, {
				id: "11111111-1111-4111-8111-111111111111",
				email: "superadmin@nowing.net",
				is_active: true,
				is_superuser: true,
				is_verified: true,
			});
		});

		await page.route("**/api/v1/admin/audit-logs*", async (route: Route) => {
			await fulfillJson(route, 200, mockAuditLogs);
		});
	});

	test("[P0] should render audit log timeline table with actor and subject", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/audit-logs");
		await expect(page.getByText("Security Audit Trail Logs")).toBeVisible();
		await expect(page.getByRole("cell", { name: "user.impersonate_start" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "global_dnc.add" })).toBeVisible();
		await expect(page.getByText("superadmin@nowing.net").first()).toBeVisible();
		await expect(page.getByText("client@example.com")).toBeVisible();
	});

	test("[P1] should open details drawer showing formatted diff payload", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/audit-logs");
		const detailsBtn = page.getByRole("button", { name: /^view$/i }).first();
		await detailsBtn.click();
		await expect(page.getByText("Investigating data export error")).toBeVisible();
		await expect(page.getByText("/api/v1/admin/users/impersonate")).toBeVisible();
	});

	test("[P2] should export audit logs as CSV file", async ({ page }: { page: Page }) => {
		await page.goto("/admin/audit-logs");
		const exportBtn = page.getByRole("button", { name: /export csv/i });
		await expect(exportBtn).toBeVisible();
	});
});
