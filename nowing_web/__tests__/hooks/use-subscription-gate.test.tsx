import { renderHook } from "@testing-library/react";
import { useAtomValue } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSubscriptionGate } from "@/hooks/use-subscription-gate";

// Replace only `useAtomValue`; preserve the rest of jotai's exports so other
// jotai utilities used by the SUT (or transitively) keep working.
vi.mock("jotai", async () => {
	const actual = await vi.importActual<typeof import("jotai")>("jotai");
	return { ...actual, useAtomValue: vi.fn() };
});

const setUser = (data: unknown, opts: Partial<{ isPending: boolean; isError: boolean }> = {}) => {
	(useAtomValue as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
		data,
		isPending: opts.isPending ?? false,
		isError: opts.isError ?? false,
	});
};

afterEach(() => {
	(useAtomValue as unknown as ReturnType<typeof vi.fn>).mockReset();
});

describe("useSubscriptionGate", () => {
	it("returns isPro=true for active pro_monthly plan", () => {
		setUser({ plan_id: "pro_monthly", subscription_status: "active", is_superuser: false });
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(true);
	});

	it("returns isPro=true for superusers regardless of plan", () => {
		setUser({ plan_id: "free", subscription_status: "none", is_superuser: true });
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(true);
	});

	it("returns isPro=false for free plan (Task 4.2)", () => {
		setUser({ plan_id: "free", subscription_status: "none", is_superuser: false });
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);
	});

	// Round-2 review: Task 4.1 explicitly demands an "expired" scenario test —
	// the previous suite only exercised `plan_id="free"` (never-paid case).
	it("returns isPro=false when subscription_status='past_due' (Task 4.1)", () => {
		setUser({
			plan_id: "pro_monthly",
			subscription_status: "past_due",
			is_superuser: false,
		});
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);
	});

	it("returns isPro=false when subscription_status='canceled' AND period_end has passed", () => {
		const expired = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		setUser({
			plan_id: "pro_monthly",
			subscription_status: "canceled",
			subscription_current_period_end: expired,
			is_superuser: false,
		});
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);
	});

	// Round-2 review: cancel-but-still-paid grace window. Stripe flips status
	// to "canceled" the moment the user clicks cancel, but they retain access
	// through `subscription_current_period_end`.
	it("returns isPro=true when canceled but period_end is still in the future", () => {
		const future = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
		setUser({
			plan_id: "pro_monthly",
			subscription_status: "canceled",
			subscription_current_period_end: future,
			is_superuser: false,
		});
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(true);
	});

	it("returns isPro=false when user is missing", () => {
		setUser(null);
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);
	});

	it("surfaces isLoading from atom isPending", () => {
		setUser(null, { isPending: true });
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isLoading).toBe(true);
		expect(result.current.isPro).toBe(false);
	});

	// AC#3: hot reactivity — when the atom updates, the hook re-renders and
	// flips isPro accordingly without needing a page reload. Task 3.2.
	it("re-renders to isPro=true when atom updates from free → pro (AC#3)", () => {
		setUser({ plan_id: "free", subscription_status: "none", is_superuser: false });
		const { result, rerender } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);

		// Simulate the user upgrading: atom emits the updated user record.
		setUser({ plan_id: "pro_yearly", subscription_status: "active", is_superuser: false });
		rerender();

		expect(result.current.isPro).toBe(true);
	});

	it("returns isPro=false when atom is in error state", () => {
		setUser(null, { isError: true });
		const { result } = renderHook(() => useSubscriptionGate());
		expect(result.current.isPro).toBe(false);
	});
});
