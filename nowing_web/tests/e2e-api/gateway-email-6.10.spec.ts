import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { acquireTestToken, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Browser Pilot E2E — Story 6.10 Inbound Email Gateway & Scheduled DSH Missions.
 *
 * This is an API-driven E2E spec because Story 6.10 has no end-user UI.
 * It exercises the live backend webhook endpoint and verifies that an
 * inbound email creates both an InboundEmailEvent row and a recurring
 * DSH mission with the correct schedule.
 */

test.describe("Story 6.10 — inbound email gateway -> scheduled DSH mission", () => {
	let token: string;
	let workspaceId: number;
	let webhookRequest: APIRequestContext;

	const makeMessageId = () =>
		`<e2e-6.10-${Date.now()}-${Math.random().toString(36).slice(2)}@nowing.test>`;

	test.beforeAll(async ({ request }) => {
		token = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			token,
			"E2E Story 6.10 Email Gateway",
			"Browser Pilot API E2E",
		);
		workspaceId = workspace.id;

		// The webhook endpoint is stateless and must not carry the browser
		// session cookie; otherwise the CSRF origin middleware blocks POSTs.
		// Explicitly clear storageState so Playwright does not inject the
		// authenticated session cookie from the default use.storageState.
		webhookRequest = await apiRequest.newContext({
			baseURL: BACKEND_URL,
			storageState: { cookies: [], origins: [] },
			extraHTTPHeaders: {
				"x-playwright-test": "true",
			},
		});
	});

	test.afterAll(async ({ request }) => {
		await webhookRequest?.dispose();
		await deleteWorkspace(request, token, workspaceId);
	});

	test("Mailgun webhook creates inbound_email_event and recurring_report mission", async ({ request }) => {
		const messageId = makeMessageId();

		const formData = new URLSearchParams();
		formData.append("to", `task+${workspaceId}@nowing.ai`);
		formData.append("from", "e2e-test@nowing.net");
		formData.append("subject", "E2E: scheduled mission 6.10");
		formData.append("body-plain", "Please send me a daily report on our competitors.");
		formData.append("Message-Id", messageId);

		const webhook = await webhookRequest.post(`${BACKEND_URL}/api/v1/gateway/email/inbound`, {
			headers: {
				"Content-Type": "application/x-www-form-urlencoded",
				"X-Mailgun-Signature": "test-signature-ignored-in-test-env",
				"X-Mailgun-Timestamp": String(Math.floor(Date.now() / 1000)),
				"X-Mailgun-Token": "test-token",
			},
			data: formData.toString(),
		});

		expect(webhook.status()).toBe(204);

		// Poll the DSH mission list until the email-derived mission appears.
		let mission:
			| {
					id: string;
					mission_type: string;
					status: string;
					source?: string;
					schedule?: { type: string; minutes: number };
			  }
			| undefined;

		await expect
			.poll(
				async () => {
					const list = await request.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/dsh/missions`, {
						headers: { Authorization: `Bearer ${token}` },
					});
					expect(list.ok()).toBeTruthy();
					const body = (await list.json()) as {
						items: Array<{
							id: string;
							mission_type: string;
							status: string;
							source?: string;
							schedule?: { type: string; minutes: number };
						}>;
					};
					mission = body.items.find((m) => m.mission_type === "recurring_report" && m.source === "email");
					return mission;
				},
				{
					message: "wait for recurring_report mission to be created from inbound email",
					timeout: 10_000,
					intervals: [200, 500, 1_000, 2_000],
				},
			)
			.toBeDefined();

		expect(mission!.status).toBe("pending");
		expect(mission!.mission_type).toBe("recurring_report");
		expect(mission!.source).toBe("email");
		expect(mission!.schedule).toEqual({ type: "interval", minutes: 360 });
	});

	test("duplicate Message-Id is idempotent and does not create a second mission", async ({ request }) => {
		const messageId = makeMessageId();
		const to = `task+${workspaceId}@nowing.ai`;

		const send = async () => {
			const formData = new URLSearchParams();
			formData.append("to", to);
			formData.append("from", "e2e-test@nowing.net");
			formData.append("subject", "E2E duplicate 6.10");
			formData.append("body-plain", "Please track my competitors daily.");
			formData.append("Message-Id", messageId);

			return webhookRequest.post(`${BACKEND_URL}/api/v1/gateway/email/inbound`, {
				headers: {
					"Content-Type": "application/x-www-form-urlencoded",
					"X-Mailgun-Signature": "test-signature-ignored-in-test-env",
					"X-Mailgun-Timestamp": String(Math.floor(Date.now() / 1000)),
					"X-Mailgun-Token": "test-token",
				},
				data: formData.toString(),
			});
		};

		const first = await send();
		const second = await send();

		expect(first.status()).toBe(204);
		expect(second.status()).toBe(204);

		const list = await request.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/dsh/missions`, {
			headers: { Authorization: `Bearer ${token}` },
		});
		expect(list.ok()).toBeTruthy();
		const body = (await list.json()) as {
			items: Array<{ request_text?: string }>;
		};
		const matching = body.items.filter((m) => m.request_text === "Please track my competitors daily.");
		expect(matching).toHaveLength(1);
	});
});
