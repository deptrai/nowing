import { type APIRequestContext, request as apiRequest, expect, test } from "@playwright/test";
import { acquireTestToken, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Browser Pilot API E2E — Story 3.18: Projects Persistent Workspace & Modular Skills Hub.
 *
 * The frontend UI for projects/skills is not yet implemented, so this spec
 * exercises the live REST endpoints directly through Playwright's request
 * context. It validates CRUD, workspace isolation, document pinning, and
 * .skill.md parsing/execution wiring.
 */

test.describe("Story 3.18 — Projects & Modular Skills Hub API E2E", () => {
	let token: string;
	let workspaceId: number;
	let api: APIRequestContext;

	test.beforeAll(async ({ request }) => {
		token = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			token,
			"E2E Story 3.18 Projects & Skills",
			"Browser Pilot API E2E"
		);
		workspaceId = workspace.id;

		api = await apiRequest.newContext({
			baseURL: BACKEND_URL,
			extraHTTPHeaders: {
				"x-playwright-test": "true",
				Authorization: `Bearer ${token}`,
				"Content-Type": "application/json",
			},
		});
	});

	test.afterAll(async ({ request }) => {
		await api?.dispose();
		await deleteWorkspace(request, token, workspaceId);
	});

	test("project CRUD lifecycle with workspace isolation", async () => {
		const create = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects`, {
			data: {
				name: "Q3 Real Estate Strategy",
				description: "Research on HCMC residential market",
				master_instructions: "Focus on District 2 and District 7 trends.",
			},
		});
		expect(create.ok()).toBeTruthy();
		const created = (await create.json()) as {
			id: number;
			workspace_id: number;
			name: string;
			master_instructions: string;
			is_archived: boolean;
		};
		expect(created.workspace_id).toBe(workspaceId);
		expect(created.name).toBe("Q3 Real Estate Strategy");
		expect(created.master_instructions).toContain("District 2");
		expect(created.is_archived).toBe(false);

		const list = await api.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects`);
		expect(list.ok()).toBeTruthy();
		const projects = (await list.json()) as (typeof created)[];
		expect(projects.some((p) => p.id === created.id)).toBe(true);

		const update = await api.patch(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects/${created.id}`,
			{
				data: { name: "Q3 Real Estate Strategy (Updated)" },
			}
		);
		expect(update.ok()).toBeTruthy();
		const updated = (await update.json()) as typeof created;
		expect(updated.name).toBe("Q3 Real Estate Strategy (Updated)");

		const get = await api.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects/${created.id}`
		);
		expect(get.ok()).toBeTruthy();
		const got = (await get.json()) as typeof created;
		expect(got.name).toBe("Q3 Real Estate Strategy (Updated)");

		// Isolation: projects in another workspace should not be reachable.
		const otherWorkspace = await createWorkspace(
			api as unknown as APIRequestContext,
			token,
			"E2E Story 3.18 Other Workspace"
		);
		const cross = await api.get(
			`${BACKEND_URL}/api/v1/workspaces/${otherWorkspace.id}/projects/${created.id}`
		);
		expect(cross.status()).toBe(404);
		await deleteWorkspace(api as unknown as APIRequestContext, token, otherWorkspace.id);

		// Archive is treated as a logical delete for the list endpoint.
		const archive = await api.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects/${created.id}/archive`,
			{ data: {} }
		);
		expect(archive.ok()).toBeTruthy();

		const listAfterArchive = await api.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/projects`
		);
		expect(listAfterArchive.ok()).toBeTruthy();
		const projectsAfterArchive = (await listAfterArchive.json()) as (typeof created)[];
		expect(projectsAfterArchive.some((p) => p.id === created.id)).toBe(false);
	});

	test(".skill.md parse endpoint extracts frontmatter and body", async () => {
		const skillMd = `---
name: Competitor Pulse
description: Daily competitor intelligence brief
trigger: competitor pulse
parameters:
  competitor:
    type: string
    description: Name of the competitor to track
---

When the user asks about a competitor, research the latest news and provide a concise summary with sources.
`;

		const parse = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills/parse`, {
			data: { file_content: skillMd },
		});
		expect(parse.ok()).toBeTruthy();
		const parsed = (await parse.json()) as {
			name: string;
			slug: string;
			description: string;
			trigger_pattern: string;
			parameters_schema: Record<string, unknown>;
			content_markdown: string;
		};
		expect(parsed.name).toBe("Competitor Pulse");
		expect(parsed.slug).toBe("competitor-pulse");
		expect(parsed.description).toBe("Daily competitor intelligence brief");
		expect(parsed.trigger_pattern).toBe("competitor pulse");
		expect(parsed.parameters_schema).toHaveProperty("competitor");
		expect(parsed.content_markdown).toContain("When the user asks");
	});

	test("skill CRUD lifecycle with active/inactive filtering", async () => {
		const create = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills`, {
			data: {
				name: "Local News Digest",
				slug: "local-news-digest",
				description: "Daily local market news summary",
				trigger_pattern: "local news",
				skill_type: "prompt",
				content_markdown: "Summarize the top 3 local news items.",
				parameters_schema: {},
				is_active: true,
			},
		});
		expect(create.ok()).toBeTruthy();
		const created = (await create.json()) as {
			id: number;
			workspace_id: number;
			name: string;
			slug: string;
			is_active: boolean;
		};
		expect(created.workspace_id).toBe(workspaceId);
		expect(created.slug).toBe("local-news-digest");

		const list = await api.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills`);
		expect(list.ok()).toBeTruthy();
		const skills = (await list.json()) as (typeof created)[];
		expect(skills.some((s) => s.id === created.id)).toBe(true);

		const update = await api.patch(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills/${created.id}`,
			{
				data: { is_active: false },
			}
		);
		expect(update.ok()).toBeTruthy();

		const listActive = await api.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills?include_inactive=false`
		);
		expect(listActive.ok()).toBeTruthy();
		const activeSkills = (await listActive.json()) as (typeof created)[];
		expect(activeSkills.some((s) => s.id === created.id)).toBe(false);

		const listInactive = await api.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills?include_inactive=true`
		);
		expect(listInactive.ok()).toBeTruthy();
		const inactiveSkills = (await listInactive.json()) as (typeof created)[];
		expect(inactiveSkills.some((s) => s.id === created.id)).toBe(true);
	});

	test("execute prompt skill renders parameters and returns content", async () => {
		const create = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills`, {
			data: {
				name: "Local Market Summary",
				slug: "local-market-summary",
				description: "Summarize local market news",
				trigger_pattern: "local market",
				skill_type: "prompt",
				content_markdown: "Summarize top 3 {{topic}} stories in {{location}}.",
				parameters_schema: {
					topic: { type: "string" },
					location: { type: "string" },
				},
				is_active: true,
			},
		});
		expect(create.ok()).toBeTruthy();
		const created = (await create.json()) as {
			id: number;
			workspace_id: number;
			slug: string;
		};

		const exec = await api.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills/${created.id}/execute`,
			{
				data: { parameters: { topic: "real estate", location: "District 2" } },
			}
		);
		expect(exec.ok()).toBeTruthy();
		const result = (await exec.json()) as {
			type: string;
			skill_id: number;
			skill_slug: string;
			content: string;
		};
		expect(result.type).toBe("prompt");
		expect(result.skill_id).toBe(created.id);
		expect(result.skill_slug).toBe("local-market-summary");
		expect(result.content).toContain("real estate");
		expect(result.content).toContain("District 2");
	});

	test("execute workflow skill dispatches a DSH mission", async () => {
		const create = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills`, {
			data: {
				name: "Lead Scraping Mission",
				slug: "lead-scraping-mission",
				description: "Trigger lead scraping workflow",
				trigger_pattern: "/scrape-leads",
				skill_type: "workflow",
				content_markdown: "# Lead scraping workflow",
				parameters_schema: { competitor: { type: "string" } },
				is_active: true,
			},
		});
		expect(create.ok()).toBeTruthy();
		const created = (await create.json()) as {
			id: number;
			workspace_id: number;
			slug: string;
		};

		const exec = await api.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills/${created.id}/execute`,
			{
				data: { parameters: { competitor: "VinGroup" } },
			}
		);
		expect(exec.ok()).toBeTruthy();
		const result = (await exec.json()) as {
			type: string;
			skill_id: number;
			mission_id: string;
			status: string;
		};
		expect(result.type).toBe("workflow");
		expect(result.skill_id).toBe(created.id);
		expect(result.mission_id).toBeTruthy();
		expect(result.status).toBe("pending");

		// Verify the mission payload references the skill and parameters.
		const missionId = result.mission_id;
		const mission = await api.get(`${BACKEND_URL}/api/v1/dsh/missions/${missionId}`);
		if (mission.ok()) {
			const missionBody = (await mission.json()) as {
				payload: { skill_id: number; skill_slug: string; parameters: { competitor: string } };
			};
			expect(missionBody.payload.skill_id).toBe(created.id);
			expect(missionBody.payload.skill_slug).toBe("lead-scraping-mission");
			expect(missionBody.payload.parameters.competitor).toBe("VinGroup");
		}
	});

	test("execute inactive skill returns 400", async () => {
		const create = await api.post(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills`, {
			data: {
				name: "Inactive Skill",
				slug: "inactive-skill",
				description: "Should not run",
				trigger_pattern: "inactive",
				skill_type: "prompt",
				content_markdown: "Do nothing.",
				parameters_schema: {},
				is_active: false,
			},
		});
		expect(create.ok()).toBeTruthy();
		const created = (await create.json()) as { id: number };

		const exec = await api.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/skills/${created.id}/execute`,
			{ data: { parameters: {} } }
		);
		expect(exec.status()).toBe(400);
	});
});
