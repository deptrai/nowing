/**
 * Runnable self-check for per-platform URL hints (Story 2.9 AC-4).
 * No test framework — run with: `npx tsx lib/playground/url-hints.selfcheck.ts`
 * Exits non-zero on the first failed assertion.
 *
 * RED PHASE: this file fails to run (module "./url-hints" does not exist yet)
 * until Story 2.9 is implemented.
 */
import assert from "node:assert/strict";
import { urlFieldWarning } from "./url-hints";

// Host mismatch with the platform -> a non-empty warning string.
assert.equal(typeof urlFieldWarning("reddit", "urls", "https://example.com"), "string");

// Host matches the platform -> no warning.
assert.equal(
	urlFieldWarning("youtube", "urls", "https://www.youtube.com/watch?v=abc123"),
	undefined
);

// Instagram urls accept bare handles -> never warn.
assert.equal(urlFieldWarning("instagram", "urls", "@natgeo"), undefined);
assert.equal(urlFieldWarning("instagram", "urls", "https://www.instagram.com/natgeo/"), undefined);

// Unknown platform or unknown field -> no false positives.
assert.equal(urlFieldWarning("unknown-platform", "urls", "https://example.com"), undefined);
assert.equal(urlFieldWarning("reddit", "search_queries", "https://example.com"), undefined);

// Amazon EU TLDs are allowed -> no warning for amazon.de / amazon.co.uk.
assert.equal(urlFieldWarning("amazon", "urls", "https://www.amazon.de/dp/B09V3KXJPB"), undefined);
assert.equal(
	urlFieldWarning("amazon", "urls", "https://www.amazon.co.uk/dp/B09V3KXJPB"),
	undefined
);

// Unparseable value -> tryGetHostname returns undefined -> no warning, no crash.
assert.equal(urlFieldWarning("reddit", "urls", "not a url"), undefined);

// Empty string value -> no warning.
assert.equal(urlFieldWarning("reddit", "urls", ""), undefined);

console.log("url-hints.selfcheck: all assertions passed");
