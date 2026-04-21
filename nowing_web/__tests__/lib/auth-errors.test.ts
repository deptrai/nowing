/**
 * Unit tests — lib/auth-errors.ts
 * Covers: getAuthErrorMessage, getAuthErrorDetails, isNetworkError, shouldRetry
 * Priority: P1
 */
import { describe, it, expect } from "vitest";
import {
	getAuthErrorMessage,
	getAuthErrorDetails,
	isNetworkError,
	shouldRetry,
} from "@/lib/auth-errors";

// -----------------------------------------------------------------------
// getAuthErrorMessage
// -----------------------------------------------------------------------

describe("getAuthErrorMessage", () => {
	// Exact code matches
	it("returns description for LOGIN_BAD_CREDENTIALS", () => {
		expect(getAuthErrorMessage("LOGIN_BAD_CREDENTIALS")).toMatch(/Invalid email or password/i);
	});

	it("returns title for LOGIN_BAD_CREDENTIALS when returnTitle=true", () => {
		expect(getAuthErrorMessage("LOGIN_BAD_CREDENTIALS", true)).toBe("Login failed");
	});

	it("returns description for LOGIN_USER_NOT_VERIFIED", () => {
		expect(getAuthErrorMessage("LOGIN_USER_NOT_VERIFIED")).toMatch(/verify your email/i);
	});

	it("returns description for REGISTER_USER_ALREADY_EXISTS", () => {
		expect(getAuthErrorMessage("REGISTER_USER_ALREADY_EXISTS")).toMatch(/already exists/i);
	});

	it("returns description for USER_INACTIVE", () => {
		expect(getAuthErrorMessage("USER_INACTIVE")).toMatch(/deactivated/i);
	});

	it("returns description for RATE_LIMIT_EXCEEDED", () => {
		expect(getAuthErrorMessage("RATE_LIMIT_EXCEEDED")).toMatch(/many requests/i);
	});

	// HTTP status codes
	it("returns description for '401'", () => {
		expect(getAuthErrorMessage("401")).toMatch(/email and password|credentials/i);
	});

	it("returns description for '403'", () => {
		expect(getAuthErrorMessage("403")).toMatch(/denied|suspended/i);
	});

	it("returns description for '409'", () => {
		expect(getAuthErrorMessage("409")).toMatch(/already exists/i);
	});

	it("returns description for '500'", () => {
		expect(getAuthErrorMessage("500")).toMatch(/server error|went wrong/i);
	});

	it("matches HTTP status embedded in message string", () => {
		expect(getAuthErrorMessage("Error 404: not found")).toMatch(/not found/i);
	});

	// OAuth codes
	it("returns description for access_denied", () => {
		expect(getAuthErrorMessage("access_denied")).toMatch(/denied|cancelled/i);
	});

	it("returns description for server_error", () => {
		expect(getAuthErrorMessage("server_error")).toMatch(/authentication server/i);
	});

	// Pattern matches
	it("matches 'bad credentials' via pattern", () => {
		const result = getAuthErrorMessage("bad_credentials");
		expect(result).toBeTruthy();
	});

	it("matches 'network error' via pattern", () => {
		expect(getAuthErrorMessage("network_error")).toMatch(/internet connection/i);
	});

	it("matches 'timeout' via pattern", () => {
		expect(getAuthErrorMessage("request_timeout")).toMatch(/too long/i);
	});

	it("matches rate limiting via pattern", () => {
		expect(getAuthErrorMessage("too many requests")).toMatch(/many|wait/i);
	});

	// Fallback
	it("returns fallback for empty string", () => {
		expect(getAuthErrorMessage("")).toBeTruthy();
	});

	it("returns fallback for unknown code", () => {
		expect(getAuthErrorMessage("TOTALLY_UNKNOWN_CODE_XYZ")).toMatch(/unexpected error/i);
	});

	// Case insensitive
	it("matches lowercase version of known code", () => {
		expect(getAuthErrorMessage("login_bad_credentials")).toMatch(/Invalid email or password/i);
	});
});

// -----------------------------------------------------------------------
// getAuthErrorDetails
// -----------------------------------------------------------------------

describe("getAuthErrorDetails", () => {
	it("returns object with title and description", () => {
		const result = getAuthErrorDetails("401");
		expect(result).toHaveProperty("title");
		expect(result).toHaveProperty("description");
	});

	it("title and description are strings", () => {
		const result = getAuthErrorDetails("LOGIN_BAD_CREDENTIALS");
		expect(typeof result.title).toBe("string");
		expect(typeof result.description).toBe("string");
	});

	it("title matches returnTitle=true result", () => {
		const result = getAuthErrorDetails("LOGIN_BAD_CREDENTIALS");
		expect(result.title).toBe(getAuthErrorMessage("LOGIN_BAD_CREDENTIALS", true));
	});
});

// -----------------------------------------------------------------------
// isNetworkError
// -----------------------------------------------------------------------

describe("isNetworkError", () => {
	it("returns true for TypeError with 'fetch' in message", () => {
		expect(isNetworkError(new TypeError("Failed to fetch"))).toBe(true);
	});

	it("returns false for TypeError without 'fetch'", () => {
		expect(isNetworkError(new TypeError("Cannot read property"))).toBe(false);
	});

	it("returns true for string containing 'network'", () => {
		expect(isNetworkError("network error")).toBe(true);
	});

	it("returns true for string containing 'connection'", () => {
		expect(isNetworkError("connection refused")).toBe(true);
	});

	it("returns true for string containing 'cors'", () => {
		expect(isNetworkError("cors error")).toBe(true);
	});

	it("returns false for generic Error", () => {
		expect(isNetworkError(new Error("something broke"))).toBe(false);
	});

	it("returns false for non-string, non-TypeError", () => {
		expect(isNetworkError(null)).toBe(false);
		expect(isNetworkError(42)).toBe(false);
	});
});

// -----------------------------------------------------------------------
// shouldRetry
// -----------------------------------------------------------------------

describe("shouldRetry", () => {
	it("returns true for '500'", () => {
		expect(shouldRetry("500")).toBe(true);
	});

	it("returns true for '503'", () => {
		expect(shouldRetry("503")).toBe(true);
	});

	it("returns true for '429'", () => {
		expect(shouldRetry("429")).toBe(true);
	});

	it("returns true for 'NETWORK_ERROR'", () => {
		expect(shouldRetry("NETWORK_ERROR")).toBe(true);
	});

	it("returns true for 'TIMEOUT'", () => {
		expect(shouldRetry("TIMEOUT")).toBe(true);
	});

	it("returns true for 'server_error'", () => {
		expect(shouldRetry("server_error")).toBe(true);
	});

	it("returns true for 'temporarily_unavailable'", () => {
		expect(shouldRetry("temporarily_unavailable")).toBe(true);
	});

	it("returns false for '401'", () => {
		expect(shouldRetry("401")).toBe(false);
	});

	it("returns false for 'LOGIN_BAD_CREDENTIALS'", () => {
		expect(shouldRetry("LOGIN_BAD_CREDENTIALS")).toBe(false);
	});

	it("returns false for 'REGISTER_USER_ALREADY_EXISTS'", () => {
		expect(shouldRetry("REGISTER_USER_ALREADY_EXISTS")).toBe(false);
	});

	it("case insensitive match for 'timeout'", () => {
		expect(shouldRetry("timeout")).toBe(true);
	});
});
