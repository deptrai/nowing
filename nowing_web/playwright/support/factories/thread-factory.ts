type ThreadOverrides = {
	title?: string;
	model?: string;
	searchSpaceId?: string;
};

type CreatedThread = {
	id: number;
	title: string;
	model: string;
};

let _counter = 0;

export async function createThreadFactory(
	request: import("@playwright/test").APIRequestContext,
	authToken: string,
	overrides: ThreadOverrides = {}
): Promise<CreatedThread> {
	const n = ++_counter;

	const payload = {
		title: overrides.title ?? `Test Thread ${n} — ${Date.now()}`,
		model: overrides.model ?? "gpt-4o-mini",
		...(overrides.searchSpaceId ? { search_space_id: overrides.searchSpaceId } : {}),
	};

	const apiUrl = process.env.API_URL || "http://localhost:8000";
	const response = await request.post(`${apiUrl}/api/v1/threads`, {
		data: payload,
		headers: { Authorization: `Bearer ${authToken}` },
	});

	if (!response.ok()) {
		throw new Error(
			`createThreadFactory failed: HTTP ${response.status()} — ${await response.text()}`
		);
	}

	return response.json() as Promise<CreatedThread>;
}
