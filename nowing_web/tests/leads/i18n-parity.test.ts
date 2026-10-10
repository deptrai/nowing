import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function flattenKeys(obj: unknown, prefix = ""): string[] {
	if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
		return [prefix];
	}
	return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
		flattenKeys(v, `${prefix}${k}.`)
	);
}

test("en.json and vi.json have identical key sets under leads.*", () => {
	const en = JSON.parse(readFileSync(join(__dirname, "../../messages/en.json"), "utf8")) as {
		leads?: unknown;
	};
	const vi = JSON.parse(readFileSync(join(__dirname, "../../messages/vi.json"), "utf8")) as {
		leads?: unknown;
	};

	const enKeys = new Set(flattenKeys(en.leads));
	const viKeys = new Set(flattenKeys(vi.leads));

	const enOnly = [...enKeys].filter((k) => !viKeys.has(k));
	const viOnly = [...viKeys].filter((k) => !enKeys.has(k));

	assert.deepEqual(
		enOnly,
		[],
		`Keys present in en.json but missing in vi.json: ${enOnly.join(", ")}`
	);
	assert.deepEqual(
		viOnly,
		[],
		`Keys present in vi.json but missing in en.json: ${viOnly.join(", ")}`
	);
});
