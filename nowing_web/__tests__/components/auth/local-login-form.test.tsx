/**
 * Story 1.3 — AC FE-1: Login form → lưu token vào localStorage, redirect to /auth/callback
 * Tests for LocalLoginForm component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks (must hoist before component import) ---

// Override the global next/navigation mock from vitest.setup.ts so useRouter is a spy
vi.mock("next/navigation", () => ({
	useRouter: vi.fn(),
	usePathname: () => "/",
	useSearchParams: () => new URLSearchParams(),
}));

// Mock Jotai atom so we don't need real QueryClient wiring
vi.mock("jotai", () => ({
	useAtom: vi.fn(),
	useAtomValue: vi.fn(),
	atom: vi.fn(),
}));

// Mock next-intl translations
vi.mock("next-intl", () => ({
	useTranslations: () => (key: string) => key,
}));

// Mock posthog tracking — side effects, not under test here
vi.mock("@/lib/posthog/events", () => ({
	trackLoginAttempt: vi.fn(),
	trackLoginSuccess: vi.fn(),
	trackLoginFailure: vi.fn(),
}));

// Mock auth-errors utilities
vi.mock("@/lib/auth-errors", () => ({
	getAuthErrorDetails: (code: string) => ({
		title: "Login Failed",
		description: `Error: ${code}`,
	}),
	isNetworkError: vi.fn(() => false),
}));

// Mock env-config
vi.mock("@/lib/env-config", () => ({
	AUTH_TYPE: "LOCAL",
	BACKEND_URL: "http://localhost:8000",
}));

// motion/react AnimatePresence — render children directly
vi.mock("motion/react", () => ({
	AnimatePresence: ({ children }: { children: React.ReactNode }) => children,
	motion: {
		div: ({ children, ...props }: React.ComponentPropsWithoutRef<"div">) => (
			<div {...props}>{children}</div>
		),
	},
}));

import React from "react";
import { useAtom } from "jotai";
import { useRouter } from "next/navigation";
import { LocalLoginForm } from "@/app/(home)/login/LocalLoginForm";

const mockPush = vi.fn();
vi.mocked(useRouter).mockReturnValue({ push: mockPush } as ReturnType<typeof useRouter>);

function makeMutateAsync(implementation: () => Promise<unknown>) {
	return {
		mutateAsync: vi.fn().mockImplementation(implementation),
		isPending: false,
	};
}

describe("LocalLoginForm", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Re-apply useRouter mock after clearAllMocks clears call history
		vi.mocked(useRouter).mockReturnValue({ push: mockPush } as ReturnType<typeof useRouter>);
		sessionStorage.clear();
		// Default: not loading, no pending mutation
		vi.mocked(useAtom).mockReturnValue([
			{ mutateAsync: vi.fn(), isPending: false },
			vi.fn(),
		] as ReturnType<typeof useAtom>);
	});

	// ------------------------------------------------------------------
	// Rendering
	// ------------------------------------------------------------------

	it("renders email + password inputs and submit button", () => {
		render(<LocalLoginForm />);

		expect(screen.getByLabelText("email")).toBeInTheDocument();
		expect(screen.getByLabelText("password")).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "sign_in" })).toBeInTheDocument();
	});

	it("shows register link when AUTH_TYPE=LOCAL", () => {
		render(<LocalLoginForm />);
		expect(screen.getByRole("link", { name: "sign_up" })).toHaveAttribute("href", "/register");
	});

	// ------------------------------------------------------------------
	// FE-1: Happy path — successful login → sessionStorage flag + redirect
	// ------------------------------------------------------------------

	it("FE-1: on login success → sets sessionStorage flag and redirects to /auth/callback", async () => {
		const user = userEvent.setup();
		const mockLogin = vi.fn().mockResolvedValue({ access_token: "tok_abc123" });

		vi.mocked(useAtom).mockReturnValue([
			{ mutateAsync: mockLogin, isPending: false },
			vi.fn(),
		] as ReturnType<typeof useAtom>);

		render(<LocalLoginForm />);

		await user.type(screen.getByLabelText("email"), "user@example.com");
		await user.type(screen.getByLabelText("password"), "secret123");
		await user.click(screen.getByRole("button", { name: "sign_in" }));

		await waitFor(() => {
			expect(mockLogin).toHaveBeenCalledWith({
				username: "user@example.com",
				password: "secret123",
				grant_type: "password",
			});
		});

		// sessionStorage flag must be set before redirect
		expect(sessionStorage.getItem("login_success_tracked")).toBe("true");

		// Redirect fires after 500ms timeout — waitFor polls until it fires (real timers)
		await waitFor(
			() => {
				expect(mockPush).toHaveBeenCalledWith("/auth/callback?token=tok_abc123");
			},
			{ timeout: 2000 }
		);
	});

	// ------------------------------------------------------------------
	// FE-1: Loading state
	// ------------------------------------------------------------------

	it("disables submit button while login is pending", () => {
		vi.mocked(useAtom).mockReturnValue([
			{ mutateAsync: vi.fn(), isPending: true },
			vi.fn(),
		] as ReturnType<typeof useAtom>);

		render(<LocalLoginForm />);

		expect(screen.getByRole("button", { name: /sign_in/i })).toBeDisabled();
	});

	// ------------------------------------------------------------------
	// Error path — API error → display error message, no redirect
	// ------------------------------------------------------------------

	it("shows error message on login failure, does not redirect", async () => {
		const user = userEvent.setup();
		const mockLogin = vi.fn().mockRejectedValue(new Error("401"));

		vi.mocked(useAtom).mockReturnValue([
			{ mutateAsync: mockLogin, isPending: false },
			vi.fn(),
		] as ReturnType<typeof useAtom>);

		render(<LocalLoginForm />);

		await user.type(screen.getByLabelText("email"), "bad@example.com");
		await user.type(screen.getByLabelText("password"), "wrongpass");
		await user.click(screen.getByRole("button", { name: "sign_in" }));

		await waitFor(() => {
			expect(screen.getByText("Login Failed")).toBeInTheDocument();
		});

		expect(mockPush).not.toHaveBeenCalled();
	});

	it("clears error when dismiss button is clicked", async () => {
		const user = userEvent.setup();
		const mockLogin = vi.fn().mockRejectedValue(new Error("401"));

		vi.mocked(useAtom).mockReturnValue([
			{ mutateAsync: mockLogin, isPending: false },
			vi.fn(),
		] as ReturnType<typeof useAtom>);

		render(<LocalLoginForm />);

		await user.type(screen.getByLabelText("email"), "bad@example.com");
		await user.type(screen.getByLabelText("password"), "wrongpass");
		await user.click(screen.getByRole("button", { name: "sign_in" }));

		await waitFor(() => {
			expect(screen.getByText("Login Failed")).toBeInTheDocument();
		});

		await user.click(screen.getByLabelText("Dismiss error"));

		await waitFor(() => {
			expect(screen.queryByText("Login Failed")).not.toBeInTheDocument();
		});
	});
});
