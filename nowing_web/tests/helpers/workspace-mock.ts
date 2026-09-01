import type { Page, Route } from "@playwright/test";
import { fulfillJson } from "./cors";

/**
 * Mocks the workspace/llm/model/thread/notification/member/dsh/lead
 * endpoints required to render a dashboard route (e.g.
 * `/dashboard/1/new-chat`) without redirecting to /login or /onboard.
 *
 * Use alongside `mockAdminAuth` when a spec navigates to a dashboard
 * page.
 */
export const ADMIN_USER_ID = "11111111-1111-4111-8111-111111111111";

const mockWorkspace = {
	id: 1,
	name: "Test Workspace",
	description: null,
	vertical: "general",
	created_at: "2026-08-26T00:00:00Z",
	user_id: ADMIN_USER_ID,
	citations_enabled: false,
	api_access_enabled: false,
	qna_custom_instructions: null,
	document_retention_days: null,
	auto_archive_enabled: false,
	document_retention_action: "archive",
	memory_retention_days: null,
	memory_auto_archive_enabled: false,
	memory_retention_action: "archive",
	memory_auto_extract_enabled: true,
	auto_reply_enabled: false,
	auto_reply_collections: [],
	auto_reply_fallback: null,
	auto_reply_recipient_chat_id: null,
	member_count: 1,
	is_owner: true,
};

export async function mockWorkspaceReady(page: Page) {
	// Workspaces list
	await page.route("**/api/v1/workspaces**", async (route: Route) => {
		await fulfillJson(route, 200, [mockWorkspace]);
	});

	// Workspace detail (exact id, no trailing wildcard, so sub-routes
	// like /llm-setup-status and /model-roles are not swallowed).
	await page.route("**/api/v1/workspaces/1", async (route: Route) => {
		if (route.request().method() === "GET") {
			await fulfillJson(route, 200, { ...mockWorkspace, member_count: undefined });
		} else {
			await route.continue();
		}
	});

	// LLM setup status (ready so we never redirect to /onboard)
	await page.route("**/api/v1/workspaces/1/llm-setup-status**", async (route: Route) => {
		await fulfillJson(route, 200, {
			status: "ready",
			source: "global_config",
			can_configure: true,
			stage: "ready",
		});
	});

	// Model connections (empty)
	await page.route("**/api/v1/model-connections**", async (route: Route) => {
		await fulfillJson(route, 200, []);
	});

	// Model roles
	await page.route("**/api/v1/workspaces/1/model-roles**", async (route: Route) => {
		await fulfillJson(route, 200, {
			chat_model_id: null,
			vision_model_id: null,
			image_gen_model_id: null,
		});
	});

	// Threads
	await page.route("**/api/v1/threads**", async (route: Route) => {
		await fulfillJson(route, 200, { threads: [], archived_threads: [] });
	});

	// Notifications
	await page.route("**/api/v1/notifications**", async (route: Route) => {
		await fulfillJson(route, 200, {
			items: [],
			total: 0,
			has_more: false,
			next_offset: null,
		});
	});

	// Unread counts
	await page.route("**/api/v1/notifications/unread-count*", async (route: Route) => {
		await fulfillJson(route, 200, { total_unread: 0, recent_unread: 0 });
	});

	await page.route("**/api/v1/notifications/unread-counts-batch**", async (route: Route) => {
		await fulfillJson(route, 200, {
			comments: { total_unread: 0, recent_unread: 0 },
			status: { total_unread: 0, recent_unread: 0 },
		});
	});

	// Members
	await page.route("**/api/v1/workspaces/1/members**", async (route: Route) => {
		await fulfillJson(route, 200, []);
	});

	await page.route("**/api/v1/workspaces/1/my-access**", async (route: Route) => {
		await fulfillJson(route, 200, {
			workspace_name: mockWorkspace.name,
			workspace_id: 1,
			is_owner: true,
			permissions: [],
			role_name: null,
		});
	});

	// DSH missions
	await page.route("**/api/v1/workspaces/1/dsh/missions**", async (route: Route) => {
		await fulfillJson(route, 200, {
			items: [],
			total: 0,
			limit: 1,
			offset: 0,
		});
	});

	// Leads
	await page.route("**/api/v1/workspaces/1/leads**", async (route: Route) => {
		await fulfillJson(route, 200, {
			items: [],
			total: 0,
			limit: 10,
			offset: 0,
		});
	});

	// Document search titles
	await page.route("**/api/v1/documents/search/titles**", async (route: Route) => {
		await fulfillJson(route, 200, {
			items: [],
			has_more: false,
		});
	});

	// Scraper capabilities
	await page.route("**/api/v1/workspaces/1/scrapers/capabilities**", async (route: Route) => {
		await fulfillJson(route, 200, []);
	});
}
