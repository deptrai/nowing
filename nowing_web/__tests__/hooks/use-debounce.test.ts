/**
 * Unit tests for hooks/use-debounce.ts
 * Tests the debounce hook with real timers via vi.useFakeTimers.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/hooks/use-debounce";

describe("useDebounce", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("returns initial value immediately", () => {
		const { result } = renderHook(() => useDebounce("hello", 300));
		expect(result.current).toBe("hello");
	});

	it("does not update debounced value before delay elapses", () => {
		const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
			initialProps: { value: "first" },
		});

		rerender({ value: "second" });

		act(() => {
			vi.advanceTimersByTime(299);
		});

		expect(result.current).toBe("first");
	});

	it("updates debounced value after delay elapses", () => {
		const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
			initialProps: { value: "first" },
		});

		rerender({ value: "second" });

		act(() => {
			vi.advanceTimersByTime(300);
		});

		expect(result.current).toBe("second");
	});

	it("resets timer on rapid consecutive updates (only last value wins)", () => {
		const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
			initialProps: { value: "a" },
		});

		rerender({ value: "b" });
		act(() => { vi.advanceTimersByTime(100); });
		rerender({ value: "c" });
		act(() => { vi.advanceTimersByTime(100); });
		rerender({ value: "d" });
		act(() => { vi.advanceTimersByTime(100); });

		// Only 300ms total since last change → not yet updated
		expect(result.current).toBe("a");

		act(() => { vi.advanceTimersByTime(200); }); // now 300ms since "d"
		expect(result.current).toBe("d");
	});

	it("uses 500ms default delay", () => {
		const { result, rerender } = renderHook(({ value }) => useDebounce(value), {
			initialProps: { value: "initial" },
		});

		rerender({ value: "updated" });

		act(() => { vi.advanceTimersByTime(499); });
		expect(result.current).toBe("initial");

		act(() => { vi.advanceTimersByTime(1); });
		expect(result.current).toBe("updated");
	});

	it("handles number values", () => {
		const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), {
			initialProps: { value: 0 },
		});

		rerender({ value: 42 });

		act(() => { vi.advanceTimersByTime(200); });
		expect(result.current).toBe(42);
	});

	it("cancels timer on unmount (no state updates after unmount)", () => {
		const { result, rerender, unmount } = renderHook(({ value }) => useDebounce(value, 300), {
			initialProps: { value: "a" },
		});

		rerender({ value: "b" });
		unmount();

		// Advancing timers after unmount should not throw
		act(() => { vi.advanceTimersByTime(300); });
		// No assertion needed — just verifying no error / act warning
		expect(result.current).toBe("a"); // last rendered value before unmount
	});
});
