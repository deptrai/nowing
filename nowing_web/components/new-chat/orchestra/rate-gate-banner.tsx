"use client";

import { Timer } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { type RateGateEvent } from "@/atoms/chat/orchestra.atom";

interface RateGateBannerProps {
	/** Most recent rate-gate wait event, or null when idle. */
	latestGate: RateGateEvent | null;
	className?: string;
}

const REASON_LABELS: Record<string, string> = {
	min_interval: "standard",
	paced: "paced",
	retry: "retry",
};

/** AC9: auto-dismiss after this many ms of no new gate event. */
const AUTO_DISMISS_MS = 15_000;

/**
 * Educational banner shown when the orchestrator is throttling LLM calls.
 * Framed as "system working correctly" — not an error state — to reduce user anxiety.
 * AC9: Auto-dismisses 15s after the most recent gate event.
 */
export function RateGateBanner({ latestGate, className }: RateGateBannerProps) {
	const [dismissed, setDismissed] = useState(false);

	// Reset dismissal when a new gate event arrives.
	useEffect(() => {
		setDismissed(false);
		if (!latestGate) return;
		const elapsed = Date.now() - latestGate.ts;
		const remaining = AUTO_DISMISS_MS - elapsed;
		if (remaining <= 0) {
			setDismissed(true);
			return;
		}
		const timer = setTimeout(() => setDismissed(true), remaining);
		return () => clearTimeout(timer);
	}, [latestGate]);

	if (!latestGate || dismissed) return null;

	const reasonLabel = REASON_LABELS[latestGate.reason] ?? latestGate.reason;
	const waitSec = latestGate.waitSeconds.toFixed(1);

	return (
		<div
			className={cn(
				"flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600 dark:text-amber-400",
				className
			)}
			role="status"
			aria-live="polite"
			data-slot="rate-gate-banner"
		>
			<Timer className="mt-px size-3.5 shrink-0" aria-hidden="true" />
			<span>
				Pacing calls to protect provider quota · Next dispatch in{" "}
				<span className="tabular-nums font-medium">{waitSec}s</span>
				{" · "}
				<span className="text-amber-500/80">{reasonLabel}</span>
			</span>
		</div>
	);
}
