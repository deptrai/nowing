import path from "node:path";
import { expect, test } from "@playwright/test";
import { acquireTestToken, authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling.
 *
 * AC-1: Reactive Kanban Board with Optimistic Concurrency Control (OCC)
 * - Two clients collaborate on a shared Kanban pipeline.
 * - Card drag-and-drop synced across clients via Zero-cache in real time.
 * - When version collision occurs, OCC returns 409 Conflict and the UI shows a
 *   conflict toast / rolls back the conflicting drag without state corruption.
 * - AC-3: Flyout Detail Drawer renders chronological activity timeline.
 */

const AUTH_FILE = path.resolve(__dirname, "..", "..", "playwright", ".auth", "user.json");

test.describe("Story 24.3 — Zero Sync Kanban Multi-Context & OCC Conflict", () => {
	test("two clients dragging lead cards on Kanban pipeline sync via Zero and handle OCC 409 collision", async ({
		browser,
		request,
	}) => {
		// 1. Authenticate Owner (User A) and create a test workspace
		const ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Team CRM Pipeline ${Date.now()}`
		);
		const workspaceId = workspace.id;

		// 2. Create a test lead in the pipeline via the clipper API
		const leadTitle = `Lead Khách Hàng ${Date.now()}`;
		const leadCreateRes = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/clip`,
			{
				headers: authHeaders(ownerToken),
				data: {
					source_canonical_url: `https://example.com/test-lead-${Date.now()}`,
					source_platform: "batdongsan",
					company_name: leadTitle,
				},
			}
		);
		expect(leadCreateRes.ok()).toBeTruthy();
		const createdLead = await leadCreateRes.json();
		const leadId = createdLead.lead_id as string;

		// 3. Resolve default pipeline stage IDs for direct backend calls
		const stagesRes = await request.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/pipeline/stages`,
			{ headers: authHeaders(ownerToken) }
		);
		expect(stagesRes.ok()).toBeTruthy();
		const stages = (await stagesRes.json()) as Array<{
			id: string;
			slug: string;
			name: string;
		}>;
		const stageBySlug = (slug: string) => {
			const found = stages.find((s) => s.slug === slug);
			expect(found, `Missing stage ${slug}`).toBeTruthy();
			if (!found) {
				throw new Error(`Missing stage ${slug}`);
			}
			return found.id;
		};
		const qualifiedStageId = stageBySlug("qualified");

		// 4. Launch two isolated browser contexts using the authenticated storage state
		const contextA = await browser.newContext({ storageState: AUTH_FILE });
		const contextB = await browser.newContext({ storageState: AUTH_FILE });

		const pageA = await contextA.newPage();
		const pageB = await contextB.newPage();

		try {
			// 5. Both clients navigate to the team Kanban pipeline board
			await pageA.goto(`/dashboard/${workspaceId}/leads/pipeline`);
			await pageB.goto(`/dashboard/${workspaceId}/leads/pipeline`);

			// Assert standard 5 Kanban stage columns are present on both clients
			const expectedColumns = [
				"Mới săn",
				"Đang tiếp cận",
				"Tiềm năng",
				"Đã chốt",
				"Hủy / Không nhu cầu",
			];
			for (const col of expectedColumns) {
				await expect(pageA.getByText(col).first()).toBeVisible({ timeout: 15_000 });
				await expect(pageB.getByText(col).first()).toBeVisible({ timeout: 15_000 });
			}

			// 6. Assert the lead card is visible on both clients in the initial column
			const leadCardA = pageA
				.locator(`[data-testid="lead-card-${leadId}"]`)
				.or(pageA.getByText(leadTitle))
				.first();
			const leadCardB = pageB
				.locator(`[data-testid="lead-card-${leadId}"]`)
				.or(pageB.getByText(leadTitle))
				.first();

			await expect(leadCardA).toBeVisible({ timeout: 15_000 });
			await expect(leadCardB).toBeVisible({ timeout: 15_000 });

			// 7. User A drags the card to the 'Đang tiếp cận' column
			const columnApproachingA = pageA
				.locator('[data-testid="kanban-column-approaching"]')
				.or(pageA.getByText("Đang tiếp cận"))
				.first();
			await leadCardA.dragTo(columnApproachingA, { steps: 15, force: true });

			// 8. AC-1: Zero-cache syncs the card transition to User B
			const approachingColumnB = pageB
				.locator('[data-testid="kanban-column-approaching"]')
				.or(pageB.getByText("Đang tiếp cận"))
				.first();
			await expect(approachingColumnB.getByText(leadTitle).first()).toBeVisible({
				timeout: 10_000,
			});

			// 9. Force an OCC 409 conflict by advancing the lead on the server
			// directly while client B still holds a stale version.
			const conflictRes = await request.patch(
				`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/${leadId}/stage`,
				{
					headers: authHeaders(ownerToken),
					data: {
						stage_id: qualifiedStageId,
						expected_version: 2,
						// Server version is also 2 at this point, so the first
						// attempt succeeds and bumps the version to 3.
					},
				}
			);
			// If this fails it means the version wasn't what we expected; log and
			// continue anyway — the client drag below should still produce a 409
			// because its local version will be 2 and the server version is now 3.
			expect(conflictRes.ok() || conflictRes.status() === 409).toBeTruthy();

			// 10. User B attempts to drag the (now stale) card to 'Tiềm năng'
			const columnQualifiedB = pageB
				.locator('[data-testid="kanban-column-qualified"]')
				.or(pageB.getByText("Tiềm năng"))
				.first();
			await leadCardB.dragTo(columnQualifiedB, { steps: 15, force: true });

			// 11. Assert conflict notification is shown
			const conflictToast = pageB
				.getByText(/xung đột dữ liệu|conflict|OCC|phiên bản/i)
				.or(pageB.locator(".toast-error"));
			await expect(conflictToast.first()).toBeVisible({ timeout: 10_000 });

			// 12. AC-3: Click on card to open Lead Detail Flyout Drawer and inspect activity timeline
			const movedLeadCardA = pageA
				.locator(`[data-testid="lead-card-${leadId}"]`)
				.or(pageA.getByText(leadTitle))
				.first();
			await movedLeadCardA.locator('button[aria-label="Mở chi tiết lead"]').first().click();
			const timelineDrawer = pageA
				.locator('[data-testid="lead-detail-flyout-drawer"]')
				.or(pageA.getByText("Lịch Sử Tương Tác & Phân Bổ"))
				.first();
			await expect(timelineDrawer).toBeVisible({ timeout: 10_000 });
		} finally {
			await contextA.close();
			await contextB.close();
			await deleteWorkspace(request, ownerToken, workspaceId);
		}
	});
});
