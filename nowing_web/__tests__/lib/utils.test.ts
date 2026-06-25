/**
 * Unit tests — lib/utils.ts
 * Covers: cn, formatDate, copyToClipboard
 * Priority: P1
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { cn, formatDate, copyToClipboard } from "@/lib/utils";

// -----------------------------------------------------------------------
// cn — className merger
// -----------------------------------------------------------------------

describe("cn", () => {
	it("merges class names", () => {
		expect(cn("foo", "bar")).toBe("foo bar");
	});

	it("deduplicates tailwind classes (twMerge)", () => {
		expect(cn("p-2", "p-4")).toBe("p-4");
	});

	it("handles conditional classes with clsx", () => {
		expect(cn("base", false && "hidden", "active")).toBe("base active");
	});

	it("handles undefined and null gracefully", () => {
		expect(cn("a", undefined, null, "b")).toBe("a b");
	});

	it("handles object syntax", () => {
		expect(cn({ foo: true, bar: false })).toBe("foo");
	});

	it("returns empty string for no args", () => {
		expect(cn()).toBe("");
	});
});

// -----------------------------------------------------------------------
// formatDate
// -----------------------------------------------------------------------

describe("formatDate", () => {
	it("formats a date as 'Month Day, Year'", () => {
		expect(formatDate(new Date("2026-01-15T00:00:00Z"))).toMatch(/January 15, 2026/);
	});

	it("returns a string", () => {
		expect(typeof formatDate(new Date())).toBe("string");
	});
});

// -----------------------------------------------------------------------
// copyToClipboard
// -----------------------------------------------------------------------

describe("copyToClipboard — Clipboard API", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("returns true when Clipboard API succeeds", async () => {
		Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
		Object.defineProperty(navigator, "clipboard", {
			configurable: true,
			value: { writeText: vi.fn().mockResolvedValue(undefined) },
		});

		const result = await copyToClipboard("hello");
		expect(result).toBe(true);
		expect(navigator.clipboard.writeText).toHaveBeenCalledWith("hello");
	});

	it("returns false when Clipboard API throws", async () => {
		Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
		Object.defineProperty(navigator, "clipboard", {
			configurable: true,
			value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
		});

		const result = await copyToClipboard("hello");
		expect(result).toBe(false);
	});
});

describe("copyToClipboard — execCommand fallback", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		// Force fallback path: no Clipboard API
		Object.defineProperty(navigator, "clipboard", {
			configurable: true,
			value: undefined,
		});
		Object.defineProperty(window, "isSecureContext", { value: false, configurable: true });
		// jsdom doesn't implement execCommand — define it so we can spy
		if (!document.execCommand) {
			document.execCommand = () => false;
		}
	});

	it("returns true when execCommand succeeds", async () => {
		vi.spyOn(document, "execCommand").mockReturnValue(true);

		const result = await copyToClipboard("fallback text");
		expect(result).toBe(true);
	});

	it("returns false when execCommand returns false", async () => {
		vi.spyOn(document, "execCommand").mockReturnValue(false);

		const result = await copyToClipboard("fallback text");
		expect(result).toBe(false);
	});

	it("returns false when execCommand throws", async () => {
		vi.spyOn(document, "execCommand").mockImplementation(() => {
			throw new Error("execCommand failed");
		});

		const result = await copyToClipboard("fallback text");
		expect(result).toBe(false);
	});
});
