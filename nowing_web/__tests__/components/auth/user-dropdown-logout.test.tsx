/**
 * Story 1.3 — AC FE-3: UserDropdown → logout clears tokens, redirect to login
 * Tests for UserDropdown component (logout flow).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

const mockPush = vi.fn();
const mockRefresh = vi.fn();

// Override the global next/navigation mock from vitest.setup.ts
vi.mock("next/navigation", () => ({
	useRouter: () => ({
		push: mockPush,
		refresh: mockRefresh,
		replace: vi.fn(),
		prefetch: vi.fn(),
		back: vi.fn(),
	}),
	usePathname: () => "/",
	useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth-utils", () => ({
	logout: vi.fn(),
	getLoginPath: vi.fn(() => "/login"),
}));

vi.mock("@/lib/posthog/events", () => ({
	resetUser: vi.fn(),
	trackLogout: vi.fn(),
}));

// Stub Radix DropdownMenu — render children directly without portal
vi.mock("@/components/ui/dropdown-menu", () => ({
	DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	DropdownMenuItem: ({
		children,
		onClick,
		disabled,
	}: {
		children: React.ReactNode;
		onClick?: () => void;
		disabled?: boolean;
	}) => (
		<button type="button" onClick={onClick} disabled={disabled}>
			{children}
		</button>
	),
	DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	DropdownMenuSeparator: () => <hr />,
	DropdownMenuGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Stub Avatar components
vi.mock("@/components/ui/avatar", () => ({
	Avatar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	AvatarImage: ({ src, alt }: { src?: string; alt?: string }) => <img src={src} alt={alt} />,
	AvatarFallback: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

// Stub Spinner
vi.mock("@/components/ui/spinner", () => ({
	Spinner: () => <span data-testid="spinner" />,
}));

// Stub Button
vi.mock("@/components/ui/button", () => ({
	Button: ({ children, onClick, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
		<button type="button" onClick={onClick} {...props}>
			{children}
		</button>
	),
}));

// Stub icons
vi.mock("lucide-react", () => ({
	BadgeCheck: () => <span />,
	LogOut: () => <span data-testid="logout-icon" />,
}));

import React from "react";
import { logout, getLoginPath } from "@/lib/auth-utils";
import { trackLogout, resetUser } from "@/lib/posthog/events";
import { UserDropdown } from "@/components/UserDropdown";

const TEST_USER = {
	name: "Test User",
	email: "user@example.com",
	avatar: "",
};

describe("UserDropdown — logout (FE-3)", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(logout).mockResolvedValue(undefined);
		vi.mocked(getLoginPath).mockReturnValue("/login");
	});

	// ------------------------------------------------------------------
	// FE-3: Happy path — logout → calls logout() + redirect
	// ------------------------------------------------------------------

	it("FE-3: clicking Log out → calls logout() and redirects to login", async () => {
		const user = userEvent.setup();
		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			expect(logout).toHaveBeenCalled();
			expect(mockPush).toHaveBeenCalledWith("/login");
		});
	});

	it("FE-3: calls trackLogout before logout", async () => {
		const user = userEvent.setup();
		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			expect(trackLogout).toHaveBeenCalled();
			expect(logout).toHaveBeenCalled();
		});
	});

	it("FE-3: calls resetUser during logout", async () => {
		const user = userEvent.setup();
		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			expect(resetUser).toHaveBeenCalled();
		});
	});

	it("FE-3: calls router.refresh() after redirect", async () => {
		const user = userEvent.setup();
		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			expect(mockRefresh).toHaveBeenCalled();
		});
	});

	// ------------------------------------------------------------------
	// FE-3: Loading state
	// ------------------------------------------------------------------

	it("disables logout button while logout is in progress", async () => {
		const user = userEvent.setup();
		let resolveLogout!: () => void;
		vi.mocked(logout).mockReturnValue(
			new Promise<void>((res) => {
				resolveLogout = res;
			})
		);

		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			const logoutBtns = screen.getAllByRole("button");
			const logoutBtn = logoutBtns.find((btn) => btn.textContent?.match(/log.?out|logging.?out/i));
			expect(logoutBtn?.disabled).toBe(true);
		});

		// Cleanup
		resolveLogout();
	});

	// ------------------------------------------------------------------
	// FE-3: Error path — logout throws, still redirects
	// ------------------------------------------------------------------

	it("FE-3: logout error → still calls logout again and redirects", async () => {
		const user = userEvent.setup();
		vi.mocked(logout)
			.mockRejectedValueOnce(new Error("Network error"))
			.mockResolvedValueOnce(undefined);

		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			// logout called twice: first attempt fails, catch block calls again
			expect(logout).toHaveBeenCalledTimes(2);
			expect(mockPush).toHaveBeenCalledWith("/login");
		});
	});

	it("FE-3: getLoginPath determines redirect target (e.g. Electron)", async () => {
		const user = userEvent.setup();
		vi.mocked(getLoginPath).mockReturnValue("/desktop/login");

		render(<UserDropdown user={TEST_USER} />);

		await user.click(screen.getByRole("button", { name: /log.?out/i }));

		await waitFor(() => {
			expect(mockPush).toHaveBeenCalledWith("/desktop/login");
		});
	});
});
