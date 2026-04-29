"use client";

import { cn } from "@/lib/utils";
import { type AgentStatus } from "@/atoms/chat/orchestra.atom";

interface StatusLightProps {
	status: AgentStatus;
	className?: string;
}

const STATUS_CONFIG: Record<AgentStatus, { color: string; pulse: boolean; label: string }> = {
	idle: { color: "bg-muted", pulse: false, label: "Idle" },
	queued: { color: "bg-muted-foreground/40", pulse: false, label: "Queued" },
	running: { color: "bg-emerald-500", pulse: true, label: "Running" },
	done: { color: "bg-emerald-500", pulse: false, label: "Done" },
	failed: { color: "bg-amber-500", pulse: false, label: "Failed" },
	cancelled: { color: "bg-muted-foreground/40", pulse: false, label: "Cancelled" },
};

export function StatusLight({ status, className }: StatusLightProps) {
	const config = STATUS_CONFIG[status];
	return (
		<span
			className={cn("relative flex size-2 shrink-0", className)}
			aria-label={config.label}
			role="status"
		>
			{config.pulse && (
				<span
					className={cn(
						"absolute inline-flex size-full animate-ping rounded-full opacity-75",
						config.color
					)}
				/>
			)}
			<span className={cn("relative inline-flex size-2 rounded-full", config.color)} />
		</span>
	);
}
