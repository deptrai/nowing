"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, CreditCard, DollarSign, Wallet } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type UsageDateRange, usageApiService } from "@/lib/apis/usage-api.service";
import { UsageDateRangePicker } from "./date-range-picker";
import { UsageBreakdown } from "./usage-breakdown";
import { UsageChart } from "./usage-chart";
import { UsageTransactions } from "./usage-transactions";

function formatUsd(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars === 0) return "$0.00";
	if (Math.abs(dollars) >= 100) return `$${dollars.toFixed(0)}`;
	if (Math.abs(dollars) >= 1) return `$${dollars.toFixed(2)}`;
	return `$${dollars.toFixed(3)}`;
}

function formatNumber(value: number): string {
	return new Intl.NumberFormat().format(value);
}

type Granularity = "day" | "week" | "month";

export function UsageContent() {
	const t = useTranslations("usage");
	const params = useParams();
	const rawWorkspaceId = Number(params.workspace_id);
	const workspaceId = Number.isFinite(rawWorkspaceId) && rawWorkspaceId > 0 ? rawWorkspaceId : 0;

	const [range, setRange] = useState<UsageDateRange>(() => {
		const end = new Date().toISOString();
		const start = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
		return { start, end };
	});
	const [granularity, setGranularity] = useState<Granularity>("day");

	const { data: summary, isLoading: isSummaryLoading } = useQuery({
		queryKey: ["usage", "summary", workspaceId, range],
		queryFn: () => usageApiService.getSummary(workspaceId, range),
		enabled: workspaceId > 0,
	});

	const { data: timeSeries, isLoading: isTimeSeriesLoading } = useQuery({
		queryKey: ["usage", "time-series", workspaceId, granularity, range],
		queryFn: () => usageApiService.getTimeSeries(workspaceId, granularity, range),
		enabled: workspaceId > 0,
	});

	const { data: transactions, isLoading: isTransactionsLoading } = useQuery({
		queryKey: ["usage", "transactions"],
		queryFn: () => usageApiService.getTransactions(),
	});

	const hasUsage = useMemo(
		() => (summary?.total_tokens ?? 0) > 0 || (summary?.total_cost_micros ?? 0) > 0,
		[summary]
	);

	if (!workspaceId) {
		return (
			<div className="flex min-h-[20rem] items-center justify-center">
				<p className="text-muted-foreground">{t("invalid_workspace")}</p>
			</div>
		);
	}

	return (
		<div className="space-y-6 px-4 md:px-0">
			<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
					<p className="text-sm text-muted-foreground">{t("subtitle")}</p>
				</div>
				<UsageDateRangePicker value={range} onChange={setRange} />
			</div>

			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<SummaryCard
					title={t("balance_title")}
					icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
					value={isSummaryLoading ? undefined : formatUsd(summary?.current_balance_micros ?? 0)}
					description={t("balance_description")}
				/>
				<SummaryCard
					title={t("reserved_title")}
					icon={<CreditCard className="h-4 w-4 text-muted-foreground" />}
					value={isSummaryLoading ? undefined : formatUsd(summary?.reserved_micros ?? 0)}
					description={t("reserved_description")}
				/>
				<SummaryCard
					title={t("tokens_title")}
					icon={<BarChart3 className="h-4 w-4 text-muted-foreground" />}
					value={isSummaryLoading ? undefined : formatNumber(summary?.total_tokens ?? 0)}
					description={t("range_description")}
				/>
				<SummaryCard
					title={t("cost_title")}
					icon={<DollarSign className="h-4 w-4 text-muted-foreground" />}
					value={isSummaryLoading ? undefined : formatUsd(summary?.total_cost_micros ?? 0)}
					description={t("range_description")}
				/>
			</div>

			{!isSummaryLoading && !hasUsage && (
				<Card>
					<CardContent className="flex flex-col items-center justify-center py-12 text-center">
						<BarChart3 className="h-12 w-12 text-muted-foreground/50" />
						<h3 className="mt-4 text-lg font-semibold">{t("empty_title")}</h3>
						<p className="mt-1 max-w-sm text-sm text-muted-foreground">{t("empty_description")}</p>
					</CardContent>
				</Card>
			)}

			<div className="grid gap-6 lg:grid-cols-3">
				<Card className="lg:col-span-2">
					<CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
						<div>
							<CardTitle>{t("chart_title")}</CardTitle>
							<CardDescription>{t("chart_description")}</CardDescription>
						</div>
						<Tabs
							value={granularity}
							onValueChange={(value) => setGranularity(value as Granularity)}
						>
							<TabsList>
								<TabsTrigger value="day">{t("granularity_day")}</TabsTrigger>
								<TabsTrigger value="week">{t("granularity_week")}</TabsTrigger>
								<TabsTrigger value="month">{t("granularity_month")}</TabsTrigger>
							</TabsList>
						</Tabs>
					</CardHeader>
					<CardContent>
						<UsageChart data={timeSeries?.points ?? []} isLoading={isTimeSeriesLoading} />
					</CardContent>
				</Card>

				<UsageBreakdown
					byUsageType={summary?.by_usage_type ?? []}
					byModel={summary?.by_model ?? []}
					byProvider={summary?.by_provider ?? []}
					isLoading={isSummaryLoading}
				/>
			</div>

			<UsageTransactions
				transactions={transactions?.transactions ?? []}
				isLoading={isTransactionsLoading}
			/>
		</div>
	);
}

function SummaryCard({
	title,
	icon,
	value,
	description,
}: {
	title: string;
	icon: React.ReactNode;
	value: string | undefined;
	description: string;
}) {
	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between pb-2">
				<CardTitle className="text-sm font-medium">{title}</CardTitle>
				{icon}
			</CardHeader>
			<CardContent>
				{value === undefined ? (
					<Skeleton className="h-8 w-24" />
				) : (
					<div className="text-2xl font-bold tabular-nums">{value}</div>
				)}
				<p className="text-xs text-muted-foreground">{description}</p>
			</CardContent>
		</Card>
	);
}
