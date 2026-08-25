import { expect, test } from "@playwright/test";
import { acquireTestToken } from "./helpers/api/auth";

test.describe("PostHog API smoke", () => {
	test("seeded e2e user can create and list workspaces", async ({ request }) => {
		const token = await acquireTestToken(request);

		const create = await request.post("http://localhost:8000/api/v1/workspaces", {
			data: {
				name: "API Smoke Workspace",
				description: "PostHog privacy hardening smoke test",
			},
			headers: {
				Authorization: `Bearer ${token}`,
				"Content-Type": "application/json",
				Origin: "http://localhost:3000",
			},
		});

		expect(create.ok()).toBeTruthy();
		const body = (await create.json()) as { id: number; name: string };
		expect(body).toHaveProperty("id");
		expect(typeof body.id).toBe("number");

		const list = await request.get("http://localhost:8000/api/v1/workspaces", {
			headers: {
				Authorization: `Bearer ${token}`,
				Origin: "http://localhost:3000",
			},
		});

		expect(list.ok()).toBeTruthy();
		const workspaces = (await list.json()) as { id: number }[];
		expect(workspaces.some((w) => w.id === body.id)).toBeTruthy();
	});
});
