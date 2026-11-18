import { expect, test } from "@playwright/test";

import { acquireTestSession, authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace } from "../helpers/api/workspaces";

/**
 * Spec 45.4 — E2E browser flow for lead-gen campaigns (Epic 45).
 *
 * Covers the full demand lifecycle end-to-end in a real browser + real API:
 *   create via wizard → list row → detail (config card + tabs) → schedule
 *   dialog PATCH → pause → resume → archive → read-only.
 * Plus the supply direction flow:
 *   create "Tìm nhà cung cấp" → list direction badge → detail renders
 *   supply_criteria (not icp_config).
 *
 * No real scraping: only "Lưu bản nháp" (draft) is exercised — the Launch
 * button and /execute path are intentionally untouched (covered by backend
 * integration tests in Epic 44).
 */

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test.describe.configure({ mode: "serial" });

let workspaceId: number;
let token: string;

test.beforeAll(async ({ request }) => {
	const session = await acquireTestSession(request);
	token = session.access_token;
	const ws = await createWorkspace(request, token, `Campaigns E2E ${Date.now()}`);
	workspaceId = ws.id;
});

async function findCampaign(
	request: Parameters<Parameters<typeof test>[0]>[0]["request"],
	name: string
) {
	const res = await request.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/campaigns`, {
		headers: authHeaders(token),
	});
	expect(res.ok()).toBeTruthy();
	const body = (await res.json()) as {
		items: Array<Record<string, unknown> & { id: string; name: string }>;
	};
	return body.items.find((c) => c.name === name);
}

/** Wizard: fill name on step 3 and hit "Lưu bản nháp" (Save Draft). */
async function saveDraftFromWizard(page: Parameters<Parameters<typeof test>[0]>[0]["page"], name: string) {
	await page.getByRole("button", { name: /Tiếp tục: Nguồn & Ngân sách/ }).click();
	await page.getByRole("button", { name: /Tiếp tục: Launch & Kích hoạt/ }).click();
	await page.getByPlaceholder(/SDR Outbound Q3/).fill(name);
	await page.getByRole("button", { name: /Lưu bản nháp/ }).click();
	await expect(page.getByText(/dưới dạng bản nháp/)).toBeVisible({ timeout: 20_000 });
}

test("demand campaign lifecycle: create → schedule → pause → resume → archive → read-only", async ({
	page,
	request,
}) => {
	const name = `E2E Demand ${Date.now()}`;

	// ── Create a demand draft via the wizard ──────────────────────────
	await page.goto(`/dashboard/${workspaceId}/leads/campaigns/new`);
	await saveDraftFromWizard(page, name);

	// API truth: campaign persisted as draft.
	const created = await findCampaign(request, name);
	expect(created).toBeTruthy();
	expect(created?.status).toBe("draft");
	const campaignId = created!.id;

	// ── List page: row shows name + status + direction ────────────────
	await page.goto(`/dashboard/${workspaceId}/leads/campaigns`);
	const row = page.getByRole("row", { name: new RegExp(escapeRe(name)) });
	await expect(row).toBeVisible();
	await expect(row).toContainText("Draft");
	await expect(row).toContainText("Find customers");

	// ── Detail: header + config card + Runs/Leads tabs ────────────────
	await row.getByRole("link", { name }).click();
	await expect(page.getByRole("heading", { name })).toBeVisible();
	await expect(page.getByText("Configuration")).toBeVisible();
	await expect(page.getByRole("tab", { name: "Runs" })).toBeVisible();
	await expect(page.getByRole("tab", { name: "Leads" })).toBeVisible();

	// ── Schedule dialog: set Frequency = Daily → status 'scheduled' ───
	await page.getByRole("button", { name: "Schedule", exact: true }).click();
	const dialog = page.getByRole("dialog");
	await expect(dialog).toBeVisible();
	await expect(dialog).toContainText("Campaign schedule");
	await dialog.getByRole("combobox").click();
	await page.getByRole("option", { name: "Daily" }).click();
	await dialog.getByRole("button", { name: "Save", exact: true }).click();

	await expect(page.getByText("Scheduled", { exact: true }).first()).toBeVisible();
	await expect(page.getByText(/Next run:/)).toBeVisible();

	// API truth: status scheduled + next_run_at populated (G-1 closure).
	const scheduledRes = await request.get(
		`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/campaigns/${campaignId}`,
		{ headers: authHeaders(token) }
	);
	const scheduled = (await scheduledRes.json()) as { status: string; next_run_at: string | null };
	expect(scheduled.status).toBe("scheduled");
	expect(scheduled.next_run_at).toBeTruthy();

	// ── Pause (scheduled → paused, no confirm needed) ─────────────────
	await page.getByRole("button", { name: "Pause", exact: true }).click();
	await expect(page.getByText("Paused", { exact: true }).first()).toBeVisible();

	// ── Resume (paused → scheduled via PATCH) ─────────────────────────
	await page.getByRole("button", { name: "Resume", exact: true }).click();
	await expect(page.getByText("Scheduled", { exact: true }).first()).toBeVisible();

	// ── Archive (confirm dialog) ──────────────────────────────────────
	await page.getByRole("button", { name: "Archive", exact: true }).click();
	await expect(page.getByText(/Archive this campaign\?/)).toBeVisible();
	await page.getByRole("button", { name: "Confirm", exact: true }).click();
	await expect(page.getByText("Archived", { exact: true }).first()).toBeVisible();

	// ── Read-only: no lifecycle buttons left on the detail page ───────
	await expect(page.getByRole("button", { name: "Run now" })).toHaveCount(0);
	await expect(page.getByRole("button", { name: "Pause" })).toHaveCount(0);
	await expect(page.getByRole("button", { name: "Resume" })).toHaveCount(0);
	await expect(page.getByRole("button", { name: "Schedule" })).toHaveCount(0);
	await expect(page.getByRole("button", { name: "Edit schedule" })).toHaveCount(0);
	await expect(page.getByRole("button", { name: "Archive", exact: true })).toHaveCount(0);

	// Backend agrees: any status PATCH on an archived campaign → 422.
	const patchRes = await request.patch(
		`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/campaigns/${campaignId}`,
		{ headers: authHeaders(token), data: { status: "scheduled" } }
	);
	expect(patchRes.status()).toBe(422);
});

test("supply campaign: direction badge + supply_criteria in detail", async ({ page, request }) => {
	const name = `E2E Supply ${Date.now()}`;

	await page.goto(`/dashboard/${workspaceId}/leads/campaigns/new`);
	await page.getByRole("button", { name: /Find suppliers \(Supply\)/ }).click();

	// Supply criteria (Epic 43.5): ≥1 category + ≥1 location required.
	const categoryInput = page.getByPlaceholder(/Enter a category/);
	await categoryInput.fill("fabric");
	await categoryInput.press("Enter");
	const locationInput = page.getByPlaceholder(/Enter a province/);
	await locationInput.fill("Khanh Hoa");
	await locationInput.press("Enter");

	await saveDraftFromWizard(page, name);

	// API truth: direction + criteria persisted on the campaign row.
	const created = await findCampaign(request, name);
	expect(created).toBeTruthy();
	expect(created?.direction).toBe("supply");
	const criteria = created?.supply_criteria as { categories: string[]; locations: string[] };
	expect(criteria.categories).toContain("fabric");
	expect(criteria.locations).toContain("Khanh Hoa");

	// List: direction badge reads "Find suppliers".
	await page.goto(`/dashboard/${workspaceId}/leads/campaigns`);
	const row = page.getByRole("row", { name: new RegExp(escapeRe(name)) });
	await expect(row).toBeVisible();
	await expect(row).toContainText("Find suppliers");

	// Detail: config card renders supply_criteria fields, not icp_config.
	await row.getByRole("link", { name }).click();
	await expect(page.getByRole("heading", { name })).toBeVisible();
	await expect(page.getByText("Categories")).toBeVisible();
	await expect(page.getByText("fabric")).toBeVisible();
	await expect(page.getByText("Require tax ID")).toBeVisible();
	await expect(page.getByText("Min rating")).toBeVisible();
	await expect(page.getByText("Verified suppliers only")).toBeVisible();
	await expect(page.getByText("Target industries")).toHaveCount(0);
});
