"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageBreakdownItem } from "@/contracts/types/usage.types";

function formatUsdMicros(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars === 0) return "$0";
	if (Math.abs(dollars) >= 1) return `$${dollars.toFixed(2)}`;
	return `$${dollars.toFixed(3)}`;
}

interface UsageBreakdownProps {
	byUsageType: UsageBreakdownItem[];
	byModel: UsageBreakdownItem[];
	byProvider: UsageBreakdownItem[];
	isLoading: boolean;
}

export function UsageBreakdown({
	byUsageType,
	byModel,
	byProvider,
	isLoading,
}: UsageBreakdownProps) {
	const t = useTranslations("usage");

	return (
		<Card>
			<CardHeader>
				<CardTitle>{t("breakdown_title")}</CardTitle>
				<CardDescription>{t("breakdown_description")}</CardDescription>
			</CardHeader>
			<CardContent className="space-y-6">
				<BreakdownSection title={t("by_usage_type")} items={byUsageType} isLoading={isLoading} />
				<BreakdownSection title={t("by_model")} items={byModel} isLoading={isLoading} />
				<BreakdownSection title={t("by_provider")} items={byProvider} isLoading={isLoading} />
			</CardContent>
		</Card>
	);
}

function BreakdownSection({
	title,
	items,
	isLoading,
}: {
	title: string;
	items: UsageBreakdownItem[];
	isLoading: boolean;
}) {
	const t = useTranslations("usage");

	return (
		<div>
			<h4 className="mb-2 text-sm font-semibold">{title}</h4>
			{isLoading ? (
				<Skeleton className="h-20 w-full" />
			) : items.length === 0 ? (
				<p className="text-sm text-muted-foreground">{t("no_data")}</p>
			) : (
				<ul className="space-y-1">
					{items.map((item) => (
						<li key={item.key} className="flex items-center justify-between text-sm">
							<span className="truncate" title={item.key}>
								{item.key}
							</span>
							<span className="ml-4 shrink-0 tabular-nums text-muted-foreground">
								{formatUsdMicros(item.cost_micros)} · {item.total_tokens.toLocaleString()}{" "}
								{t("tokens_suffix")}
							</span>
						</li>
					))}
				</ul>
			)}
		</div>
	);
}
