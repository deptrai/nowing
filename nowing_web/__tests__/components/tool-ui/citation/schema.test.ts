/**
 * Unit tests — components/tool-ui/citation/schema.ts
 * Covers: CitationTypeSchema, CitationVariantSchema, SerializableCitationSchema,
 *         detectConflict, CONFLICT_NUMERIC_DELTA
 */
import { describe, it, expect } from "vitest";
import {
	CitationTypeSchema,
	CitationVariantSchema,
	SerializableCitationSchema,
	detectConflict,
	CONFLICT_NUMERIC_DELTA,
} from "@/components/tool-ui/citation/schema";

// ---------------------------------------------------------------------------
// Zod enum schemas
// ---------------------------------------------------------------------------

describe("CitationTypeSchema", () => {
	it.each(["webpage", "document", "article", "api", "code", "other"])("accepts '%s'", (val) => {
		expect(CitationTypeSchema.parse(val)).toBe(val);
	});

	it("rejects unknown type", () => {
		expect(() => CitationTypeSchema.parse("video")).toThrow();
	});
});

describe("CitationVariantSchema", () => {
	it.each(["default", "inline", "stacked", "cluster", "conflict"])("accepts '%s'", (val) => {
		expect(CitationVariantSchema.parse(val)).toBe(val);
	});

	it("rejects unknown variant", () => {
		expect(() => CitationVariantSchema.parse("tooltip")).toThrow();
	});
});

// ---------------------------------------------------------------------------
// SerializableCitationSchema
// ---------------------------------------------------------------------------

describe("SerializableCitationSchema", () => {
	const minimal = {
		id: "cite-1",
		href: "https://example.com",
		title: "Example",
	};

	it("parses minimal valid citation", () => {
		const result = SerializableCitationSchema.parse(minimal);
		expect(result.id).toBe("cite-1");
		expect(result.href).toBe("https://example.com");
		expect(result.title).toBe("Example");
	});

	it("parses citation with all optional fields", () => {
		const full = {
			...minimal,
			role: "information",
			snippet: "Lorem ipsum",
			domain: "example.com",
			favicon: "https://example.com/icon.png",
			author: "Author",
			publishedAt: "2026-01-01T00:00:00Z",
			type: "webpage",
			locale: "en",
		};
		const result = SerializableCitationSchema.parse(full);
		expect(result.type).toBe("webpage");
		expect(result.author).toBe("Author");
	});

	it("rejects invalid href (not URL)", () => {
		expect(() => SerializableCitationSchema.parse({ ...minimal, href: "not-a-url" })).toThrow();
	});

	it("rejects missing title", () => {
		expect(() => SerializableCitationSchema.parse({ id: "x", href: "https://a.com" })).toThrow();
	});

	it("rejects missing href", () => {
		expect(() => SerializableCitationSchema.parse({ id: "x", title: "T" })).toThrow();
	});

	it("rejects invalid publishedAt (not datetime)", () => {
		expect(() =>
			SerializableCitationSchema.parse({ ...minimal, publishedAt: "not-a-date" })
		).toThrow();
	});

	it("rejects invalid favicon (not URL)", () => {
		expect(() => SerializableCitationSchema.parse({ ...minimal, favicon: "just-text" })).toThrow();
	});
});

// ---------------------------------------------------------------------------
// detectConflict
// ---------------------------------------------------------------------------

describe("detectConflict", () => {
	it("returns false for empty array", () => {
		expect(detectConflict([])).toBe(false);
	});

	it("returns false for single value", () => {
		expect(detectConflict([42])).toBe(false);
	});

	// Numeric — no conflict
	it("returns false when numeric values are within delta", () => {
		expect(detectConflict([100, 100 * (1 + CONFLICT_NUMERIC_DELTA * 0.9)])).toBe(false);
	});

	it("returns false for identical numbers", () => {
		expect(detectConflict([42, 42, 42])).toBe(false);
	});

	// Numeric — conflict
	it("returns true when numeric values exceed delta", () => {
		expect(detectConflict([100, 100 * (1 + CONFLICT_NUMERIC_DELTA * 2)])).toBe(true);
	});

	it("returns true for significantly different numbers", () => {
		expect(detectConflict([100, 200])).toBe(true);
	});

	// Numeric edge: max is 0
	it("returns true when max is 0 and min is non-zero", () => {
		expect(detectConflict([-5, 0])).toBe(true);
	});

	it("returns false when all values are 0", () => {
		expect(detectConflict([0, 0])).toBe(false);
	});

	// String — no conflict
	it("returns false for identical strings", () => {
		expect(detectConflict(["yes", "yes"])).toBe(false);
	});

	// String — conflict
	it("returns true for different strings", () => {
		expect(detectConflict(["yes", "no"])).toBe(true);
	});

	it("returns true for strings that differ in case", () => {
		expect(detectConflict(["Yes", "yes"])).toBe(true);
	});

	// Boolean — no conflict
	it("returns false for identical booleans", () => {
		expect(detectConflict([true, true])).toBe(false);
	});

	// Boolean — conflict
	it("returns true for different booleans", () => {
		expect(detectConflict([true, false])).toBe(true);
	});

	// Mixed types — treated as no-conflict per implementation (first is number but rest aren't)
	it("returns false for mixed types where first is number but others aren't", () => {
		expect(detectConflict([42, "42" as unknown as number])).toBe(false);
	});

	// NaN / Infinity
	it("returns false when any numeric value is NaN (not all finite)", () => {
		expect(detectConflict([42, NaN])).toBe(false);
	});

	it("returns false when any numeric value is Infinity", () => {
		expect(detectConflict([42, Infinity])).toBe(false);
	});
});

// ---------------------------------------------------------------------------
// CONFLICT_NUMERIC_DELTA constant
// ---------------------------------------------------------------------------

describe("CONFLICT_NUMERIC_DELTA", () => {
	it("is 5%", () => {
		expect(CONFLICT_NUMERIC_DELTA).toBe(0.05);
	});
});
