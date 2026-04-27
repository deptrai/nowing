/**
 * Story 1.3 — AC FE-2: TokenHandler → lưu token vào localStorage, redirect
 * Tests for TokenHandler component.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";

// --- Module-level mocks ---

vi.mock("@/lib/auth-utils", () => ({
	setBearerToken: vi.fn(),
	setRefreshToken: vi.fn(),
	getAndClearRedirectPath: vi.fn(() => null),
}));

vi.mock("@/lib/apis/search-spaces-api.service", () => ({
	searchSpacesApiService: {
		getSearchSpaces: vi.fn(() => Promise.resolve([])),
	},
}));

vi.mock("@/lib/posthog/events", () => ({
	trackLoginSuccess: vi.fn(),
}));

vi.mock("@/hooks/use-global-loading", () => ({
	useGlobalLoadingEffect: vi.fn(),
}));

import React from "react";
import TokenHandler from "@/components/TokenHandler";
import { setBearerToken, setRefreshToken, getAndClearRedirectPath } from "@/lib/auth-utils";

// --- localStorage mock ---
const localStorageStore: Record<string, string> = {};
const localStorageMock = {
	getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
	setItem: vi.fn((key: string, value: string) => {
		localStorageStore[key] = value;
	}),
	removeItem: vi.fn((key: string) => {
		delete localStorageStore[key];
	}),
	clear: vi.fn(() => {
		Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k]);
	}),
};
Object.defineProperty(window, "localStorage", {
	value: localStorageMock,
	writable: true,
});

describe("TokenHandler", () => {
	const originalLocation = window.location;

	beforeEach(() => {
		vi.clearAllMocks();
		localStorageMock.clear();

		// Allow window.location.href assignment
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { ...originalLocation, href: "" },
		});
	});

	afterEach(() => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: originalLocation,
		});
	});

	// ------------------------------------------------------------------
	// FE-2: Token stored in localStorage on mount
	// ------------------------------------------------------------------

	it("FE-2: stores token in localStorage when token param is present", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: {
				href: "",
				search: "?token=abc123",
			},
		});

		render(<TokenHandler storageKey="nowing_bearer_token" />);

		await vi.waitFor(() => {
			expect(localStorageMock.setItem).toHaveBeenCalledWith("nowing_bearer_token", "abc123");
		});
	});

	it("FE-2: calls setBearerToken with the token", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "?token=tok_xyz" },
		});

		render(<TokenHandler />);

		await vi.waitFor(() => {
			expect(setBearerToken).toHaveBeenCalledWith("tok_xyz");
		});
	});

	it("stores refresh_token when present in URL", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "?token=tok_xyz&refresh_token=ref_abc" },
		});

		render(<TokenHandler />);

		await vi.waitFor(() => {
			expect(setRefreshToken).toHaveBeenCalledWith("ref_abc");
		});
	});

	it("does not call setRefreshToken when refresh_token absent", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "?token=tok_xyz" },
		});

		render(<TokenHandler />);

		await vi.waitFor(() => {
			expect(setBearerToken).toHaveBeenCalled();
		});

		expect(setRefreshToken).not.toHaveBeenCalled();
	});

	// ------------------------------------------------------------------
	// FE-2: Redirect after storing token
	// ------------------------------------------------------------------

	it("FE-2: redirects to default /dashboard after token stored", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "?token=tok_xyz" },
		});
		vi.mocked(getAndClearRedirectPath).mockReturnValue(null);

		render(<TokenHandler redirectPath="/dashboard" />);

		await vi.waitFor(() => {
			expect(window.location.href).toBe("/dashboard");
		});
	});

	it("redirects to saved path when getAndClearRedirectPath returns one", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "?token=tok_xyz" },
		});
		vi.mocked(getAndClearRedirectPath).mockReturnValue("/dashboard/space123");

		render(<TokenHandler redirectPath="/dashboard" />);

		await vi.waitFor(() => {
			expect(window.location.href).toBe("/dashboard/space123");
		});
	});

	// ------------------------------------------------------------------
	// No-op when token param absent
	// ------------------------------------------------------------------

	it("does nothing when no token in URL", async () => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "", search: "" },
		});

		await act(async () => {
			render(<TokenHandler />);
		});

		expect(localStorageMock.getItem("nowing_bearer_token")).toBeNull();
		expect(setBearerToken).not.toHaveBeenCalled();
		expect(window.location.href).toBe("");
	});

	// ------------------------------------------------------------------
	// Returns null (no visual output)
	// ------------------------------------------------------------------

	it("renders null — no visible DOM output", () => {
		const { container } = render(<TokenHandler />);
		expect(container.firstChild).toBeNull();
	});
});
