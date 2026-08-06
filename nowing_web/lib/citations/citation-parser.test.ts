import assert from "node:assert";
import { parseTextWithCitations } from "./citation-parser";

const urlMap = new Map<string, string>();

// run_<uuid> parses to a run token.
{
	const text = "Result from scraper [citation:run_550e8400-e29b-41d4-a716-446655440000].";
	const segments = parseTextWithCitations(text, urlMap);
	assert.strictEqual(segments.length, 3);
	assert.strictEqual(typeof segments[0], "string");
	assert.deepStrictEqual(segments[1], {
		kind: "run",
		runId: "run_550e8400-e29b-41d4-a716-446655440000",
	});
	assert.strictEqual(typeof segments[2], "string");
	console.log("✓ run_<uuid> parses to a run token");
}

// run_ handles do not collide with numeric chunk citations.
{
	const text = "Chunk [citation:42] and run [citation:run_550e8400-e29b-41d4-a716-446655440000].";
	const segments = parseTextWithCitations(text, urlMap);
	const tokens = segments.filter((s) => typeof s !== "string");
	assert.strictEqual(tokens.length, 2);
	assert.deepStrictEqual(tokens[0], { kind: "chunk", chunkId: 42, isDocsChunk: false });
	assert.deepStrictEqual(tokens[1], {
		kind: "run",
		runId: "run_550e8400-e29b-41d4-a716-446655440000",
	});
	console.log("✓ run_ handles do not collide with numeric chunk citations");
}

// Chinese brackets and ZWSP work for run handles.
{
	const text = "Run【citation: run_550e8400-e29b-41d4-a716-446655440000 \u200b】";
	const segments = parseTextWithCitations(text, urlMap);
	const tokens = segments.filter((s) => typeof s !== "string");
	assert.strictEqual(tokens.length, 1);
	assert.deepStrictEqual(tokens[0], {
		kind: "run",
		runId: "run_550e8400-e29b-41d4-a716-446655440000",
	});
	console.log("✓ Chinese brackets and ZWSP work for run handles");
}

console.log("All citation-parser tests passed.");
