import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProContentGate } from "@/components/crypto/ProContentGate";
import { useSubscriptionGate } from "@/hooks/use-subscription-gate";

vi.mock("@/hooks/use-subscription-gate", () => ({
	useSubscriptionGate: vi.fn(),
}));

const mockGate = (state: { isPro: boolean; isLoading?: boolean }) => {
	(useSubscriptionGate as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
		isPro: state.isPro,
		isLoading: state.isLoading ?? false,
	});
};

/**
 * `navigator.onLine` setter helper. Returned function restores the previous
 * value — pair with `try/finally` (or `afterEach`) so a failed assertion
 * doesn't leak the offline state into subsequent tests.
 */
const setOnline = (online: boolean): (() => void) => {
	const original = navigator.onLine;
	Object.defineProperty(navigator, "onLine", { value: online, configurable: true });
	return () => {
		Object.defineProperty(navigator, "onLine", { value: original, configurable: true });
	};
};

afterEach(() => {
	(useSubscriptionGate as unknown as ReturnType<typeof vi.fn>).mockReset();
});

describe("ProContentGate", () => {
	it("renders children when user is Pro", () => {
		mockGate({ isPro: true });

		render(
			<ProContentGate>
				<div data-testid="protected-content">Secret Data</div>
			</ProContentGate>,
		);

		expect(screen.getByTestId("protected-content")).toBeDefined();
		expect(screen.queryByText(/Upgrade to Pro/i)).toBeNull();
	});

	it("renders upgrade prompt when user is not Pro", () => {
		mockGate({ isPro: false });

		render(
			<ProContentGate>
				<div data-testid="protected-content">Secret Data</div>
			</ProContentGate>,
		);

		expect(screen.getAllByText(/Upgrade to Pro/i).length).toBeGreaterThan(0);
		expect(screen.getByTestId("protected-content")).toBeDefined();
	});

	// Round-2 review: blurred subtree must be `inert` + `aria-hidden` so a free
	// user cannot Tab into interactive controls behind the blur and trigger
	// paid actions (the documented bypass).
	it("marks gated children as inert + aria-hidden when not Pro", () => {
		mockGate({ isPro: false });

		render(
			<ProContentGate>
				<button type="button" data-testid="hidden-button">
					Trigger Paid Action
				</button>
			</ProContentGate>,
		);

		const button = screen.getByTestId("hidden-button");
		const wrapper = button.closest('[aria-hidden="true"]');
		expect(wrapper).not.toBeNull();
		expect(wrapper?.getAttribute("inert")).not.toBeNull();
		expect(wrapper?.getAttribute("tabIndex")).toBe("-1");
	});

	// Round-2 review (anti-pattern fix): no skeleton flash. While the user
	// record is loading the component renders the redacted view directly so
	// the page is never blocked. Once the atom resolves, isPro flips and the
	// gate unblurs.
	it("renders the redacted view immediately while loading, never a skeleton", () => {
		mockGate({ isPro: false, isLoading: true });

		const { container } = render(
			<ProContentGate>
				<div data-testid="protected-content">Secret Data</div>
			</ProContentGate>,
		);

		expect(screen.getAllByText(/Upgrade to Pro/i).length).toBeGreaterThan(0);
		expect(screen.getByTestId("protected-content")).toBeDefined();
		expect(container.querySelector(".animate-pulse")).toBeNull();
	});

	it("renders children when offline (AC#6)", () => {
		mockGate({ isPro: false });
		const restore = setOnline(false);

		try {
			render(
				<ProContentGate>
					<div data-testid="protected-content">Secret Data</div>
				</ProContentGate>,
			);

			expect(screen.getByTestId("protected-content")).toBeDefined();
			expect(screen.queryByText(/Upgrade to Pro/i)).toBeNull();
		} finally {
			restore();
		}
	});

	it("when online + not Pro, gate engages (offline path is the exception)", () => {
		mockGate({ isPro: false });
		const restore = setOnline(true);

		try {
			render(
				<ProContentGate>
					<div data-testid="protected-content">Secret Data</div>
				</ProContentGate>,
			);

			expect(screen.getAllByText(/Upgrade to Pro/i).length).toBeGreaterThan(0);
		} finally {
			restore();
		}
	});
});
