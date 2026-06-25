/**
 * Unit tests — lib/announcements/announcements-storage.ts
 * Covers: getAnnouncementState, markAnnouncementRead, markAllAnnouncementsRead,
 *         markAnnouncementToasted, isAnnouncementRead, isAnnouncementToasted
 * Priority: P1
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from "vitest";
import {
	getAnnouncementState,
	markAnnouncementRead,
	markAllAnnouncementsRead,
	markAnnouncementToasted,
	isAnnouncementRead,
	isAnnouncementToasted,
} from "@/lib/announcements/announcements-storage";

const STORAGE_KEY = "nowing_announcements_state";

// -----------------------------------------------------------------------
// localStorage mock
// -----------------------------------------------------------------------

const localStorageMock = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: vi.fn((key: string) => store[key] ?? null),
		setItem: vi.fn((key: string, value: string) => {
			store[key] = value;
		}),
		removeItem: vi.fn((key: string) => {
			delete store[key];
		}),
		clear: vi.fn(() => {
			store = {};
		}),
	};
})();

let originalDescriptor: PropertyDescriptor | undefined;

beforeAll(() => {
	originalDescriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
	Object.defineProperty(globalThis, "localStorage", {
		value: localStorageMock,
		writable: true,
		configurable: true,
	});
});

afterAll(() => {
	if (originalDescriptor) {
		Object.defineProperty(globalThis, "localStorage", originalDescriptor);
	}
});

beforeEach(() => {
	localStorageMock.clear();
	localStorageMock.getItem.mockClear();
	localStorageMock.setItem.mockClear();
	localStorageMock.removeItem.mockClear();
	localStorageMock.clear.mockClear();
});

// -----------------------------------------------------------------------
// getAnnouncementState
// -----------------------------------------------------------------------

describe("getAnnouncementState", () => {
	it("returns default state when localStorage is empty", () => {
		const state = getAnnouncementState();
		expect(state).toEqual({ readIds: [], toastedIds: [] });
	});

	it("returns persisted state from localStorage", () => {
		localStorageMock.setItem(
			STORAGE_KEY,
			JSON.stringify({ readIds: ["a", "b"], toastedIds: ["c"] })
		);
		const state = getAnnouncementState();
		expect(state.readIds).toEqual(["a", "b"]);
		expect(state.toastedIds).toEqual(["c"]);
	});

	it("returns default state when JSON is malformed", () => {
		localStorageMock.setItem(STORAGE_KEY, "not-json{{");
		const state = getAnnouncementState();
		expect(state).toEqual({ readIds: [], toastedIds: [] });
	});

	it("handles legacy state missing toastedIds", () => {
		localStorageMock.setItem(STORAGE_KEY, JSON.stringify({ readIds: ["x"] }));
		const state = getAnnouncementState();
		expect(state.readIds).toEqual(["x"]);
		expect(state.toastedIds).toEqual([]);
	});

	it("handles state missing readIds", () => {
		localStorageMock.setItem(STORAGE_KEY, JSON.stringify({ toastedIds: ["y"] }));
		const state = getAnnouncementState();
		expect(state.readIds).toEqual([]);
		expect(state.toastedIds).toEqual(["y"]);
	});

	it("handles non-array readIds gracefully", () => {
		localStorageMock.setItem(STORAGE_KEY, JSON.stringify({ readIds: "bad", toastedIds: [] }));
		const state = getAnnouncementState();
		expect(state.readIds).toEqual([]);
	});
});

// -----------------------------------------------------------------------
// markAnnouncementRead
// -----------------------------------------------------------------------

describe("markAnnouncementRead", () => {
	it("adds id to readIds when not already read", () => {
		markAnnouncementRead("ann-1");
		expect(isAnnouncementRead("ann-1")).toBe(true);
	});

	it("does not duplicate id if already read", () => {
		markAnnouncementRead("ann-1");
		markAnnouncementRead("ann-1");
		const state = getAnnouncementState();
		expect(state.readIds.filter((id) => id === "ann-1")).toHaveLength(1);
	});

	it("persists to localStorage", () => {
		markAnnouncementRead("ann-2");
		expect(localStorageMock.setItem).toHaveBeenCalled();
		const raw = localStorageMock.getItem(STORAGE_KEY);
		expect(raw).not.toBeNull();
		const parsed = JSON.parse(raw!);
		expect(parsed.readIds).toContain("ann-2");
	});

	it("preserves existing readIds when adding new one", () => {
		markAnnouncementRead("ann-1");
		markAnnouncementRead("ann-2");
		const state = getAnnouncementState();
		expect(state.readIds).toContain("ann-1");
		expect(state.readIds).toContain("ann-2");
	});
});

// -----------------------------------------------------------------------
// markAllAnnouncementsRead
// -----------------------------------------------------------------------

describe("markAllAnnouncementsRead", () => {
	it("marks all provided ids as read", () => {
		markAllAnnouncementsRead(["a", "b", "c"]);
		expect(isAnnouncementRead("a")).toBe(true);
		expect(isAnnouncementRead("b")).toBe(true);
		expect(isAnnouncementRead("c")).toBe(true);
	});

	it("does not duplicate ids already read", () => {
		markAnnouncementRead("a");
		markAllAnnouncementsRead(["a", "b"]);
		const state = getAnnouncementState();
		expect(state.readIds.filter((id) => id === "a")).toHaveLength(1);
		expect(state.readIds).toContain("b");
	});

	it("does not call setItem when all ids already read", () => {
		markAnnouncementRead("a");
		const callsBefore = localStorageMock.setItem.mock.calls.length;
		markAllAnnouncementsRead(["a"]);
		// No new ids → no additional write
		expect(localStorageMock.setItem.mock.calls.length).toBe(callsBefore);
	});

	it("handles empty array input", () => {
		markAllAnnouncementsRead([]);
		expect(localStorageMock.setItem).not.toHaveBeenCalled();
	});
});

// -----------------------------------------------------------------------
// markAnnouncementToasted
// -----------------------------------------------------------------------

describe("markAnnouncementToasted", () => {
	it("adds id to toastedIds", () => {
		markAnnouncementToasted("ann-toast-1");
		expect(isAnnouncementToasted("ann-toast-1")).toBe(true);
	});

	it("does not duplicate if already toasted", () => {
		markAnnouncementToasted("ann-toast-1");
		markAnnouncementToasted("ann-toast-1");
		const state = getAnnouncementState();
		expect(state.toastedIds.filter((id) => id === "ann-toast-1")).toHaveLength(1);
	});

	it("does not affect readIds — toasted id is not marked as read", () => {
		markAnnouncementToasted("ann-toast-only");
		expect(isAnnouncementRead("ann-toast-only")).toBe(false);
		expect(isAnnouncementToasted("ann-toast-only")).toBe(true);
	});
});

// -----------------------------------------------------------------------
// isAnnouncementRead / isAnnouncementToasted
// -----------------------------------------------------------------------

describe("isAnnouncementRead", () => {
	it("returns false for unread announcement", () => {
		expect(isAnnouncementRead("not-read")).toBe(false);
	});

	it("returns true after marking as read", () => {
		markAnnouncementRead("was-read");
		expect(isAnnouncementRead("was-read")).toBe(true);
	});
});

describe("isAnnouncementToasted", () => {
	it("returns false for un-toasted announcement", () => {
		expect(isAnnouncementToasted("not-toasted")).toBe(false);
	});

	it("returns true after marking as toasted", () => {
		markAnnouncementToasted("was-toasted");
		expect(isAnnouncementToasted("was-toasted")).toBe(true);
	});
});
