/**
 * Story 6.6 — AC FE-8/FE-9: Gift page → chọn tier + duration, gọi API, redirect Stripe
 * AC FE-10: API error → toast error, không crash
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

vi.mock("@/lib/apis/stripe-api.service", () => ({
	stripeApiService: {
		createGiftCheckout: vi.fn(),
		requestGift: vi.fn(),
	},
}));

vi.mock("jotai", () => ({
	useAtomValue: vi.fn(),
	useAtom: vi.fn(),
	atom: vi.fn(),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		info: vi.fn(),
	},
}));

// Stub UI components that aren't under test
vi.mock("@/components/ui/badge", () => ({
	Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("@/components/ui/button", () => ({
	Button: ({ children, onClick, disabled }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
		<button onClick={onClick} disabled={disabled} type="button">
			{children}
		</button>
	),
}));
vi.mock("@/components/ui/card", () => ({
	Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
	CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
}));

import React from "react";
import { useAtomValue } from "jotai";
import { toast } from "sonner";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import GiftPage from "@/app/dashboard/[search_space_id]/gift/page";

describe("GiftPage", () => {
	const originalLocation = window.location;

	beforeEach(() => {
		vi.clearAllMocks();

		// currentUserAtom returns null by default (no user info needed for most tests)
		vi.mocked(useAtomValue).mockReturnValue({ data: null });

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
	});

	// ------------------------------------------------------------------
	// Rendering — tier + duration selectors
	// ------------------------------------------------------------------

	it("renders Pro and Max tier options", () => {
		render(<GiftPage />);

		expect(screen.getByText("Pro")).toBeInTheDocument();
		expect(screen.getByText("Max")).toBeInTheDocument();
	});

	it("renders duration options (1, 3, 6, 12 months)", () => {
		render(<GiftPage />);

		expect(screen.getByText("1 tháng")).toBeInTheDocument();
		expect(screen.getByText("3 tháng")).toBeInTheDocument();
		expect(screen.getByText("6 tháng")).toBeInTheDocument();
		expect(screen.getByText("12 tháng")).toBeInTheDocument();
	});

	it("renders purchase button with default Pro 1-month price", () => {
		render(<GiftPage />);
		expect(screen.getByRole("button", { name: /Mua Gift Pro 1 tháng/i })).toBeInTheDocument();
	});

	// ------------------------------------------------------------------
	// FE-9: Tier selection updates button label
	// ------------------------------------------------------------------

	it("FE-9: selecting Max tier updates purchase button label", async () => {
		const user = userEvent.setup();
		render(<GiftPage />);

		const maxButton = screen.getByRole("button", { name: /Max/i });
		await user.click(maxButton);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: /Mua Gift Max 1 tháng/i })).toBeInTheDocument();
		});
	});

	it("FE-9: selecting 3-month duration updates button label and price", async () => {
		const user = userEvent.setup();
		render(<GiftPage />);

		const duration3Button = screen.getByRole("button", { name: /3 tháng/ });
		await user.click(duration3Button);

		await waitFor(() => {
			expect(
				screen.getByRole("button", { name: /Mua Gift Pro 3 tháng.*\$36/i })
			).toBeInTheDocument();
		});
	});

	// ------------------------------------------------------------------
	// FE-9: Stripe redirect on success
	// ------------------------------------------------------------------

	it("FE-9: successful checkout → redirects to Stripe checkout_url", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.createGiftCheckout).mockResolvedValue({
			checkout_url: "https://checkout.stripe.com/pay/cs_test_abc",
			admin_approval_mode: false,
		} as Awaited<ReturnType<typeof stripeApiService.createGiftCheckout>>);

		render(<GiftPage />);

		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(window.location.href).toBe("https://checkout.stripe.com/pay/cs_test_abc");
		});
	});

	it("FE-9: calls createGiftCheckout with selected tier and duration", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.createGiftCheckout).mockResolvedValue({
			checkout_url: "https://checkout.stripe.com/pay/cs_test_abc",
			admin_approval_mode: false,
		} as Awaited<ReturnType<typeof stripeApiService.createGiftCheckout>>);

		render(<GiftPage />);

		// Select Max tier + 6 months
		await user.click(screen.getByRole("button", { name: /Max/ }));
		await user.click(screen.getByRole("button", { name: /6 tháng/ }));
		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(stripeApiService.createGiftCheckout).toHaveBeenCalledWith("max_monthly", 6);
		});
	});

	// ------------------------------------------------------------------
	// Admin approval mode
	// ------------------------------------------------------------------

	it("admin_approval_mode → calls requestGift and shows success toast", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.createGiftCheckout).mockResolvedValue({
			checkout_url: null,
			admin_approval_mode: true,
		} as Awaited<ReturnType<typeof stripeApiService.createGiftCheckout>>);
		vi.mocked(stripeApiService.requestGift).mockResolvedValue(undefined as never);

		render(<GiftPage />);

		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(stripeApiService.requestGift).toHaveBeenCalled();
			expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Admin sẽ xử lý"));
		});

		// No Stripe redirect in admin mode
		expect(window.location.href).toBe("");
	});

	// ------------------------------------------------------------------
	// FE-10: Error handling — API failure → toast error, no crash
	// ------------------------------------------------------------------

	it("FE-10: API error → shows toast.error, does not redirect", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.createGiftCheckout).mockRejectedValue(new Error("Network error"));

		render(<GiftPage />);

		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Failed to create gift checkout. Please try again.");
		});

		expect(window.location.href).toBe("");
	});

	it("FE-10: missing checkout_url → shows toast.error for invalid response", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.createGiftCheckout).mockResolvedValue({
			checkout_url: null,
			admin_approval_mode: false,
		} as Awaited<ReturnType<typeof stripeApiService.createGiftCheckout>>);

		render(<GiftPage />);

		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				"Stripe checkout URL is missing. Please try again or contact support."
			);
		});
	});

	it("FE-10: loading state disables purchase button during API call", async () => {
		const user = userEvent.setup();
		let resolveCheckout!: (v: unknown) => void;
		vi.mocked(stripeApiService.createGiftCheckout).mockReturnValue(
			new Promise((res) => {
				resolveCheckout = res;
			})
		);

		render(<GiftPage />);

		await user.click(screen.getByRole("button", { name: /Mua Gift/i }));

		await waitFor(() => {
			expect(screen.getByRole("button", { name: /Đang xử lý/i })).toBeDisabled();
		});

		// Cleanup
		resolveCheckout({ checkout_url: null, admin_approval_mode: false });
	});

	// ------------------------------------------------------------------
	// Shows current user email when logged in
	// ------------------------------------------------------------------

	it("shows current user email when user is logged in", () => {
		vi.mocked(useAtomValue).mockReturnValue({ data: { email: "user@example.com" } });

		render(<GiftPage />);

		expect(screen.getByText(/user@example\.com/)).toBeInTheDocument();
	});
});
