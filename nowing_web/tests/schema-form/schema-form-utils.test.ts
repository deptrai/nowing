import assert from "node:assert/strict";
import type { JSONSchema } from "@/contracts/types/schema-ui.types";
import { buildDefaultValues } from "@/lib/schema-form/build-default-values";
import { jsonSchemaToZod } from "@/lib/schema-form/json-schema-to-zod";

function testBuildDefaultValuesAnyOf() {
	const schema: JSONSchema = {
		type: "object",
		properties: {
			title: {
				type: "string",
				description: "Page title",
			},
			parent_id: {
				anyOf: [{ type: "string" }, { type: "null" }],
				description: "Parent page id",
			},
			channel: {
				anyOf: [{ type: "string" }, { type: "null" }],
				default: null,
			},
		},
		required: ["title"],
	};

	const defaults = buildDefaultValues(schema);
	assert.equal(defaults.title, "");
	assert.equal(defaults.parent_id, null);
	assert.equal(defaults.channel, null);
}

function testJsonSchemaToZodAnyOfNull() {
	const schema: JSONSchema = {
		type: "object",
		properties: {
			text: { type: "string", minLength: 1 },
			chat_id: {
				anyOf: [{ type: "string" }, { type: "null" }],
			},
		},
		required: ["text"],
	};

	const zodSchema = jsonSchemaToZod(schema);
	const valid = zodSchema.safeParse({ text: "hello", chat_id: "123" });
	assert.equal(valid.success, true);

	const withNull = zodSchema.safeParse({ text: "hello", chat_id: null });
	assert.equal(withNull.success, true);

	const invalid = zodSchema.safeParse({ text: "" });
	assert.equal(invalid.success, false);
}

function testJsonSchemaToZodEnum() {
	const schema: JSONSchema = {
		type: "string",
		enum: ["Markdown", "MarkdownV2", null],
	};

	const zodSchema = jsonSchemaToZod(schema);
	const valid = zodSchema.safeParse("Markdown");
	assert.equal(valid.success, true);

	const nullValid = zodSchema.safeParse(null);
	assert.equal(nullValid.success, true);

	const invalid = zodSchema.safeParse("HTML");
	assert.equal(invalid.success, false);
}

function testJsonSchemaToZodOptions() {
	const schema: JSONSchema = {
		type: "string",
		"x-ui": {
			widget: "select",
			options: [
				{ label: "A", value: "a" },
				{ label: "B", value: "b" },
			],
		},
	};

	const zodSchema = jsonSchemaToZod(schema);
	assert.equal(zodSchema.safeParse("a").success, true);
	assert.equal(zodSchema.safeParse("c").success, false);
}

testBuildDefaultValuesAnyOf();
testJsonSchemaToZodAnyOfNull();
testJsonSchemaToZodEnum();
testJsonSchemaToZodOptions();

console.log("schema-form-utils.test.ts: all assertions passed");
