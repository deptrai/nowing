import type { JSONSchema, SchemaUiHints, SchemaUiOption } from "@/contracts/types/schema-ui.types";

export function toTitleCase(value: string): string {
	return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fieldLabel(schema: JSONSchema, name: string): string {
	return schema["x-ui"]?.label ?? schema.title ?? toTitleCase(name);
}

export function fieldDescription(schema: JSONSchema): string | undefined {
	return schema.description;
}

export function fieldUi(schema: JSONSchema): SchemaUiHints | undefined {
	return schema["x-ui"];
}

export function optionsFromSchema(schema: JSONSchema): SchemaUiOption[] {
	const ui = fieldUi(schema);
	if (ui?.options && ui.options.length > 0) {
		return ui.options;
	}
	if (schema.enum && schema.enum.length > 0) {
		return schema.enum.map((value) => ({ label: String(value), value }));
	}
	if (schema.const !== undefined) {
		return [{ label: String(schema.const), value: schema.const }];
	}
	return [];
}

export function valueToString(value: unknown): string {
	if (value === undefined || value === null) return "";
	return String(value);
}

export function stringToValue(raw: string, options: SchemaUiOption[], baseType?: string): unknown {
	const match = options.find((o) => String(o.value) === raw);
	if (match) {
		const value = match.value;
		if (baseType === "number" || baseType === "integer") {
			const n = Number(value);
			return Number.isNaN(n) ? value : n;
		}
		return value;
	}
	if (baseType === "number" || baseType === "integer") {
		const n = Number(raw);
		return Number.isNaN(n) ? undefined : n;
	}
	return raw;
}

// Default set of Vietnamese districts used by the ``district-picker`` widget.
// Renderers may override via ``x-ui.options``; this keeps one single renderer.
export const DEFAULT_DISTRICT_OPTIONS: SchemaUiOption[] = [
	{ label: "Quận 1", value: "quan_1" },
	{ label: "Quận 2", value: "quan_2" },
	{ label: "Quận 3", value: "quan_3" },
	{ label: "Quận 4", value: "quan_4" },
	{ label: "Quận 5", value: "quan_5" },
	{ label: "Quận 7", value: "quan_7" },
	{ label: "Quận Bình Thạnh", value: "binh_thanh" },
	{ label: "Quận Phú Nhuận", value: "phu_nhuan" },
	{ label: "Quận Tân Bình", value: "tan_binh" },
	{ label: "Thủ Đức", value: "thu_duc" },
];

export function deepEqual(a: unknown, b: unknown): boolean {
	if (a === b) return true;
	if (typeof a !== typeof b) return false;
	if (a === null || b === null) return a === b;
	if (typeof a !== "object") return false;
	if (Array.isArray(a) !== Array.isArray(b)) return false;

	if (Array.isArray(a)) {
		if (a.length !== (b as unknown[]).length) return false;
		return a.every((v, i) => deepEqual(v, (b as unknown[])[i]));
	}

	const aKeys = Object.keys(a as Record<string, unknown>);
	const bKeys = Object.keys(b as Record<string, unknown>);
	if (aKeys.length !== bKeys.length) return false;
	return aKeys.every((k) =>
		deepEqual((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k])
	);
}
