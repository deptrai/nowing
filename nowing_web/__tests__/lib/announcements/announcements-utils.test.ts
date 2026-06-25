/**
 * Unit tests — lib/announcements/announcements-utils.ts
 * Covers: isAnnouncementActive, announcementMatchesAudience,
 *         getActiveAnnouncements, msUntilNextTransition
 * Priority: P1
 */
import { describe, it, expect } from "vitest";
import {
	isAnnouncementActive,
	announcementMatchesAudience,
	getActiveAnnouncements,
	msUntilNextTransition,
} from "@/lib/announcements/announcements-utils";
import type { Announcement } from "@/contracts/types/announcement.types";

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function makeAnnouncement(overrides: Partial<Announcement> = {}): Announcement {
	return {
		id: "ann-1",
		title: "Test",
		description: "desc",
		category: "info",
		date: "2026-01-01T00:00:00Z",
		startTime: "2026-01-01T00:00:00Z",
		endTime: "2026-12-31T23:59:59Z",
		audience: "all",
		isImportant: false,
		...overrides,
	};
}

const NOW = new Date("2026-06-15T12:00:00Z");

// -----------------------------------------------------------------------
// isAnnouncementActive
// -----------------------------------------------------------------------

describe("isAnnouncementActive", () => {
	it("returns true when now is within [startTime, endTime]", () => {
		const a = makeAnnouncement({
			startTime: "2026-01-01T00:00:00Z",
			endTime: "2026-12-31T23:59:59Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(true);
	});

	it("returns false when now is before startTime", () => {
		const a = makeAnnouncement({
			startTime: "2026-07-01T00:00:00Z",
			endTime: "2026-12-31T23:59:59Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(false);
	});

	it("returns false when now is after endTime", () => {
		const a = makeAnnouncement({
			startTime: "2026-01-01T00:00:00Z",
			endTime: "2026-05-01T00:00:00Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(false);
	});

	it("returns false when endTime is before startTime (invalid window)", () => {
		const a = makeAnnouncement({
			startTime: "2026-12-31T23:59:59Z",
			endTime: "2026-01-01T00:00:00Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(false);
	});

	it("returns false when startTime is invalid date string", () => {
		const a = makeAnnouncement({ startTime: "not-a-date" });
		expect(isAnnouncementActive(a, NOW)).toBe(false);
	});

	it("returns false when endTime is invalid date string", () => {
		const a = makeAnnouncement({ endTime: "not-a-date" });
		expect(isAnnouncementActive(a, NOW)).toBe(false);
	});

	it("returns true when now equals startTime exactly", () => {
		const a = makeAnnouncement({
			startTime: "2026-06-15T12:00:00Z",
			endTime: "2026-12-31T23:59:59Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(true);
	});

	it("returns true when now equals endTime exactly", () => {
		const a = makeAnnouncement({
			startTime: "2026-01-01T00:00:00Z",
			endTime: "2026-06-15T12:00:00Z",
		});
		expect(isAnnouncementActive(a, NOW)).toBe(true);
	});
});

// -----------------------------------------------------------------------
// announcementMatchesAudience
// -----------------------------------------------------------------------

describe("announcementMatchesAudience", () => {
	it("audience='all' → matches authenticated users", () => {
		const a = makeAnnouncement({ audience: "all" });
		expect(announcementMatchesAudience(a, true)).toBe(true);
	});

	it("audience='all' → matches unauthenticated visitors", () => {
		const a = makeAnnouncement({ audience: "all" });
		expect(announcementMatchesAudience(a, false)).toBe(true);
	});

	it("audience='users' → matches authenticated users only", () => {
		const a = makeAnnouncement({ audience: "users" });
		expect(announcementMatchesAudience(a, true)).toBe(true);
		expect(announcementMatchesAudience(a, false)).toBe(false);
	});

	it("audience='web_visitors' → matches unauthenticated visitors only", () => {
		const a = makeAnnouncement({ audience: "web_visitors" });
		expect(announcementMatchesAudience(a, false)).toBe(true);
		expect(announcementMatchesAudience(a, true)).toBe(false);
	});

	it("unknown audience → returns false", () => {
		const a = makeAnnouncement({ audience: "unknown" as never });
		expect(announcementMatchesAudience(a, true)).toBe(false);
		expect(announcementMatchesAudience(a, false)).toBe(false);
	});
});

// -----------------------------------------------------------------------
// getActiveAnnouncements
// -----------------------------------------------------------------------

describe("getActiveAnnouncements", () => {
	const active = makeAnnouncement({
		id: "active",
		startTime: "2026-01-01T00:00:00Z",
		endTime: "2026-12-31T23:59:59Z",
		audience: "all",
	});
	const expired = makeAnnouncement({
		id: "expired",
		startTime: "2026-01-01T00:00:00Z",
		endTime: "2026-05-01T00:00:00Z",
		audience: "all",
	});
	const usersOnly = makeAnnouncement({
		id: "users-only",
		startTime: "2026-01-01T00:00:00Z",
		endTime: "2026-12-31T23:59:59Z",
		audience: "users",
	});

	it("returns only active announcements matching audience", () => {
		const result = getActiveAnnouncements([active, expired, usersOnly], true, NOW);
		expect(result.map((a) => a.id)).toEqual(["active", "users-only"]);
	});

	it("filters out audience-mismatch for unauthenticated user", () => {
		const result = getActiveAnnouncements([active, usersOnly], false, NOW);
		expect(result.map((a) => a.id)).toEqual(["active"]);
	});

	it("returns empty array when no announcements match", () => {
		expect(getActiveAnnouncements([expired], true, NOW)).toEqual([]);
	});

	it("returns empty array for empty input", () => {
		expect(getActiveAnnouncements([], true, NOW)).toEqual([]);
	});
});

// -----------------------------------------------------------------------
// msUntilNextTransition
// -----------------------------------------------------------------------

describe("msUntilNextTransition", () => {
	it("returns ms until upcoming startTime", () => {
		const futureStart = new Date(NOW.getTime() + 5_000);
		const a = makeAnnouncement({
			startTime: futureStart.toISOString(),
			endTime: new Date(NOW.getTime() + 10_000).toISOString(),
		});
		const result = msUntilNextTransition([a], NOW);
		expect(result).toBe(5_000);
	});

	it("returns ms until upcoming endTime (sooner of two)", () => {
		const a = makeAnnouncement({
			startTime: "2026-01-01T00:00:00Z", // past
			endTime: new Date(NOW.getTime() + 3_000).toISOString(),
		});
		const result = msUntilNextTransition([a], NOW);
		expect(result).toBe(3_000);
	});

	it("returns the nearest transition across multiple announcements", () => {
		const a1 = makeAnnouncement({
			id: "a1",
			startTime: new Date(NOW.getTime() + 10_000).toISOString(),
			endTime: new Date(NOW.getTime() + 20_000).toISOString(),
		});
		const a2 = makeAnnouncement({
			id: "a2",
			startTime: new Date(NOW.getTime() + 2_000).toISOString(),
			endTime: new Date(NOW.getTime() + 30_000).toISOString(),
		});
		const result = msUntilNextTransition([a1, a2], NOW);
		expect(result).toBe(2_000);
	});

	it("returns null when all announcements are in the past", () => {
		const a = makeAnnouncement({
			startTime: "2026-01-01T00:00:00Z",
			endTime: "2026-05-01T00:00:00Z",
		});
		expect(msUntilNextTransition([a], NOW)).toBeNull();
	});

	it("returns null for empty array", () => {
		expect(msUntilNextTransition([], NOW)).toBeNull();
	});

	it("skips announcements with invalid dates", () => {
		const a = makeAnnouncement({ startTime: "bad-date", endTime: "also-bad" });
		expect(msUntilNextTransition([a], NOW)).toBeNull();
	});
});
