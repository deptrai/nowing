"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import type {
	ScenarioAssumptions,
	ScenarioResult,
	ScenarioType,
} from "@/components/new-chat/simulator/scenario-simulator-panel";

interface UseScenarioResynthesizeOptions {
	threadId: number | null;
	token: string | null;
}

interface UseScenarioResynthesizeReturn {
	activeScenario: ScenarioType;
	scenarioResult: ScenarioResult | null;
	isResynthesizing: boolean;
	resynthesize: (scenario: ScenarioType, assumptions: ScenarioAssumptions) => void;
	resetToBase: () => void;
}

const BACKEND_URL =
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ||
	(process.env.NODE_ENV === "production"
		? (() => {
				throw new Error("NEXT_PUBLIC_FASTAPI_BACKEND_URL is required in production");
			})()
		: "http://localhost:8000");

export function useScenarioResynthesize({
	threadId,
	token,
}: UseScenarioResynthesizeOptions): UseScenarioResynthesizeReturn {
	const [activeScenario, setActiveScenario] = useState<ScenarioType>("base");
	const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
	const [isResynthesizing, setIsResynthesizing] = useState(false);
	const abortRef = useRef<AbortController | null>(null);

	const resynthesize = useCallback(
		async (scenario: ScenarioType, assumptions: ScenarioAssumptions) => {
			if (!threadId || !token || scenario === "base") return;

			// Abort any in-flight request — last click wins
			abortRef.current?.abort();
			const ctrl = new AbortController();
			abortRef.current = ctrl;

			setIsResynthesizing(true);
			setActiveScenario(scenario);

			let accumulated = "";

			try {
				const response = await fetch(`${BACKEND_URL}/api/v1/scenarios/resynthesize`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						thread_id: threadId,
						scenario,
						assumptions,
					}),
					signal: ctrl.signal,
				});

				if (!response.ok || !response.body) {
					throw new Error(`HTTP ${response.status}`);
				}

				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = "";
				let streamDone = false;

				while (!streamDone) {
					const { done, value } = await reader.read();
					if (done) break;

					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split("\n");
					buffer = lines.pop() ?? "";

					for (const line of lines) {
						if (!line.startsWith("data: ")) continue;
						const raw = line.slice(6);
						if (raw === "[DONE]") {
							streamDone = true;
							break;
						}
						try {
							const parsed = JSON.parse(raw) as { type: string; data?: unknown };
							if (parsed.type === "data-scenario-text-delta") {
								const d = parsed.data as { delta?: unknown };
								if (typeof d?.delta === "string") {
									accumulated += d.delta;
								}
							}
						} catch (parseErr) {
							console.warn("[useScenarioResynthesize] SSE parse", parseErr);
						}
					}
				}

				if (accumulated && !ctrl.signal.aborted) {
					setScenarioResult({
						scenario,
						assumptions,
						content: accumulated,
						loadedAt: Date.now(),
					});
				}
			} catch (err) {
				if ((err as Error).name === "AbortError") return;
				console.error("[useScenarioResynthesize]", err);
				toast.error("Không thể tổng hợp kịch bản. Vui lòng thử lại.");
				setActiveScenario("base");
			} finally {
				if (abortRef.current === ctrl) {
					setIsResynthesizing(false);
				}
			}
		},
		[threadId, token]
	);

	const resetToBase = useCallback(() => {
		abortRef.current?.abort();
		setActiveScenario("base");
		setScenarioResult(null);
	}, []);

	return { activeScenario, scenarioResult, isResynthesizing, resynthesize, resetToBase };
}
