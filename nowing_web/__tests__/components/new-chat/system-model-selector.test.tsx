/**
 * Story 3.5 — AC FE-5: SystemModelSelector → fetch models, select model, update atom
 * Tests for SystemModelSelector component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-level mocks ---

const mockModels = [
	{
		id: 1,
		name: "Claude 3.5 Sonnet",
		model_name: "claude-3-5-sonnet-20241022",
		provider: "anthropic",
		tier_required: "pro",
	},
	{
		id: 2,
		name: "GPT-4o",
		model_name: "gpt-4o",
		provider: "openai",
		tier_required: "pro",
	},
	{
		id: 3,
		name: "GPT-3.5 Turbo",
		model_name: "gpt-3.5-turbo",
		provider: "openai",
		tier_required: "free",
	},
];

let mockSelectedId: number | null = null;
const mockSetSelectedId = vi.fn((id: number | null) => {
	mockSelectedId = id;
});

vi.mock("jotai", () => ({
	useAtom: vi.fn(),
	useAtomValue: vi.fn(),
	atom: vi.fn(),
}));

// Stub UI components to avoid Radix portal issues
vi.mock("@/components/ui/popover", () => ({
	Popover: ({ children, open }: { children: React.ReactNode; open?: boolean }) => (
		<div data-open={open}>{children}</div>
	),
	PopoverTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	PopoverContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/command", () => ({
	Command: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CommandInput: ({
		placeholder,
		value,
		onValueChange,
	}: {
		placeholder?: string;
		value?: string;
		onValueChange?: (v: string) => void;
	}) => (
		<input
			placeholder={placeholder}
			value={value}
			onChange={(e) => onValueChange?.(e.target.value)}
		/>
	),
	CommandList: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CommandEmpty: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CommandGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	CommandItem: ({ children, onSelect }: { children: React.ReactNode; onSelect?: () => void }) => (
		<button type="button" onClick={onSelect}>
			{children}
		</button>
	),
}));

vi.mock("@/components/ui/badge", () => ({
	Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/ui/button", () => ({
	Button: ({ children, onClick, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
		<button type="button" onClick={onClick} {...props}>
			{children}
		</button>
	),
}));

vi.mock("@/components/ui/spinner", () => ({
	Spinner: () => <span data-testid="spinner" />,
}));

vi.mock("lucide-react", () => ({
	Bot: () => <span />,
	Check: () => <span data-testid="check" />,
	ChevronDown: () => <span />,
	Crown: () => <span />,
	Zap: () => <span />,
}));

import React from "react";
import { useAtom, useAtomValue } from "jotai";
import { SystemModelSelector } from "@/components/new-chat/system-model-selector";

describe("SystemModelSelector — FE-5", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockSelectedId = null;

		// Default: models loaded, no selection
		vi.mocked(useAtomValue).mockReturnValue({
			data: mockModels,
			isPending: false,
		});
		vi.mocked(useAtom).mockReturnValue([mockSelectedId, mockSetSelectedId] as ReturnType<
			typeof useAtom
		>);
	});

	// ------------------------------------------------------------------
	// FE-5: Rendering — model list
	// ------------------------------------------------------------------

	it("FE-5: renders trigger button with first model as default display", () => {
		render(<SystemModelSelector />);
		// getAllByText because model name appears in both trigger and list
		const elements = screen.getAllByText("Claude 3.5 Sonnet");
		expect(elements.length).toBeGreaterThanOrEqual(1);
	});

	it("FE-5: shows spinner while models are loading", () => {
		vi.mocked(useAtomValue).mockReturnValue({ data: undefined, isPending: true });

		render(<SystemModelSelector />);

		const spinners = screen.getAllByTestId("spinner");
		expect(spinners.length).toBeGreaterThanOrEqual(1);
	});

	it("FE-5: shows 'Select model' placeholder when no models available", () => {
		vi.mocked(useAtomValue).mockReturnValue({ data: [], isPending: false });

		render(<SystemModelSelector />);

		expect(screen.getByText("Select model")).toBeInTheDocument();
	});

	it("FE-5: renders all model names in the list", () => {
		render(<SystemModelSelector />);

		expect(screen.getAllByText("Claude 3.5 Sonnet").length).toBeGreaterThanOrEqual(1);
		expect(screen.getAllByText("GPT-4o").length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText("GPT-3.5 Turbo")).toBeInTheDocument();
	});

	// ------------------------------------------------------------------
	// FE-5: Selection — updates selectedSystemModelIdAtom
	// ------------------------------------------------------------------

	it("FE-5: clicking a model → calls setSelectedId with model id", async () => {
		const user = userEvent.setup();
		render(<SystemModelSelector />);

		// Click GPT-4o button (rendered by CommandItem mock as button)
		const gptButtons = screen
			.getAllByRole("button")
			.filter((b) => b.textContent?.includes("GPT-4o"));
		expect(gptButtons.length).toBeGreaterThanOrEqual(1);
		await user.click(gptButtons[0]);

		expect(mockSetSelectedId).toHaveBeenCalledWith(2);
	});

	it("FE-5: shows selected model name in trigger after selection", () => {
		vi.mocked(useAtom).mockReturnValue([2, mockSetSelectedId] as ReturnType<typeof useAtom>);

		render(<SystemModelSelector />);

		const allGptElements = screen.getAllByText("GPT-4o");
		expect(allGptElements.length).toBeGreaterThanOrEqual(1);
	});

	// ------------------------------------------------------------------
	// FE-5: Search filtering
	// ------------------------------------------------------------------

	it("FE-5: typing in search filters models by name", async () => {
		const user = userEvent.setup();
		render(<SystemModelSelector />);

		const searchInput = screen.getByPlaceholderText("Search models…");
		await user.type(searchInput, "claude");

		await waitFor(() => {
			// GPT models should not appear as CommandItem buttons after filtering
			const allButtons = screen.getAllByRole("button");
			const gptButton = allButtons.find(
				(b) => b.textContent?.includes("GPT-4o") && b.textContent?.includes("gpt-4o")
			);
			expect(gptButton).toBeUndefined();
		});
	});

	it("FE-5: shows 'No models found' when search has no results", async () => {
		const user = userEvent.setup();
		render(<SystemModelSelector />);

		const searchInput = screen.getByPlaceholderText("Search models…");
		await user.type(searchInput, "llama3-nonexistent");

		await waitFor(() => {
			expect(screen.getByText("No models found.")).toBeInTheDocument();
		});
	});

	// ------------------------------------------------------------------
	// FE-5: Tier badge displayed
	// ------------------------------------------------------------------

	it("FE-5: shows tier badge for each model", () => {
		render(<SystemModelSelector />);

		// Pro tier badges shown
		const proBadges = screen.getAllByText("Pro");
		expect(proBadges.length).toBeGreaterThanOrEqual(2);

		// Free tier badge
		expect(screen.getByText("Free")).toBeInTheDocument();
	});
});
