import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveWebsetsMetadata } from "../LeadDetailFlyoutDrawer";

test("resolveWebsetsMetadata returns object for valid metadata.websets", () => {
	const meta = { opening_hours: { value: "08:00", status: "verified" } };
	const lead = { metadata: { websets: meta } };
	assert.deepEqual(resolveWebsetsMetadata(lead as never), meta);
});

test("resolveWebsetsMetadata falls back to extra_metadata.websets", () => {
	const meta = { annual_revenue: { value: "$5M" } };
	const lead = { extra_metadata: { websets: meta } };
	assert.deepEqual(resolveWebsetsMetadata(lead as never), meta);
});

test("resolveWebsetsMetadata returns undefined for malformed payloads", () => {
	for (const bad of [
		null,
		undefined,
		{},
		{ metadata: null },
		{ metadata: { websets: null } },
		{ metadata: { websets: "not-an-object" } },
		{ metadata: { websets: 42 } },
		{ metadata: { websets: ["a", "b"] } },
	]) {
		assert.equal(
			resolveWebsetsMetadata(bad as never),
			undefined,
			`should be undefined for ${JSON.stringify(bad)}`
		);
	}

	// Nested arrays inside a valid object are allowed — the guard only
	// rejects a websets payload that is itself non-object/array.
	const obj = resolveWebsetsMetadata({
		metadata: { websets: { nested: [] } },
	} as never);
	assert.deepEqual(obj, { nested: [] });
});
