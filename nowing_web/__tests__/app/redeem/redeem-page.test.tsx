/**
 * Story 4.x — AC FE-11: Redeem gift code → calls API, shows success/error
 * Tests for RedeemPage (app/redeem/page.tsx).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

vi.mock("@/lib/auth-utils", () => ({
	getBearerToken: vi.fn(() => "tok_test"),
}));

vi.mock("@/lib/apis/stripe-api.service", () => ({
	stripeApiService: {
		redeemGiftCode: vi.fn(),
	},
}));

vi.mock("@tanstack/react-query", () => ({
	useQueryClient: vi.fn(() => ({
		invalidateQueries: vi.fn(),
	})),
}));

vi.mock("@/atoms/user/user-query.atoms", () => ({
	USER_QUERY_KEY: ["user"],
}));

vi.mock("@/lib/error", () => ({
	AppError: class AppError extends Error {
		constructor(message: string) {
			super(message);
			this.name = "AppError";
		}
	},
}));

// Stub Next.js Link
vi.mock("next/link", () => ({
	default: ({ href, children }: { href: string; children: React.ReactNode }) => (
		<a href={href}>{children}</a>
	),
}));

// Stub UI components
vi.mock("@/components/ui/button", () => ({
	Button: ({
		children,
		onClick,
		disabled,
		asChild,
		...props
	}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => {
		if (asChild && React.isValidElement(children)) return children;
		return (
			<button type="button" onClick={onClick} disabled={disabled} {...props}>
				{children}
			</button>
		);
	},
}));

vi.mock("@/components/ui/input", () => ({
	Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/card", () => ({
	Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
	CardDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
	CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CardFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import React from "react";
import { getBearerToken } from "@/lib/auth-utils";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import RedeemPage from "@/app/redeem/page";

describe("RedeemPage — gift code (FE-11)", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(getBearerToken).mockReturnValue("tok_test");
	});

	// ------------------------------------------------------------------
	// Auth gate
	// ------------------------------------------------------------------

	it("FE-11: unauthenticated → shows login link", async () => {
		vi.mocked(getBearerToken).mockReturnValue(null);

		render(<RedeemPage />);

		await waitFor(() => {
			expect(screen.getByRole("link", { name: /đăng nhập/i })).toBeInTheDocument();
		});
	});

	it("FE-11: authenticated → shows gift code input form", async () => {
		render(<RedeemPage />);

		await waitFor(() => {
			expect(screen.getByPlaceholderText(/GIFT-XXXX/i)).toBeInTheDocument();
		});
	});

	// ------------------------------------------------------------------
	// FE-11: Happy path — redeem success
	// ------------------------------------------------------------------

	it("FE-11: submit valid code → calls redeemGiftCode with uppercased code", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.redeemGiftCode).mockResolvedValue({
			message: "ok",
			new_expiry: "2025-12-31T00:00:00Z",
		});

		render(<RedeemPage />);

		await waitFor(() => {
			expect(screen.getByPlaceholderText(/GIFT-XXXX/i)).toBeInTheDocument();
		});

		await user.type(screen.getByPlaceholderText(/GIFT-XXXX/i), "gift-test-1234");
		await user.click(screen.getByRole("button", { name: /kích hoạt/i }));

		await waitFor(() => {
			expect(stripeApiService.redeemGiftCode).toHaveBeenCalledWith("GIFT-TEST-1234");
		});
	});

	it("FE-11: success → shows expiry date in success card", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.redeemGiftCode).mockResolvedValue({
			message: "ok",
			new_expiry: "2025-12-31T00:00:00Z",
		});

		render(<RedeemPage />);

		await waitFor(() => screen.getByPlaceholderText(/GIFT-XXXX/i));

		await user.type(screen.getByPlaceholderText(/GIFT-XXXX/i), "GIFT-ABCD-1234");
		await user.click(screen.getByRole("button", { name: /kích hoạt/i }));

		await waitFor(() => {
			expect(screen.getByText(/kích hoạt thành công/i)).toBeInTheDocument();
		});
	});

	// ------------------------------------------------------------------
	// FE-11: Error path
	// ------------------------------------------------------------------

	it("FE-11: API error → shows error message", async () => {
		const user = userEvent.setup();
		vi.mocked(stripeApiService.redeemGiftCode).mockRejectedValue(new Error("Invalid code"));

		render(<RedeemPage />);

		await waitFor(() => screen.getByPlaceholderText(/GIFT-XXXX/i));

		await user.type(screen.getByPlaceholderText(/GIFT-XXXX/i), "GIFT-INVALID");
		await user.click(screen.getByRole("button", { name: /kích hoạt/i }));

		await waitFor(() => {
			expect(screen.getByText("Invalid code")).toBeInTheDocument();
		});
	});

	// ------------------------------------------------------------------
	// FE-11: Loading state
	// ------------------------------------------------------------------

	it("FE-11: submit → button shows 'Đang xử lý...' during loading", async () => {
		const user = userEvent.setup();
		let resolve!: (v: unknown) => void;
		vi.mocked(stripeApiService.redeemGiftCode).mockReturnValue(
			new Promise((res) => {
				resolve = res;
			})
		);

		render(<RedeemPage />);

		await waitFor(() => screen.getByPlaceholderText(/GIFT-XXXX/i));

		await user.type(screen.getByPlaceholderText(/GIFT-XXXX/i), "GIFT-1234");
		await user.click(screen.getByRole("button", { name: /kích hoạt/i }));

		await waitFor(() => {
			expect(screen.getByRole("button", { name: /đang xử lý/i })).toBeDisabled();
		});

		resolve({ message: "ok", new_expiry: "2025-12-31" });
	});

	// ------------------------------------------------------------------
	// FE-11: Empty input — button disabled
	// ------------------------------------------------------------------

	it("FE-11: empty input → submit button is disabled", async () => {
		render(<RedeemPage />);

		await waitFor(() => screen.getByPlaceholderText(/GIFT-XXXX/i));

		const btn = screen.getByRole("button", { name: /kích hoạt/i });
		expect(btn).toBeDisabled();
	});
});
