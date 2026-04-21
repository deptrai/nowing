/**
 * Story 2.x — AC FE-4: Citation click → calls onNavigate callback / openSafeNavigationHref
 * Tests for Citation component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

vi.mock("@/components/tool-ui/shared/media", () => ({
	openSafeNavigationHref: vi.fn(),
	sanitizeHref: vi.fn((href: string) => href),
}));

// Stub Popover to render children directly
vi.mock("@/components/tool-ui/citation/_adapter", () => ({
	Popover: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	PopoverTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	PopoverContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

import React from "react";
import { openSafeNavigationHref } from "@/components/tool-ui/shared/media";
import { Citation } from "@/components/tool-ui/citation/citation";

const BASE_PROPS = {
	id: "cite-1",
	href: "https://example.com/article",
	title: "Example Article",
	snippet: "This is a test snippet",
	domain: "example.com",
};

describe("Citation — click behavior (FE-4)", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	// ------------------------------------------------------------------
	// FE-4: onNavigate callback
	// ------------------------------------------------------------------

	it("FE-4: inline citation click → calls onNavigate with href and citation data", async () => {
		const user = userEvent.setup();
		const onNavigate = vi.fn();

		render(<Citation {...BASE_PROPS} variant="inline" onNavigate={onNavigate} />);

		await user.click(screen.getByRole("button"));

		expect(onNavigate).toHaveBeenCalledWith(
			"https://example.com/article",
			expect.objectContaining({ href: "https://example.com/article" })
		);
	});

	it("FE-4: default citation click → calls onNavigate when provided", async () => {
		const user = userEvent.setup();
		const onNavigate = vi.fn();

		render(<Citation {...BASE_PROPS} variant="default" onNavigate={onNavigate} />);

		// Default variant renders a div with role="link" when href is present
		const link = screen.getByRole("link");
		await user.click(link);

		expect(onNavigate).toHaveBeenCalledWith(
			"https://example.com/article",
			expect.objectContaining({ href: "https://example.com/article" })
		);
	});

	// ------------------------------------------------------------------
	// FE-4: openSafeNavigationHref fallback
	// ------------------------------------------------------------------

	it("FE-4: inline citation click → calls openSafeNavigationHref when no onNavigate", async () => {
		const user = userEvent.setup();

		render(<Citation {...BASE_PROPS} variant="inline" />);

		await user.click(screen.getByRole("button"));

		expect(openSafeNavigationHref).toHaveBeenCalledWith("https://example.com/article");
	});

	it("FE-4: default citation click → calls openSafeNavigationHref when no onNavigate", async () => {
		const user = userEvent.setup();

		render(<Citation {...BASE_PROPS} variant="default" />);

		const link = screen.getByRole("link");
		await user.click(link);

		expect(openSafeNavigationHref).toHaveBeenCalledWith("https://example.com/article");
	});

	// ------------------------------------------------------------------
	// FE-4: No-op when no href
	// ------------------------------------------------------------------

	it("does not call onNavigate when href is empty", async () => {
		const user = userEvent.setup();
		const onNavigate = vi.fn();

		render(<Citation {...BASE_PROPS} href="" variant="inline" onNavigate={onNavigate} />);

		await user.click(screen.getByRole("button"));

		expect(onNavigate).not.toHaveBeenCalled();
		expect(openSafeNavigationHref).not.toHaveBeenCalled();
	});

	// ------------------------------------------------------------------
	// FE-4: Rendering
	// ------------------------------------------------------------------

	it("renders citation title", () => {
		render(<Citation {...BASE_PROPS} variant="default" />);
		expect(screen.getByText("Example Article")).toBeInTheDocument();
	});

	it("inline variant renders a button with data-tool-ui-id", () => {
		render(<Citation {...BASE_PROPS} variant="inline" />);
		const btn = screen.getByRole("button");
		expect(btn).toHaveAttribute("data-tool-ui-id", "cite-1");
	});
});
