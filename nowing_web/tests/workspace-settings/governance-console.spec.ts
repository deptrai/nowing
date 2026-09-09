import { expect, type Page, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

async function dismissOnboardingModal(page: Page) {
	const gotIt = page.getByRole("button", { name: /got it/i });
	try {
		await expect(gotIt).toBeVisible({ timeout: 3000 });
		await gotIt.click();
	} catch {
		// Onboarding modal not displayed in this session
	}
}

/**
 * End-to-End browser tests for Story 29.6: Data Governance & Retention Policy Console.
 *
 * Verifies:
 * - AC-1: Governance console tabs overview (Retention, Source Risk Tiers, DNC, Audit Log, Status)
 * - AC-2: Retention policy editing, inputs, and save actions
 * - AC-3: Source risk tiers table rendering and Edit dialog
 * - AC-4: Right-to-delete panel (single vs bulk mode, dry-run preview)
 * - AC-5: Workspace DNC management (modal dialog, list, delete)
 * - Navigation: Governance entry in workspace settings navigation shell
 */
test.describe("Story 29.6 — Data Governance & Retention Policy Console", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`E2E Governance Test ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		if (workspaceId && ownerToken) {
			await deleteWorkspace(request, ownerToken, workspaceId).catch(() => {
				// Ignore cleanup failures on ephemeral test workspaces
			});
		}
	});

	test("AC-1: Owner can navigate to governance console and view all five tabs", async ({
		page,
	}) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		// Verify page title
		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		// Verify 5 tab triggers inside governance console tabs
		const retentionTab = page.getByRole("tab", { name: /data retention|chính sách lưu trữ/i });
		const sourceTiersTab = page.getByRole("tab", {
			name: /source risk tiers|cấp độ rủi ro nguồn/i,
		});
		const dncTab = page.getByRole("tab", { name: /dnc/i });
		const auditLogTab = page.getByRole("tab", { name: /audit log|nhật ký kiểm toán/i });
		const statusTab = page.getByRole("tab", { name: /workspace status|trạng thái workspace/i });

		await expect(retentionTab).toBeVisible();
		await expect(sourceTiersTab).toBeVisible();
		await expect(dncTab).toBeVisible();
		await expect(auditLogTab).toBeVisible();
		await expect(statusTab).toBeVisible();

		// Default active tab is retention
		const retentionSection = page.getByRole("region", {
			name: /data retention|chính sách lưu trữ/i,
		});
		await expect(retentionSection).toBeVisible();
	});

	test("AC-1: Tab switching displays corresponding governance sections", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		// 1. Switch to Source Risk Tiers
		await page.getByRole("tab", { name: /source risk tiers|cấp độ rủi ro nguồn/i }).click();
		const tiersSection = page.getByRole("region", {
			name: /source risk tiers|cấp độ rủi ro nguồn/i,
		});
		await expect(tiersSection).toBeVisible();
		await expect(tiersSection.getByText("scraper_run")).toBeVisible();

		// 2. Switch to DNC
		await page.getByRole("tab", { name: /dnc/i }).click();
		const dncSection = page.getByRole("region", { name: /do-not-call|dnc/i });
		await expect(dncSection).toBeVisible();
		await expect(
			dncSection.getByRole("button", { name: /add dnc record|thêm bản ghi dnc/i })
		).toBeVisible();

		// 3. Switch to Audit Log
		await page.getByRole("tab", { name: /audit log|nhật ký kiểm toán/i }).click();
		const auditSection = page.getByRole("region", { name: /audit log|nhật ký kiểm toán/i });
		await expect(auditSection).toBeVisible();

		// 4. Switch to Workspace Status
		await page.getByRole("tab", { name: /workspace status|trạng thái workspace/i }).click();
		const statusSection = page.getByRole("region", {
			name: /workspace status|trạng thái workspace/i,
		});
		await expect(statusSection).toBeVisible();
		const rtdSection = page.getByRole("region", {
			name: /right to delete|quyền xóa|quyền được xoá/i,
		});
		await expect(rtdSection).toBeVisible();
	});

	test("AC-2: Owner can edit and save data retention policy", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		const retentionSection = page.getByRole("region", {
			name: /data retention|chính sách lưu trữ/i,
		});
		await expect(retentionSection).toBeVisible();

		const docDaysInput = retentionSection.locator("#doc-retention-days");
		await expect(docDaysInput).toBeVisible();
		await docDaysInput.fill("180");

		const memDaysInput = retentionSection.locator("#mem-retention-days");
		await expect(memDaysInput).toBeVisible();
		await memDaysInput.fill("90");

		const saveBtn = retentionSection.getByRole("button", { name: /save changes|lưu thay đổi/i });
		await expect(saveBtn).toBeVisible();
		await saveBtn.click();

		// Verify success toast notification
		const toastMsg = page.getByText(/retention policy saved|đã lưu chính sách lưu trữ/i);
		await expect(toastMsg).toBeVisible({ timeout: 10_000 });
	});

	test("AC-3: Source risk tier edit dialog opens and shows tier options", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		await page.getByRole("tab", { name: /source risk tiers|cấp độ rủi ro nguồn/i }).click();
		const tiersSection = page.getByRole("region", {
			name: /source risk tiers|cấp độ rủi ro nguồn/i,
		});
		await expect(tiersSection).toBeVisible();

		const firstEditBtn = tiersSection.getByRole("button", { name: /edit|chỉnh sửa/i }).first();
		await expect(firstEditBtn).toBeVisible();
		await firstEditBtn.click();

		// Dialog should open
		const dialog = page.getByRole("dialog");
		await expect(dialog).toBeVisible();
		const riskSelect = dialog.locator("#risk-tier");
		await expect(riskSelect).toBeVisible();

		// Cancel dialog
		await dialog.getByRole("button", { name: /cancel|hủy|huỷ/i }).click();
		await expect(dialog).not.toBeVisible();
	});

	test("AC-5: Owner can add a DNC record and remove it", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		await page.getByRole("tab", { name: /dnc/i }).click();
		const dncSection = page.getByRole("region", { name: /do-not-call|dnc/i });
		await expect(dncSection).toBeVisible();

		// Open Add dialog
		const addBtn = dncSection.getByRole("button", { name: /add dnc record|thêm bản ghi dnc/i });
		await addBtn.click();

		const dialog = page.getByRole("dialog");
		await expect(dialog).toBeVisible();

		const valueInput = dialog.locator("#dnc-value");
		const reasonInput = dialog.locator("#dnc-reason");
		const testPhone = "+84988776655";

		await valueInput.fill(testPhone);
		await reasonInput.fill("Customer opt-out request");

		const submitBtn = dialog.getByRole("button", { name: /save|lưu/i });
		await submitBtn.click();

		// Verify record added in table
		await expect(dialog).not.toBeVisible();
		const table = dncSection.getByRole("table");
		await expect(table.getByText(/Customer opt-out request/i)).toBeVisible({ timeout: 10_000 });

		// Clean up: delete the newly added DNC record
		const deleteBtn = table.getByRole("button", { name: /delete|xóa|xoá/i }).first();
		await deleteBtn.click();
		await expect(table.getByText(/Customer opt-out request/i)).not.toBeVisible({ timeout: 10_000 });
	});

	test("AC-4: Right to Delete panel supports bulk dry-run preview", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/governance`);
		await dismissOnboardingModal(page);

		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible({ timeout: 15_000 });

		await page.getByRole("tab", { name: /workspace status|trạng thái workspace/i }).click();
		const rtdSection = page.getByRole("region", {
			name: /right to delete|quyền xóa|quyền được xoá/i,
		});
		await expect(rtdSection).toBeVisible();

		// Switch to bulk mode
		const bulkBtn = rtdSection.getByRole("button", {
			name: /bulk by source|hàng loạt|xóa hàng loạt|xoá hàng loạt/i,
		});
		await expect(bulkBtn).toBeVisible();
		await bulkBtn.click();

		// Verify bulk filter fields exist
		await expect(rtdSection.locator("#rtd-source-type")).toBeVisible();
		await expect(rtdSection.locator("#rtd-source-id")).toBeVisible();
		await expect(rtdSection.locator("#rtd-source-entity-type")).toBeVisible();

		// Run dry run
		const dryRunBtn = rtdSection.getByRole("button", {
			name: /run dry-run|chạy thử|thử nghiệm|chạy thử nghiệm/i,
		});
		await expect(dryRunBtn).toBeVisible();
		await dryRunBtn.click();

		// Dry run result card should display
		const resultCard = rtdSection.getByText(/dry-run result|kết quả chạy thử|kết quả thử nghiệm/i);
		await expect(resultCard).toBeVisible({ timeout: 10_000 });
	});

	test("Navigation: Workspace settings shell links directly to governance console", async ({
		page,
	}) => {
		await page.goto(`/dashboard/${workspaceId}/workspace-settings/general`);
		await dismissOnboardingModal(page);

		// Find Governance nav item in settings sidebar / nav list
		const govLink = page.getByRole("link", { name: /governance|quản trị/i });
		await expect(govLink).toBeVisible();
		await govLink.click();

		// URL should update to /governance
		await expect(page).toHaveURL(new RegExp(`/dashboard/${workspaceId}/governance`));
		const heading = page.getByRole("heading", { name: /governance|quản trị dữ liệu/i, level: 1 });
		await expect(heading).toBeVisible();
	});
});
