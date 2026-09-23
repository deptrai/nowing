"use client";
import { AlertCircle, CheckCircle2, Clock, Loader2, TimerOff, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { RunStatus } from "@/contracts/types/automation.types";
import { cn } from "@/lib/utils";

function getStatusStyles(
	t: (k: string) => string
): Record<
	RunStatus,
	{ label: string; icon: typeof CheckCircle2; classes: string; spin?: boolean }
> {
	return {
		pending: {
			label: t("auto_pending"),
			icon: Clock,
			classes: "bg-muted text-muted-foreground border-border/60",
		},
		running: {
			label: t("auto_running"),
			icon: Loader2,
			classes: "bg-blue-500/10 text-blue-600 border-blue-500/20",
			spin: true,
		},
		succeeded: {
			label: t("auto_succeeded"),
			icon: CheckCircle2,
			classes: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
		},
		failed: {
			label: t("auto_failed"),
			icon: XCircle,
			classes: "bg-destructive/10 text-destructive border-destructive/20",
		},
		cancelled: {
			label: t("auto_cancelled"),
			icon: AlertCircle,
			classes: "bg-muted text-muted-foreground border-border/60",
		},
		timed_out: {
			label: t("auto_timed_out"),
			icon: TimerOff,
			classes: "bg-amber-500/10 text-amber-600 border-amber-500/20",
		},
	};
}

export function RunStatusBadge({ status, className }: { status: RunStatus; className?: string }) {
	const t = useTranslations("automations");
	const { label, icon: Icon, classes, spin } = getStatusStyles(t)[status];
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
				classes,
				className
			)}
		>
			<Icon className={cn("h-3 w-3", spin && "animate-spin")} aria-hidden />
			{label}
		</span>
	);
}
