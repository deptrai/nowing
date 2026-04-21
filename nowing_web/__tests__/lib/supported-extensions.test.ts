/**
 * Unit tests — lib/supported-extensions.ts
 * Covers: getSupportedExtensions, getSupportedExtensionsSet
 * Priority: P1
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
	getSupportedExtensions,
	getSupportedExtensionsSet,
	getAcceptedFileTypes,
} from "@/lib/supported-extensions";

// -----------------------------------------------------------------------
// getSupportedExtensions
// -----------------------------------------------------------------------

describe("getSupportedExtensions", () => {
	it("returns a sorted array of unique extensions", () => {
		const exts = getSupportedExtensions();
		expect(Array.isArray(exts)).toBe(true);
		expect(exts.length).toBeGreaterThan(0);
	});

	it("extensions are sorted alphabetically", () => {
		const exts = getSupportedExtensions();
		const sorted = [...exts].sort();
		expect(exts).toEqual(sorted);
	});

	it("extensions are unique (no duplicates)", () => {
		const exts = getSupportedExtensions();
		expect(new Set(exts).size).toBe(exts.length);
	});

	it("includes common extensions like .pdf and .docx", () => {
		const exts = getSupportedExtensions();
		expect(exts).toContain(".pdf");
		expect(exts).toContain(".docx");
	});

	it("includes image extensions", () => {
		const exts = getSupportedExtensions();
		expect(exts).toContain(".jpg");
		expect(exts).toContain(".png");
	});

	it("accepts custom fileTypes map", () => {
		const custom = { "text/plain": [".txt", ".log"] };
		const exts = getSupportedExtensions(custom);
		expect(exts).toContain(".txt");
		expect(exts).toContain(".log");
		expect(exts).not.toContain(".pdf");
	});
});

// -----------------------------------------------------------------------
// getSupportedExtensionsSet
// -----------------------------------------------------------------------

describe("getSupportedExtensionsSet", () => {
	it("returns a Set", () => {
		expect(getSupportedExtensionsSet()).toBeInstanceOf(Set);
	});

	it("contains lowercase extensions", () => {
		const set = getSupportedExtensionsSet();
		expect(set.has(".pdf")).toBe(true);
		expect(set.has(".PNG")).toBe(false); // lowercased
		expect(set.has(".png")).toBe(true);
	});

	it("accepts custom fileTypes map", () => {
		const custom = { "text/plain": [".TXT"] };
		const set = getSupportedExtensionsSet(custom);
		expect(set.has(".txt")).toBe(true); // lowercased
	});
});

// -----------------------------------------------------------------------
// getAcceptedFileTypes — env-driven selection
// -----------------------------------------------------------------------

describe("getAcceptedFileTypes", () => {
	const originalEnv = process.env.NEXT_PUBLIC_ETL_SERVICE;

	afterEach(() => {
		process.env.NEXT_PUBLIC_ETL_SERVICE = originalEnv;
	});

	it("returns default config when NEXT_PUBLIC_ETL_SERVICE is unset", () => {
		delete process.env.NEXT_PUBLIC_ETL_SERVICE;
		const types = getAcceptedFileTypes();
		expect(types).toHaveProperty("application/pdf");
	});

	it("returns LLAMACLOUD config when env is LLAMACLOUD", () => {
		process.env.NEXT_PUBLIC_ETL_SERVICE = "LLAMACLOUD";
		const types = getAcceptedFileTypes();
		expect(types).toHaveProperty("application/pdf");
		// LLAMACLOUD has extra types like epub
		expect(types).toHaveProperty("application/epub+zip");
	});

	it("returns DOCLING config when env is DOCLING", () => {
		process.env.NEXT_PUBLIC_ETL_SERVICE = "DOCLING";
		const types = getAcceptedFileTypes();
		expect(types).toHaveProperty("application/pdf");
	});

	it("falls back to default for unknown ETL service", () => {
		process.env.NEXT_PUBLIC_ETL_SERVICE = "UNKNOWN_SERVICE";
		const types = getAcceptedFileTypes();
		expect(types).toHaveProperty("application/pdf");
	});
});
