import { z } from "zod";
import type { JSONSchema, SchemaUiHints } from "@/contracts/types/schema-ui.types";
import { fieldLabel, optionsFromSchema } from "./utils";

// Zod's accepted literal values: string, number, bigint, boolean, null, undefined.
type Literal = string | number | bigint | boolean | null | undefined;

export function jsonSchemaToZod(
	schema: JSONSchema,
	isRequired = true,
	name = "",
	parentUi?: SchemaUiHints
): z.ZodType {
	const resolved = resolveSchema(schema);
	const baseSchema = resolved.schema;
	const ui = schema["x-ui"] ?? parentUi;
	const label = fieldLabel(schema, name);

	let base = buildBaseZod(baseSchema, name, label, ui);

	if (resolved.nullable) {
		base = base.nullable();
	}

	if (!isRequired || schema.default !== undefined) {
		base = base.optional();
	}

	if (schema.default !== undefined) {
		base = base.default(schema.default);
	}

	return base;
}

function resolveSchema(schema: JSONSchema): { schema: JSONSchema; nullable: boolean } {
	if (schema.anyOf && Array.isArray(schema.anyOf)) {
		const nullBranch = schema.anyOf.find(
			(b) =>
				b.type === "null" || (Array.isArray(b.enum) && b.enum.length === 1 && b.enum[0] === null)
		);
		const realBranch = schema.anyOf.find(
			(b) =>
				b.type !== "null" && !(Array.isArray(b.enum) && b.enum.length === 1 && b.enum[0] === null)
		);
		if (realBranch) {
			return { schema: realBranch, nullable: !!nullBranch };
		}
	}
	return { schema, nullable: false };
}

function buildBaseZod(
	schema: JSONSchema,
	name: string,
	label: string,
	ui?: SchemaUiHints
): z.ZodType {
	const options = optionsFromSchema(schema);
	const widget = ui?.widget;

	if (schema.type === "object" || (schema.type === undefined && schema.properties)) {
		const shape: Record<string, z.ZodType> = {};
		const required = new Set(schema.required ?? []);
		for (const [key, prop] of Object.entries(schema.properties ?? {})) {
			shape[key] = jsonSchemaToZod(prop, required.has(key), key);
		}
		if (schema.additionalProperties === false) {
			return z.object(shape);
		}
		return z.object(shape).passthrough();
	}

	if (schema.type === "array" || (schema.type === undefined && schema.items)) {
		const itemSchema = schema.items ?? { type: "string" };
		return z.array(jsonSchemaToZod(itemSchema, true, `${name}[]`));
	}

	if (schema.type === "boolean") {
		return z.boolean();
	}

	if (schema.type === "number" || schema.type === "integer") {
		let base: z.ZodNumber = schema.type === "integer" ? z.number().int() : z.number();
		if (schema.minimum !== undefined) {
			base = base.min(schema.minimum);
		}
		if (schema.maximum !== undefined) {
			base = base.max(schema.maximum);
		}
		return base;
	}

	if (
		schema.type === "string" ||
		(schema.type === undefined &&
			(schema.enum ||
				schema.const !== undefined ||
				options.length > 0 ||
				widget === "district-picker"))
	) {
		if (schema.const !== undefined) {
			return z.literal(schema.const as Literal);
		}

		if (options.length > 0) {
			return optionsUnion(options, label);
		}

		if (schema.enum) {
			return enumUnion(schema.enum, label);
		}

		let base = z.string();
		if (schema.minLength === 1) {
			base = base.min(1, `${label} is required`);
		} else if (schema.minLength !== undefined && schema.minLength > 1) {
			base = base.min(schema.minLength);
		}
		if (schema.maxLength !== undefined) {
			base = base.max(schema.maxLength);
		}
		return base;
	}

	if (schema.enum) {
		return enumUnion(schema.enum, label);
	}

	// Fallback: accept anything we do not know how to validate.
	return z.any();
}

function optionsUnion(options: { label: string; value: unknown }[], _label: string): z.ZodType {
	const values = options.map((o) => o.value as Literal);
	if (values.length === 1) {
		return z.literal(values[0]);
	}
	const literals = values.map((v) => z.literal(v));
	return z.union(literals as unknown as [z.ZodType, z.ZodType, ...z.ZodType[]]);
}

function enumUnion(values: unknown[], _label: string): z.ZodType {
	if (values.length === 0) {
		return z.string();
	}
	if (values.length === 1) {
		return z.literal(values[0] as Literal);
	}
	if (values.every((v): v is string => typeof v === "string")) {
		return z.enum(values as [string, ...string[]]);
	}
	const literals = values.map((v) => z.literal(v as Literal));
	return z.union(literals as unknown as [z.ZodType, z.ZodType, ...z.ZodType[]]);
}
