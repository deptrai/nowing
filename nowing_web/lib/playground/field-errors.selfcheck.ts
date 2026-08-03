/**
 * Runnable self-check for 422 field-error mapping (Story 2.9 AC-3).
 * No test framework — run with: `npx tsx lib/playground/field-errors.selfcheck.ts`
 * Exits non-zero on the first failed assertion.
 *
 * RED PHASE: this file fails to run (module "./field-errors" does not exist yet)
 * until Story 2.9 is implemented.
 */
import assert from "node:assert/strict";
import type { AppError } from "../error";
import { fieldErrorsFromError } from "./field-errors";

type LocError = { loc: (string | number)[]; msg: string };

function errWithFields(fields: LocError[] | undefined): AppError {
	return {
		name: "ValidationError",
		message: "Validation failed.",
		status: 422,
		statusText: "Unprocessable Entity",
		code: "VALIDATION_ERROR",
		fields,
	} as unknown as AppError;
}

// Full backend loc ["body","urls",0] maps to the top-level field name "urls".
assert.deepEqual(
	fieldErrorsFromError(
		errWithFields([{ loc: ["body", "urls", 0], msg: "must be a valid http(s) URL" }])
	),
	{ urls: "must be a valid http(s) URL" }
);

// camelCase / snake_case field names map to their own top-level name.
assert.deepEqual(
	fieldErrorsFromError(errWithFields([{ loc: ["body", "video_urls", 0], msg: "bad video" }])),
	{ video_urls: "bad video" }
);
assert.deepEqual(
	fieldErrorsFromError(errWithFields([{ loc: ["body", "startUrls", 0], msg: "bad seed" }])),
	{ startUrls: "bad seed" }
);

// First failure per field wins; a later failure in the same field is dropped.
assert.deepEqual(
	fieldErrorsFromError(
		errWithFields([
			{ loc: ["body", "urls", 0], msg: "first" },
			{ loc: ["body", "urls", 2], msg: "second" },
		])
	),
	{ urls: "first" }
);

// 3 invalid URLs in one submit -> all 3 fields get one inline error each.
assert.deepEqual(
	fieldErrorsFromError(
		errWithFields([
			{ loc: ["body", "urls", 0], msg: "a" },
			{ loc: ["body", "video_urls", 0], msg: "b" },
			{ loc: ["body", "startUrls", 0], msg: "c" },
		])
	),
	{ urls: "a", video_urls: "b", startUrls: "c" }
);

// Loc path that cannot be mapped to a field -> no entry (toast fallback).
assert.deepEqual(fieldErrorsFromError(errWithFields([{ loc: ["query", "q"], msg: "bad" }])), {});

// Empty fields array -> treated as no inline errors.
assert.deepEqual(fieldErrorsFromError(errWithFields([])), {});

// Legacy envelope: plain AppError WITHOUT fields -> {} (toast path, no crash).
assert.deepEqual(
	fieldErrorsFromError({ name: "AppError", message: "boom", status: 500 } as unknown as AppError),
	{}
);

// Null/undefined error -> no crash.
assert.deepEqual(fieldErrorsFromError(null as unknown as AppError), {});
assert.deepEqual(fieldErrorsFromError(undefined as unknown as AppError), {});

console.log("field-errors.selfcheck: all assertions passed");
