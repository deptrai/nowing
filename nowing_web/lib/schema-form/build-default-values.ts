import type { JSONSchema } from "@/contracts/types/schema-ui.types";

export function buildDefaultValues(
	schema: JSONSchema,
	existing: Record<string, unknown> = {}
): Record<string, unknown> {
	const result: Record<string, unknown> = {};
	if (schema.type !== "object" || !schema.properties) {
		return { value: existing };
	}

	const required = new Set(schema.required ?? []);
	for (const [key, prop] of Object.entries(schema.properties)) {
		if (key in existing && existing[key] !== undefined) {
			if (
				prop.type === "object" &&
				prop.properties &&
				typeof existing[key] === "object" &&
				existing[key] !== null
			) {
				result[key] = buildDefaultValues(prop, existing[key] as Record<string, unknown>);
			} else {
				result[key] = existing[key];
			}
			continue;
		}
		result[key] = propertyDefault(prop, key, required.has(key));
	}
	return result;
}

function propertyDefault(prop: JSONSchema, key: string, required: boolean): unknown {
	const options = prop["x-ui"]?.options;
	const enumValues = prop.enum;
	const propConst = prop.const;

	if (propConst !== undefined) {
		return propConst;
	}

	if (options && options.length === 1) {
		return options[0].value;
	}

	if (enumValues && enumValues.length === 1) {
		return enumValues[0];
	}

	if (prop.default !== undefined) {
		return prop.default;
	}

	if (prop.anyOf) {
		const nullBranch = prop.anyOf.find(
			(b) =>
				b.type === "null" || (Array.isArray(b.enum) && b.enum.length === 1 && b.enum[0] === null)
		);
		const realBranch = prop.anyOf.find(
			(b) =>
				b.type !== "null" && !(Array.isArray(b.enum) && b.enum.length === 1 && b.enum[0] === null)
		);
		if (realBranch) {
			if (realBranch.default !== undefined) {
				return realBranch.default;
			}
			if (nullBranch) {
				// Nullable optional field with no explicit default starts as null.
				return required ? propertyDefault(realBranch, key, true) : null;
			}
			return propertyDefault(realBranch, key, required);
		}
	}

	if (prop.type === "object" && prop.properties) {
		return buildDefaultValues(prop);
	}

	if (prop.type === "array") {
		return [];
	}

	if (prop.type === "boolean") {
		return prop.default ?? false;
	}

	if (prop.type === "number" || prop.type === "integer") {
		return prop.default ?? undefined;
	}

	if (prop.type === "string") {
		if (enumValues && enumValues.length > 1) {
			return required ? enumValues[0] : undefined;
		}
		return "";
	}

	if (enumValues && enumValues.length > 0) {
		return required ? enumValues[0] : undefined;
	}

	return "";
}
