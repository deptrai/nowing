/**
 * Unit tests for hooks/use-typewriter.ts
 * Tests the typewriter animation hook.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTypewriter } from "@/hooks/use-typewriter";

describe("useTypewriter", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	// ------------------------------------------------------------------
	// No animation cases
	// ------------------------------------------------------------------

	it("returns text immediately when prev text was not the skip sentinel", () => {
		const { result } = renderHook(() => useTypewriter("Hello"));
		// prev === "New Chat" (initial = text passed), so prevText starts as "Hello"
		// Since prevText !== skipFor ("New Chat") → no animation → displays immediately
		expect(result.current).toBe("Hello");
	});

	it("returns new text immediately when text changes but prev != skipFor", () => {
		const { result, rerender } = renderHook(({ text }) => useTypewriter(text), {
			initialProps: { text: "First" },
		});

		rerender({ text: "Second" });
		// prevText was "First" which is not "New Chat" → immediate update
		expect(result.current).toBe("Second");
	});

	it("returns empty string initially when text is empty", () => {
		const { result } = renderHook(() => useTypewriter(""));
		expect(result.current).toBe("");
	});

	// ------------------------------------------------------------------
	// Animation: prev === "New Chat" → triggers typewriter
	// ------------------------------------------------------------------

	it("starts with empty string when transitioning from 'New Chat'", () => {
		// Start at "New Chat" (the skip sentinel)
		const { result, rerender } = renderHook(({ text }) => useTypewriter(text), {
			initialProps: { text: "New Chat" },
		});

		rerender({ text: "Hello" });

		// Immediately after update, displayed should be "" (animation starting)
		expect(result.current).toBe("");
	});

	it("reveals characters one at a time via setInterval", () => {
		const SPEED = 35;
		const { result, rerender } = renderHook(({ text }) => useTypewriter(text, SPEED), {
			initialProps: { text: "New Chat" },
		});

		rerender({ text: "Hi" });

		act(() => { vi.advanceTimersByTime(SPEED); });
		expect(result.current).toBe("H");

		act(() => { vi.advanceTimersByTime(SPEED); });
		expect(result.current).toBe("Hi");
	});

	it("shows full text after all intervals fire", () => {
		const text = "Hello";
		const SPEED = 20;
		const { result, rerender } = renderHook(({ t }) => useTypewriter(t, SPEED), {
			initialProps: { t: "New Chat" },
		});

		rerender({ t: text });

		act(() => { vi.advanceTimersByTime(SPEED * text.length); });
		expect(result.current).toBe("Hello");
	});

	it("clears interval after fully revealing text", () => {
		const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
		const text = "Hi";
		const SPEED = 30;

		const { rerender } = renderHook(({ t }) => useTypewriter(t, SPEED), {
			initialProps: { t: "New Chat" },
		});

		rerender({ t: text });

		act(() => { vi.advanceTimersByTime(SPEED * text.length); });

		expect(clearIntervalSpy).toHaveBeenCalled();
		clearIntervalSpy.mockRestore();
	});

	// ------------------------------------------------------------------
	// Custom skipFor
	// ------------------------------------------------------------------

	it("respects custom skipFor sentinel", () => {
		const { result, rerender } = renderHook(
			({ text, skipFor }) => useTypewriter(text, 35, skipFor),
			{ initialProps: { text: "LOADING", skipFor: "LOADING" } }
		);

		rerender({ text: "Done", skipFor: "LOADING" });

		// prev === "LOADING" === skipFor → animation triggers
		expect(result.current).toBe("");
	});

	it("does not animate when skipFor is changed to different value", () => {
		const { result, rerender } = renderHook(
			({ text, skipFor }) => useTypewriter(text, 35, skipFor),
			{ initialProps: { text: "Initial", skipFor: "OTHER" } }
		);

		rerender({ text: "New", skipFor: "OTHER" });

		// prev was "Initial" ≠ "OTHER" → no animation
		expect(result.current).toBe("New");
	});

	// ------------------------------------------------------------------
	// Interruption / cleanup
	// ------------------------------------------------------------------

	it("clears interval on unmount during animation", () => {
		const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
		const SPEED = 35;

		const { rerender, unmount } = renderHook(({ t }) => useTypewriter(t, SPEED), {
			initialProps: { t: "New Chat" },
		});

		rerender({ t: "Hello World" });

		act(() => { vi.advanceTimersByTime(SPEED * 2); }); // mid-animation

		unmount();

		expect(clearIntervalSpy).toHaveBeenCalled();
		clearIntervalSpy.mockRestore();
	});

	it("restarts animation when text changes mid-animation", () => {
		const SPEED = 35;
		const { result, rerender } = renderHook(({ t }) => useTypewriter(t, SPEED), {
			initialProps: { t: "New Chat" },
		});

		rerender({ t: "First" });
		act(() => { vi.advanceTimersByTime(SPEED); }); // partial: "F"
		expect(result.current).toBe("F");

		// Interrupting with a new text from "First" (not skipFor) → immediate
		rerender({ t: "Second" });
		expect(result.current).toBe("Second");
	});
});
