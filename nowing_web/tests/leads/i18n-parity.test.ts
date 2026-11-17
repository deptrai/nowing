import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

function flattenKeys(obj: unknown, prefix = ""): string[] {
	if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
		return [prefix];
	}
	return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
		flattenKeys(v, `${prefix}${k}.`)
	);
}

test("en.json and vi.json have identical key sets under leads.*", () => {
	const enPath = join(process.cwd(), "messages/en.json");
	const viPath = join(process.cwd(), "messages/vi.json");
	const en = JSON.parse(readFileSync(enPath, "utf8")) as {
		leads?: unknown;
	};
	const vi = JSON.parse(readFileSync(viPath, "utf8")) as {
		leads?: unknown;
	};

	const enKeys = new Set(flattenKeys(en.leads));
	const viKeys = new Set(flattenKeys(vi.leads));

	const enOnly = [...enKeys].filter((k) => !viKeys.has(k));
	const viOnly = [...viKeys].filter((k) => !enKeys.has(k));

	expect(enOnly).toEqual([]);
	expect(viOnly).toEqual([]);
});
