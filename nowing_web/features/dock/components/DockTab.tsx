"use client";

import { cn } from "@/lib/utils";

export interface DockTabProps {
	label: string;
	isActive: boolean;
	hasUpdate: boolean;
	onClick: () => void;
}

export function DockTab({ label, isActive, hasUpdate, onClick }: DockTabProps) {
	return (
		<button
			type="button"
			onClick={onClick}
			className={cn(
				"relative inline-flex items-center gap-1.5 shrink-0 whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium transition-all",
				"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
				isActive
					? "bg-background text-foreground shadow-xs border border-border/80"
					: "text-muted-foreground hover:text-foreground hover:bg-muted/60",
				hasUpdate && !isActive && "ring-1 ring-emerald-500/60 animate-pulse"
			)}
		>
			<span className="truncate max-w-[120px]">{label}</span>
			{hasUpdate && !isActive && (
				<span className="size-1.5 rounded-full bg-emerald-500" aria-hidden />
			)}
		</button>
	);
}
