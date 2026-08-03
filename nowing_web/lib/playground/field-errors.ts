import type { AppError, ValidationFieldError } from "../error";

/**
 * Map a 422 error envelope's `fields` to a `fieldName -> message` map for
 * inline display. Only `body` loc roots map to top-level field names; the
 * first failure per field wins.
 */
export function fieldErrorsFromError(error: unknown): Record<string, string> {
	if (!error || typeof error !== "object") return {};
	const fields = (error as AppError).fields;
	if (!Array.isArray(fields)) return {};
	const result: Record<string, string> = {};
	for (const item of fields as ValidationFieldError[]) {
		const field = fieldNameFromLoc(item.loc);
		if (!field || field in result) continue;
		result[field] = item.msg;
	}
	return result;
}

function fieldNameFromLoc(loc: (string | number)[] | undefined): string | undefined {
	if (!Array.isArray(loc) || loc.length < 2 || loc[0] !== "body") return undefined;
	const name = loc[1];
	return typeof name === "string" && name.length > 0 ? name : undefined;
}
