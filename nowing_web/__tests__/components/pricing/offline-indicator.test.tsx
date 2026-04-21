/**
 * Story 4.2 — AC FE-6: Offline indicator → disables actions when navigator.onLine = false
 * Tests for PricingBasic offline behavior.
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
			{plans.map((p) => (
				<button
					key={p.name}
					type="button"
					onClick={p.onAction}
					disabled={p.disabled}
					data-plan={p.name}
				>
					{p.buttonText}
				</button>
			))}
		</div>
	),
}));

import React from "react";
import { isAuthenticated, authenticatedFetch } from "@/lib/auth-utils";
import PricingBasic from "@/components/pricing/pricing-section";

describe("PricingBasic — offline indicator (FE-6)", () => {
	const originalLocation = window.location;

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(isAuthenticated).mockReturnValue(true);

		Object.defineProperty(window, "location", {
			configurable: true,
			value: { href: "" },
		});
	});

	afterEach(() => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: originalLocation,
		});
		// Restore navigator.onLine
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: true,
		});
	});

	// ------------------------------------------------------------------
	// FE-6: Offline → buttons disabled
	// ------------------------------------------------------------------

	it("FE-6: when navigator.onLine is false → plan buttons are disabled", () => {
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: false,
		});

		render(<PricingBasic />);

		// When offline, button text changes to "Offline — unavailable"
		const offlineButtons = screen.getAllByRole("button", { name: /Offline/i });
		expect(offlineButtons.length).toBeGreaterThanOrEqual(2);
		offlineButtons.forEach((btn) => expect(btn).toBeDisabled());
	});

	it("FE-6: when offline → clicking disabled button does not call API", async () => {
		const user = userEvent.setup();
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: false,
		});

		render(<PricingBasic />);

		const offlineButtons = screen.getAllByRole("button", { name: /Offline/i });
		await user.click(offlineButtons[0]);

		expect(authenticatedFetch).not.toHaveBeenCalled();
	});

	// ------------------------------------------------------------------
	// FE-6: Online → buttons enabled
	// ------------------------------------------------------------------

	it("FE-6: when navigator.onLine is true → plan buttons are enabled", () => {
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: true,
		});

		render(<PricingBasic />);

		const proButton = screen.getByRole("button", { name: /Upgrade to Pro/i });
		expect(proButton).not.toBeDisabled();
	});

	// ------------------------------------------------------------------
	// FE-6: Online event → re-enables buttons
	// ------------------------------------------------------------------

	it("FE-6: 'online' event fires → buttons become enabled", async () => {
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: false,
		});

		render(<PricingBasic />);

		// Initially disabled (text changes to "Offline — unavailable" when offline)
		const offlineBtns = screen.getAllByRole("button", { name: /Offline/i });
		expect(offlineBtns.length).toBeGreaterThanOrEqual(1);
		expect(offlineBtns[0]).toBeDisabled();

		// Simulate coming back online
		Object.defineProperty(navigator, "onLine", {
			configurable: true,
			value: true,
		});
		window.dispatchEvent(new Event("online"));

		await waitFor(() => {
			expect(screen.getByRole("button", { name: /Upgrade to Pro/i })).not.toBeDisabled();
		});
	});
});
