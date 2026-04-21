/**
 * Unit tests — lib/error.ts
 * Covers: AppError, NetworkError, ValidationError, AuthenticationError,
 *         AuthorizationError, NotFoundError
 * Priority: P1
 */
import { describe, it, expect } from "vitest";
import {
	AppError,
	NetworkError,
	ValidationError,
	AuthenticationError,
	AuthorizationError,
	NotFoundError,
} from "@/lib/error";

describe("AppError", () => {
	it("is an instance of Error", () => {
		expect(new AppError("msg")).toBeInstanceOf(Error);
	});

	it("has name 'AppError'", () => {
		expect(new AppError("msg").name).toBe("AppError");
	});

	it("stores message", () => {
		expect(new AppError("something went wrong").message).toBe("something went wrong");
	});

	it("stores status", () => {
		expect(new AppError("msg", 404).status).toBe(404);
	});

	it("stores statusText", () => {
		expect(new AppError("msg", 500, "Internal Server Error").statusText).toBe(
			"Internal Server Error"
		);
	});

	it("status and statusText are undefined when not provided", () => {
		const e = new AppError("msg");
		expect(e.status).toBeUndefined();
		expect(e.statusText).toBeUndefined();
	});
});

describe("NetworkError", () => {
	it("is an instance of AppError and Error", () => {
		const e = new NetworkError("network fail");
		expect(e).toBeInstanceOf(AppError);
		expect(e).toBeInstanceOf(Error);
	});

	it("has name 'NetworkError'", () => {
		expect(new NetworkError("msg").name).toBe("NetworkError");
	});

	it("stores status and statusText", () => {
		const e = new NetworkError("timeout", 503, "Service Unavailable");
		expect(e.status).toBe(503);
		expect(e.statusText).toBe("Service Unavailable");
	});
});

describe("ValidationError", () => {
	it("is an instance of AppError", () => {
		expect(new ValidationError("bad input")).toBeInstanceOf(AppError);
	});

	it("has name 'ValidationError'", () => {
		expect(new ValidationError("msg").name).toBe("ValidationError");
	});
});

describe("AuthenticationError", () => {
	it("is an instance of AppError", () => {
		expect(new AuthenticationError("unauth")).toBeInstanceOf(AppError);
	});

	it("has name 'AuthenticationError'", () => {
		expect(new AuthenticationError("msg").name).toBe("AuthenticationError");
	});

	it("stores 401 status", () => {
		expect(new AuthenticationError("msg", 401).status).toBe(401);
	});
});

describe("AuthorizationError", () => {
	it("is an instance of AppError", () => {
		expect(new AuthorizationError("forbidden")).toBeInstanceOf(AppError);
	});

	it("has name 'AuthorizationError'", () => {
		expect(new AuthorizationError("msg").name).toBe("AuthorizationError");
	});
});

describe("NotFoundError", () => {
	it("is an instance of AppError", () => {
		expect(new NotFoundError("not found")).toBeInstanceOf(AppError);
	});

	it("has name 'NotFoundError'", () => {
		expect(new NotFoundError("msg").name).toBe("NotFoundError");
	});

	it("stores 404 status", () => {
		expect(new NotFoundError("msg", 404).status).toBe(404);
	});
});
