"use client";

import { cn } from "@/lib/utils";
import { type RateGateEvent } from "@/atoms/chat/orchestra.atom";

interface LlmCallEvent {
	ts: number;
	agentId: string;
}

interface ActivityTimelineProps {
	spawnedAt: number;
	rateGateWaits: RateGateEvent[];
	llmCallEvents?: LlmCallEvent[];
	className?: string;
}

/**
 * AC10: Horizontal mini-timeline showing one tick per LLM call (slate)
 * + amber ticks per rate-gate pause. Gate-spacing gaps appear as visual
 * blank space between ticks.
 */
export function ActivityTimeline({
	spawnedAt,
	rateGateWaits,
	llmCallEvents = [],
	className,
}: ActivityTimelineProps) {
	const nowMs = Date.now();
	const totalMs = nowMs - spawnedAt;

	if (totalMs < 500) return null;

	return (
		<div
			className={cn("flex flex-col gap-1", className)}
			data-slot="activity-timeline"
			aria-label="Activity timeline"
		>
			{/* Timeline bar */}
			<div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
				{/* Background fill */}
				<div className="h-full rounded-full bg-muted-foreground/15" style={{ width: "100%" }} />

				{/* AC10: one tick per LLM call (slate) */}
				{llmCallEvents.map((call, i) => {
					const offsetPct = ((call.ts - spawnedAt) / totalMs) * 100;
					if (offsetPct < 0 || offsetPct > 100) return null;
					return (
						<span
							key={`call-${call.ts}-${i}`}
							className="absolute top-0 h-full w-px bg-muted-foreground/60"
							style={{ left: `${Math.min(offsetPct, 99.5)}%` }}
							title={`call #${i + 1} at ${formatClock(call.ts)} · ${call.agentId}`}
						/>
					);
				})}

				{/* Rate-gate pauses (amber, slightly wider) */}
				{rateGateWaits.map((gate, i) => {
					const offsetPct = Math.min(((gate.ts - spawnedAt) / totalMs) * 100, 98);
					if (offsetPct < 0) return null;
					return (
						<span
							key={`gate-${gate.ts}-${i}`}
							className="absolute top-0 h-full w-0.5 bg-amber-400/80"
							style={{ left: `${offsetPct}%` }}
							title={`Pacing ${gate.waitSeconds}s (${gate.reason})`}
						/>
					);
				})}
			</div>

			{/* Legend */}
			{(rateGateWaits.length > 0 || llmCallEvents.length > 0) && (
				<p className="flex items-center gap-2 text-[10px] text-muted-foreground/60">
					{llmCallEvents.length > 0 && (
						<span className="inline-flex items-center gap-1">
							<span className="inline-block size-1 rounded-full bg-muted-foreground/60" />
							{llmCallEvents.length} call{llmCallEvents.length > 1 ? "s" : ""}
						</span>
					)}
					{rateGateWaits.length > 0 && (
						<span className="inline-flex items-center gap-1">
							<span className="inline-block size-1.5 rounded-full bg-amber-400/80" />
							{rateGateWaits.length} pause{rateGateWaits.length > 1 ? "s" : ""}
						</span>
					)}
				</p>
			)}
		</div>
	);
}

function formatClock(ts: number): string {
	const d = new Date(ts);
	return `${d.getHours().toString().padStart(2, "0")}:${d
		.getMinutes()
		.toString()
		.padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}
