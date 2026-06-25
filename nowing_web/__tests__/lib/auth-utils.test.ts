/**
 * Unit tests — lib/auth-utils.ts
 * Covers: isPublicRoute (P0), handleUnauthorized (P0), getAndClearRedirectPath
 * Priority: P0 (security-critical)
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { isPublicRoute, handleUnauthorized, getAndClearRedirectPath } from "@/lib/auth-utils";

// -----------------------------------------------------------------------
// localStorage + window.location mock
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
		_store: () => store,
	};
})();

Object.defineProperty(globalThis, "localStorage", {
	value: localStorageMock,
	writable: true,
});

const BEARER_TOKEN_KEY = "nowing_bearer_token";
const REFRESH_TOKEN_KEY = "nowing_refresh_token";
const REDIRECT_PATH_KEY = "nowing_redirect_path";

function setLocation(pathname: string, search = "", hash = "") {
	Object.defineProperty(window, "location", {
		configurable: true,
		value: { pathname, search, hash, href: "" },
	});
}

beforeEach(() => {
	localStorageMock.clear();
	localStorageMock.getItem.mockClear();
	localStorageMock.setItem.mockClear();
	localStorageMock.removeItem.mockClear();

	// Default: /dashboard (protected route)
	setLocation("/dashboard");

	// Ensure no electronAPI (web env)
	Object.defineProperty(window, "electronAPI", {
		configurable: true,
		value: undefined,
	});
});

afterEach(() => {
	setLocation("/");
});

// -----------------------------------------------------------------------
// isPublicRoute — P0
// -----------------------------------------------------------------------

describe("isPublicRoute", () => {
	it("returns true for root path '/'", () => {
		expect(isPublicRoute("/")).toBe(true);
	});

	it("returns true for empty string", () => {
		expect(isPublicRoute("")).toBe(true);
	});

	it("returns true for /login", () => {
		expect(isPublicRoute("/login")).toBe(true);
	});

	it("returns true for /login subpath", () => {
		expect(isPublicRoute("/login/sso")).toBe(true);
	});

	it("returns true for /register", () => {
		expect(isPublicRoute("/register")).toBe(true);
	});

	it("returns true for /auth", () => {
		expect(isPublicRoute("/auth")).toBe(true);
	});

	it("returns true for /auth/callback", () => {
		expect(isPublicRoute("/auth/callback")).toBe(true);
	});

	it("returns true for /pricing", () => {
		expect(isPublicRoute("/pricing")).toBe(true);
	});

	it("returns true for /docs/api", () => {
		expect(isPublicRoute("/docs/api")).toBe(true);
	});

	it("returns true for /public/any", () => {
		expect(isPublicRoute("/public/any")).toBe(true);
	});

	it("returns true for /invite/abc123", () => {
		expect(isPublicRoute("/invite/abc123")).toBe(true);
	});

	it("returns true for /changelog", () => {
		expect(isPublicRoute("/changelog")).toBe(true);
	});

	it("returns true for /privacy", () => {
		expect(isPublicRoute("/privacy")).toBe(true);
	});

	it("returns true for /terms", () => {
		expect(isPublicRoute("/terms")).toBe(true);
	});

	it("returns false for /dashboard", () => {
		expect(isPublicRoute("/dashboard")).toBe(false);
	});

	it("returns false for /chat", () => {
		expect(isPublicRoute("/chat")).toBe(false);
	});

	it("returns false for /settings/profile", () => {
		expect(isPublicRoute("/settings/profile")).toBe(false);
	});

	it("returns false for /redeem", () => {
		expect(isPublicRoute("/redeem")).toBe(false);
	});

	it("returns false for path that starts with /log but not /login", () => {
		// /log is not a public prefix
		expect(isPublicRoute("/log")).toBe(false);
	});
});

// -----------------------------------------------------------------------
// handleUnauthorized — P0
// -----------------------------------------------------------------------

describe("handleUnauthorized", () => {
	it("clears bearer token from localStorage", () => {
		localStorageMock.setItem(BEARER_TOKEN_KEY, "tok_abc");
		setLocation("/dashboard");

		handleUnauthorized();

		expect(localStorageMock.removeItem).toHaveBeenCalledWith(BEARER_TOKEN_KEY);
	});

	it("clears refresh token from localStorage", () => {
		localStorageMock.setItem(REFRESH_TOKEN_KEY, "ref_abc");
		setLocation("/dashboard");

		handleUnauthorized();

		expect(localStorageMock.removeItem).toHaveBeenCalledWith(REFRESH_TOKEN_KEY);
	});

	it("redirects to /login on protected route", () => {
		setLocation("/dashboard");

		handleUnauthorized();

		expect(window.location.href).toBe("/login");
	});

	it("saves redirect path when on protected non-excluded route", () => {
		setLocation("/chat", "?q=hello", "#section");

		handleUnauthorized();

		expect(localStorageMock.setItem).toHaveBeenCalledWith(
			REDIRECT_PATH_KEY,
			"/chat?q=hello#section"
		);
	});

	it("does NOT save redirect path when on /auth", () => {
		setLocation("/auth");

		handleUnauthorized();

		const setItemCalls = localStorageMock.setItem.mock.calls.map((c) => c[0]);
		expect(setItemCalls).not.toContain(REDIRECT_PATH_KEY);
	});

	it("does NOT save redirect path when on /auth/callback", () => {
		setLocation("/auth/callback");

		handleUnauthorized();

		const setItemCalls = localStorageMock.setItem.mock.calls.map((c) => c[0]);
		expect(setItemCalls).not.toContain(REDIRECT_PATH_KEY);
	});

	it("does NOT save redirect path when on /", () => {
		setLocation("/");

		handleUnauthorized();

		const setItemCalls = localStorageMock.setItem.mock.calls.map((c) => c[0]);
		expect(setItemCalls).not.toContain(REDIRECT_PATH_KEY);
	});

	it("does NOT redirect when on a public route", () => {
		setLocation("/login");

		handleUnauthorized();

		// href stays empty string (not set to /login)
		expect(window.location.href).toBe("");
	});

	it("still clears tokens even on public route", () => {
		localStorageMock.setItem(BEARER_TOKEN_KEY, "tok_xyz");
		setLocation("/pricing");

		handleUnauthorized();

		expect(localStorageMock.removeItem).toHaveBeenCalledWith(BEARER_TOKEN_KEY);
		expect(localStorageMock.removeItem).toHaveBeenCalledWith(REFRESH_TOKEN_KEY);
	});
});

// -----------------------------------------------------------------------
// getAndClearRedirectPath
// -----------------------------------------------------------------------

describe("getAndClearRedirectPath", () => {
	it("returns null when no redirect path stored", () => {
		expect(getAndClearRedirectPath()).toBeNull();
	});

	it("returns stored redirect path", () => {
		localStorageMock.setItem(REDIRECT_PATH_KEY, "/chat");
		expect(getAndClearRedirectPath()).toBe("/chat");
	});

	it("removes redirect path after reading", () => {
		localStorageMock.setItem(REDIRECT_PATH_KEY, "/settings");
		getAndClearRedirectPath();
		expect(localStorageMock.removeItem).toHaveBeenCalledWith(REDIRECT_PATH_KEY);
	});

	it("returns null on second call (cleared)", () => {
		localStorageMock.setItem(REDIRECT_PATH_KEY, "/chat");
		getAndClearRedirectPath(); // first call
		expect(getAndClearRedirectPath()).toBeNull(); // second call
	});
});
