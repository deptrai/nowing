"use client";
import { useTranslations } from "next-intl";
import type { Execution } from "@/contracts/types/automation.types";

interface ExecutionSummaryProps {
	execution: Execution;
}

/**
 * Compact view of an automation's execution defaults (wall-clock cap,
 * retries, backoff, concurrency, on_failure presence). Per-step overrides
 * are shown inside each PlanStepCard, not here.
 */
export function ExecutionSummary({ execution }: ExecutionSummaryProps) {
	const t = useTranslations("automations");
	return (
		<dl className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-xs">
			<Item label={t("auto_timeout")} value={`${execution.timeout_seconds}s`} />
			<Item label={t("auto_max_retries")} value={String(execution.max_retries)} />
			<Item label={t("auto_retry_backoff")} value={formatEnumValue(execution.retry_backoff)} />
			<Item label={t("auto_concurrency")} value={formatEnumValue(execution.concurrency)} />
			{execution.on_failure.length > 0 && (
				<Item
					label={t("auto_on_failure")}
					value={`${execution.on_failure.length} step${execution.on_failure.length === 1 ? "" : "s"}`}
				/>
			)}
		</dl>
	);
}

function formatEnumValue(value: string): string {
	const text = value.replace(/_/g, " ");
	return text.charAt(0).toUpperCase() + text.slice(1);
}

function Item({ label, value }: { label: string; value: string }) {
	return (
		<div className="flex flex-col gap-0.5 min-w-0">
			<dt className="text-muted-foreground">{label}</dt>
			<dd className="text-foreground font-medium truncate">{value}</dd>
		</div>
	);
}
