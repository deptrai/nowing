/**
 * Story 5.1 — AC FE-8: Pricing page → chọn plan, click → Stripe checkout redirect
 * Tests for PricingBasic (pricing-section) component.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

vi.mock("@/lib/auth-utils", () => ({
	isAuthenticated: vi.fn(() => true),
	redirectToLogin: vi.fn(),
	authenticatedFetch: vi.fn(),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

vi.mock("@/lib/env-config", () => ({
	BACKEND_URL: "http://localhost:8000",
}));

// Stub Pricing sub-component — exposes plan onAction callbacks as buttons
vi.mock("@/components/pricing", () => ({
	Pricing: ({
		plans,
	}: {
		plans: Array<{
			name: string;
			buttonText: string;
			onAction?: () => void;
			disabled?: boolean;
		}>;
	}) => (
		<div>
			{plans
				.filter((p) => p.onAction)
				.map((p) => (
					<button key={p.name} type="button" onClick={p.onAction} disabled={p.disabled}>
						{p.buttonText}
					</button>
				))}
		</div>
	),
}));

import React from "react";
import { toast } from "sonner";
import { isAuthenticated, redirectToLogin, authenticatedFetch } from "@/lib/auth-utils";
import PricingBasic from "@/components/pricing/pricing-section";

function makeFetchResponse(body: object, status = 200) {
	return Promise.resolve({
		ok: status >= 200 && status < 300,
		status,
		json: () => Promise.resolve(body),
	} as Response);
}

describe("PricingBasic (pricing-section)", () => {
	const originalLocation = window.location;

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(isAuthenticated).mockReturnValue(true);

		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "" },
		});

		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: true,
		});
	});

	afterEach(() => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: originalLocation,
		});
	});

	// ------------------------------------------------------------------
	// FE-8: Successful Stripe redirect — Pro plan
	// ------------------------------------------------------------------

	it("FE-8: clicking Upgrade to Pro → calls API and redirects to Stripe checkout", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockReturnValue(
			makeFetchResponse({ checkout_url: "https://checkout.stripe.com/pay/pro_test" })
		);

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(authenticatedFetch).toHaveBeenCalledWith(
				expect.stringContaining("/stripe/create-subscription-checkout"),
				expect.objectContaining({
					method: "POST",
					body: expect.stringContaining("pro_monthly"),
				})
			);
			expect(window.location.href).toBe("https://checkout.stripe.com/pay/pro_test");
		});
	});

	// ------------------------------------------------------------------
	// FE-8: Successful Stripe redirect — Max plan
	// ------------------------------------------------------------------

	it("FE-8: clicking Upgrade to Max → calls API and redirects to Stripe checkout", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockReturnValue(
			makeFetchResponse({ checkout_url: "https://checkout.stripe.com/pay/max_test" })
		);

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Max" }));

		await waitFor(() => {
			expect(window.location.href).toBe("https://checkout.stripe.com/pay/max_test");
		});
	});

	// ------------------------------------------------------------------
	// Unauthenticated → redirect to login
	// ------------------------------------------------------------------

	it("redirects to login when user is not authenticated", async () => {
		const user = userEvent.setup();
		vi.mocked(isAuthenticated).mockReturnValue(false);

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(redirectToLogin).toHaveBeenCalled();
		});

		expect(authenticatedFetch).not.toHaveBeenCalled();
	});

	// ------------------------------------------------------------------
	// Admin approval mode
	// ------------------------------------------------------------------

	it("admin_approval_mode → shows success toast, no redirect", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockReturnValue(makeFetchResponse({ admin_approval_mode: true }));

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("admin will approve"));
		});

		expect(window.location.href).toBe("");
	});

	// ------------------------------------------------------------------
	// Error paths — FE-8 resilience
	// ------------------------------------------------------------------

	it("503 response → shows payment not configured toast", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockReturnValue(makeFetchResponse({}, 503));

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("Payment not configured"));
		});
	});

	it("409 response → shows already subscribed toast", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockReturnValue(
			makeFetchResponse({ detail: "Already subscribed" }, 409)
		);

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Already subscribed");
		});
	});

	it("network error → shows connection error toast", async () => {
		const user = userEvent.setup();
		vi.mocked(authenticatedFetch).mockRejectedValue(new Error("Network failure"));

		render(<PricingBasic />);

		await user.click(screen.getByRole("button", { name: "Upgrade to Pro" }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("check your connection"));
		});
	});
});
