import { test as base, type APIRequestContext, type Page } from "@playwright/test";
import { createUserFactory } from "./factories/user-factory";

type TestUser = {
	id: string;
	email: string;
	name: string;
	role: string;
};

type InterceptOptions = {
	url: string;
	method?: string;
	fulfillResponse?: { status: number; body: unknown };
	handler?: (route: import("@playwright/test").Route) => Promise<void>;
};

type InterceptResult = {
	url: string;
	status: number;
	body: unknown;
	responseJson: unknown;
};

type ApiRequestParams = {
	method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
	path: string;
	baseUrl?: string;
	body?: unknown;
	headers?: Record<string, string>;
	params?: Record<string, string | number | boolean>;
};

type ApiResult<T = unknown> = { status: number; body: T };

type CustomFixtures = {
	authToken: string;
	testUser: TestUser;
	interceptNetworkCall: (options: InterceptOptions) => Promise<InterceptResult>;
	apiRequest: <T = unknown>(params: ApiRequestParams) => Promise<ApiResult<T>>;
};

const defaultApiUrl = process.env.API_URL ?? "http://localhost:8000";
const email = process.env.TEST_USER_EMAIL ?? "test@nowing.test";
const password = process.env.TEST_USER_PASSWORD ?? "Admin@Nowing1";

async function makeApiRequest<T>(
	request: APIRequestContext,
	params: ApiRequestParams
): Promise<ApiResult<T>> {
	const base = params.baseUrl ?? defaultApiUrl;
	const url = new URL(params.path, base);
	if (params.params) {
		for (const [k, v] of Object.entries(params.params)) {
			url.searchParams.set(k, String(v));
		}
	}
	const response = await request.fetch(url.toString(), {
		method: params.method,
		data: params.body !== undefined ? JSON.stringify(params.body) : undefined,
		headers: {
			"Content-Type": "application/json",
			...params.headers,
		},
	});
	const body = await response.json().catch(() => null);
	return { status: response.status(), body: body as T };
}

async function setupIntercept(page: Page, options: InterceptOptions): Promise<InterceptResult> {
	return new Promise((resolve) => {
		page.route(options.url, async (route) => {
			if (options.fulfillResponse) {
				await route.fulfill({
					status: options.fulfillResponse.status,
					contentType: "application/json",
					body: JSON.stringify(options.fulfillResponse.body),
				});
				resolve({
					url: route.request().url(),
					status: options.fulfillResponse.status,
					body: options.fulfillResponse.body,
					responseJson: options.fulfillResponse.body,
				});
			} else if (options.handler) {
				await options.handler(route);
				resolve({ url: route.request().url(), status: 0, body: null, responseJson: null });
			} else {
				const response = await route.fetch();
				const body = await response.json().catch(() => null);
				await route.fulfill({ response });
				resolve({
					url: route.request().url(),
					status: response.status(),
					body,
					responseJson: body,
				});
			}
		});
	});
}

export const test = base.extend<CustomFixtures>({
	authToken: async ({ request }, use) => {
		const response = await request.post(`${defaultApiUrl}/auth/jwt/login`, {
			form: { username: email, password },
		});
		if (!response.ok()) {
			throw new Error(`Auth failed (${response.status()}): ${await response.text()}`);
		}
		const { access_token } = await response.json();
		await use(access_token as string);
	},

	apiRequest: async ({ request }, use) => {
		await use(<T = unknown>(params: ApiRequestParams) => makeApiRequest<T>(request, params));
	},

	interceptNetworkCall: async ({ page }, use) => {
		await use((options: InterceptOptions) => setupIntercept(page, options));
	},

	testUser: async ({ request }, use) => {
		const user = await createUserFactory(request, { role: "user" });
		await use(user);
		await request.delete(`/api/test/users/${user.id}`).catch(() => {
			/* best-effort cleanup */
		});
	},
});
