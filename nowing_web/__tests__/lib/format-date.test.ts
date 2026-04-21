/**
 * Unit tests — lib/format-date.ts
 * Covers: formatRelativeDate (all display branches)
 * Priority: P1
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { formatRelativeDate } from "@/lib/format-date";

// -----------------------------------------------------------------------
// Fake timers — pin "now" to 2026-04-21T14:30:00Z (local: depends on TZ)
// We use UTC-aware dates to avoid TZ-sensitive format assertions.
// -----------------------------------------------------------------------

const NOW_ISO = "2026-04-21T14:30:00Z";
const NOW = new Date(NOW_ISO);

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(NOW);
});

afterEach(() => {
	vi.useRealTimers();
});

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function minutesBefore(min: number): string {
	return new Date(NOW.getTime() - min * 60_000).toISOString();
}
function secondsBefore(sec: number): string {
	return new Date(NOW.getTime() - sec * 1_000).toISOString();
}
function daysBefore(days: number, hour = 14, minute = 0): string {
	const d = new Date(NOW);
	d.setUTCDate(d.getUTCDate() - days);
	d.setUTCHours(hour, minute, 0, 0);
	return d.toISOString();
}

// -----------------------------------------------------------------------
// "Just now" — < 1 minute
// -----------------------------------------------------------------------

describe('formatRelativeDate — "Just now"', () => {
	it("returns 'Just now' for 0 seconds ago", () => {
		expect(formatRelativeDate(NOW.toISOString())).toBe("Just now");
	});

	it("returns 'Just now' for 30 seconds ago", () => {
		expect(formatRelativeDate(secondsBefore(30))).toBe("Just now");
	});

	it("returns 'Just now' for 59 seconds ago", () => {
		expect(formatRelativeDate(secondsBefore(59))).toBe("Just now");
	});
});

// -----------------------------------------------------------------------
// "Xm ago" — 1–59 minutes
// -----------------------------------------------------------------------

describe('formatRelativeDate — "Xm ago"', () => {
	it("returns '1m ago' for exactly 1 minute ago", () => {
		expect(formatRelativeDate(minutesBefore(1))).toBe("1m ago");
	});

	it("returns '15m ago' for 15 minutes ago", () => {
		expect(formatRelativeDate(minutesBefore(15))).toBe("15m ago");
	});

	it("returns '59m ago' for 59 minutes ago", () => {
		expect(formatRelativeDate(minutesBefore(59))).toBe("59m ago");
	});
});

// -----------------------------------------------------------------------
// "Today, H:mm a" — same calendar day, >= 60 minutes ago
// -----------------------------------------------------------------------

describe('formatRelativeDate — "Today, …"', () => {
	it("returns 'Today, …' for 2 hours ago (same day)", () => {
		const twoHoursAgo = minutesBefore(120);
		const result = formatRelativeDate(twoHoursAgo);
		expect(result).toMatch(/^Today,/);
	});

	it("'Today' result includes formatted time", () => {
		const result = formatRelativeDate(minutesBefore(90));
		expect(result).toMatch(/Today, \d+:\d{2} (AM|PM)/i);
	});
});

// -----------------------------------------------------------------------
// "Yesterday, H:mm a"
// -----------------------------------------------------------------------

describe('formatRelativeDate — "Yesterday, …"', () => {
	it("returns 'Yesterday, …' for a date yesterday", () => {
		const result = formatRelativeDate(daysBefore(1));
		expect(result).toMatch(/^Yesterday,/);
	});

	it("'Yesterday' result includes formatted time", () => {
		const result = formatRelativeDate(daysBefore(1, 10, 15));
		expect(result).toMatch(/Yesterday, \d+:\d{2} (AM|PM)/i);
	});
});

// -----------------------------------------------------------------------
// "Xd ago" — 2–6 days ago
// -----------------------------------------------------------------------

describe('formatRelativeDate — "Xd ago"', () => {
	it("returns '2d ago' for 2 days ago", () => {
		expect(formatRelativeDate(daysBefore(2))).toBe("2d ago");
	});

	it("returns '6d ago' for 6 days ago", () => {
		expect(formatRelativeDate(daysBefore(6))).toBe("6d ago");
	});
});

// -----------------------------------------------------------------------
// Absolute date — >= 7 days
// -----------------------------------------------------------------------

describe("formatRelativeDate — absolute date", () => {
	it("returns 'MMM d, yyyy' format for 7 days ago", () => {
		const result = formatRelativeDate(daysBefore(7));
		// Should match e.g. "Apr 14, 2026"
		expect(result).toMatch(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/);
	});

	it("returns 'MMM d, yyyy' format for old date", () => {
		const result = formatRelativeDate("2025-01-15T10:00:00Z");
		expect(result).toBe("Jan 15, 2025");
	});

	it("returns 'MMM d, yyyy' for exactly 30 days ago", () => {
		const result = formatRelativeDate(daysBefore(30));
		expect(result).toMatch(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/);
	});
});
