/**
 * Focused non-Playwright check for Story 3.14 (D9): every new-write automation
 * definition the builder produces must declare ``schema_version: "1.1"``, never
 * the legacy ``"1.0"``. Run directly with ``tsx`` — the package has no unit-test
 * script (see story Dev Notes, "Exact validation commands").
 */

import assert from "node:assert/strict";
import {
	buildCreatePayload,
	buildUpdatePayload,
	createEmptyForm,
} from "@/lib/automations/builder-schema";

function formWithTask() {
	const form = createEmptyForm();
	form.name = "Weekly digest";
	form.tasks[0].query = "Summarize the week and send it to Slack.";
	return form;
}

function testBuildCreatePayloadEmitsSchemaVersion11() {
	const payload = buildCreatePayload(formWithTask(), 42);
	assert.equal(payload.definition.schema_version, "1.1");
}

function testBuildUpdatePayloadEmitsSchemaVersion11() {
	const payload = buildUpdatePayload(formWithTask());
	assert.ok(payload.definition, "buildUpdatePayload must always set definition");
	assert.equal(payload.definition.schema_version, "1.1");
}

testBuildCreatePayloadEmitsSchemaVersion11();
testBuildUpdatePayloadEmitsSchemaVersion11();

console.log("builder-schema.test.ts: all assertions passed");
