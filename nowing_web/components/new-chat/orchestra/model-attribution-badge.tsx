"use client";

import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModelAttributionBadgeProps {
	model: string;
	provider: string;
	tier?: string;
	className?: string;
}

export function ModelAttributionBadge({
	model,
	provider,
	tier,
	className,
}: ModelAttributionBadgeProps) {
	const shortModel = model.replace(/^claude-/, "").replace(/-\d{8}$/, "");
	const label = tier ? `${shortModel} · ${provider} · ${tier}` : `${shortModel} · ${provider}`;

	return (
		<span
			className={cn(
				"inline-flex items-center gap-1 rounded-full border border-border/50 bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground",
				className
			)}
			title={label}
		>
			<Bot className="size-2.5 shrink-0" aria-hidden="true" />
			<span className="truncate max-w-[120px]">{label}</span>
		</span>
	);
}
