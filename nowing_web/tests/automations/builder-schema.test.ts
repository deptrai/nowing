/**
 * Focused non-Playwright check for Story 3.14 (D9): every new-write automation
 * definition the builder produces must declare ``schema_version: "1.1"``, never
 * the legacy ``"1.0"``. Run directly with ``tsx`` — the package has no unit-test
 * script (see story Dev Notes, "Exact validation commands").
 */

import assert from "node:assert/strict";
import type { Automation } from "@/contracts/types/automation.types";
import {
	buildCreatePayload,
	buildUpdatePayload,
	createEmptyForm,
	formFromAutomation,
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

function testTelegramRoundTrip() {
	const form = createEmptyForm();
	form.name = "Telegram alert";
	form.tasks = [
		{
			id: "task-1",
			action: "write_back_telegram",
			query: "",
			mentions: [],
			writeBackParams: {
				provider: "telegram",
				text: "Hello from automation",
				chat_id: "12345",
				parse_mode: "Markdown",
				reply_markup: { inline_keyboard: [[{ text: "Open", url: "https://nowing.net" }]] },
				account_id: null,
				use_system_bot: true,
				reply_to_message_id: null,
				connector_name: null,
				object_id: null,
			},
			maxRetries: null,
			timeoutSeconds: null,
		},
	];

	const payload = buildCreatePayload(form, 42);
	const step = payload.definition.plan[0];
	assert.equal(step.action, "write_back_telegram");
	assert.equal(step.params.text, "Hello from automation");
	assert.equal(step.params.chat_id, "12345");
	assert.equal(step.params.parse_mode, "Markdown");
	assert.deepEqual(step.params.reply_markup, {
		inline_keyboard: [[{ text: "Open", url: "https://nowing.net" }]],
	});
	assert.equal(step.params.provider, undefined);

	const automation: Automation = {
		id: 1,
		workspace_id: 42,
		name: payload.name,
		description: payload.description,
		status: "active",
		version: 1,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
		definition: payload.definition,
		triggers: payload.triggers as Automation["triggers"],
	};

	const hydrated = formFromAutomation(automation);
	assert.equal(hydrated.formable, true);
	assert.equal(hydrated.form.tasks[0].action, "write_back_telegram");
	assert.equal(hydrated.form.tasks[0].writeBackParams?.provider, "telegram");
	assert.equal(hydrated.form.tasks[0].writeBackParams?.text, "Hello from automation");
	assert.equal(hydrated.form.tasks[0].writeBackParams?.chat_id, "12345");
	assert.equal(hydrated.form.tasks[0].writeBackParams?.parse_mode, "Markdown");
}

function testTelegramNoneParseMode() {
	const form = createEmptyForm();
	form.name = "Telegram plain";
	form.tasks = [
		{
			id: "task-1",
			action: "write_back_telegram",
			query: "",
			mentions: [],
			writeBackParams: {
				provider: "telegram",
				text: "plain text",
				chat_id: null,
				parse_mode: null,
				reply_markup: null,
				account_id: null,
				use_system_bot: true,
				reply_to_message_id: null,
				connector_name: null,
				object_id: null,
			},
			maxRetries: null,
			timeoutSeconds: null,
		},
	];

	const payload = buildCreatePayload(form, 42);
	assert.equal(payload.definition.plan[0].params.parse_mode, null);
}

testTelegramRoundTrip();
testTelegramNoneParseMode();

console.log("builder-schema.test.ts: all assertions passed");
