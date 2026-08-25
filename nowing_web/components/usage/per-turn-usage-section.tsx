"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3 } from "lucide-react";
import { useTranslations } from "next-intl";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { UsageDateRange } from "@/contracts/types/usage.types";
import { usageApiService } from "@/lib/apis/usage-api.service";

interface PerTurnUsageSectionProps {
	workspaceId: number;
	range: UsageDateRange;
}

function formatUsdMicros(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0";
}

function formatTokens(value: number): string {
	return new Intl.NumberFormat().format(value);
}

function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString();
}

export function PerTurnUsageSection({ workspaceId, range }: PerTurnUsageSectionProps) {
	const t = useTranslations("usage");

	const { data, isLoading } = useQuery({
		queryKey: ["usage", "per-turn", workspaceId, range],
		queryFn: () => usageApiService.getPerTurn(workspaceId, range),
		enabled: workspaceId > 0,
	});

	const chartData = data?.items.slice().sort((a, b) => {
		return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
	});

	if (isLoading) {
		return (
			<Card>
				<CardHeader>
					<Skeleton className="h-6 w-40" aria-hidden="true" />
					<Skeleton className="h-4 w-64" aria-hidden="true" />
				</CardHeader>
				<CardContent>
					<Skeleton className="h-[240px] w-full" />
				</CardContent>
			</Card>
		);
	}

	if (!data || data.items.length === 0) {
		return (
			<Card>
				<CardHeader className="flex flex-row items-center gap-2">
					<BarChart3 className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
					<CardTitle className="text-base font-medium">{t("per_turn_title")}</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="flex h-[160px] items-center justify-center rounded-md border border-dashed">
						<p className="text-sm text-muted-foreground">{t("per_turn_empty")}</p>
					</div>
				</CardContent>
			</Card>
		);
	}

	return (
		<Card>
			<CardHeader className="flex flex-row items-center gap-2">
				<BarChart3 className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
				<div>
					<CardTitle className="text-base font-medium">{t("per_turn_title")}</CardTitle>
					<CardDescription>{t("per_turn_description")}</CardDescription>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				{data.reconcile_warning && (
					<Alert variant="warning">
						<AlertTriangle className="h-4 w-4" aria-hidden="true" />
						<AlertTitle>{t("per_turn_reconcile_warning_title")}</AlertTitle>
						<AlertDescription>{t("per_turn_reconcile_warning_description")}</AlertDescription>
					</Alert>
				)}

				<div className="h-[240px] w-full">
					<ResponsiveContainer width="100%" height="100%">
						<BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
							<CartesianGrid strokeDasharray="3 3" vertical={false} />
							<XAxis
								dataKey="turn_key"
								tick={{ fontSize: 12 }}
								tickLine={false}
								axisLine={false}
								tickFormatter={(_value, index) => {
									const item = chartData?.[index];
									return item ? formatDate(item.created_at) : "";
								}}
							/>
							<YAxis
								tick={{ fontSize: 12 }}
								tickLine={false}
								axisLine={false}
								tickFormatter={(value: number) => formatUsdMicros(value)}
								width={60}
							/>
							<Tooltip
								content={({ active, payload }) => {
									if (!active || !payload?.length) return null;
									const item = payload[0].payload as {
										capability: string;
										resolved_model: string;
										llm_tokens: number;
										embedding_tokens: number;
										recall_tokens: number;
										cost_micros: number;
										memories_created: number;
										citations_generated: number;
									};
									return (
										<div className="rounded-md border bg-popover p-2 text-sm shadow-md">
											<p className="font-medium">
												{t("per_turn_tooltip_capability")}: {item.capability}
											</p>
											<p className="text-muted-foreground">
												{t("per_turn_tooltip_model")}: {item.resolved_model}
											</p>
											<p className="text-muted-foreground">
												{t("per_turn_tooltip_cost")}: {formatUsdMicros(item.cost_micros)}
											</p>
											<p className="text-muted-foreground">
												{t("per_turn_tooltip_tokens", {
													llm: formatTokens(item.llm_tokens),
													embedding: formatTokens(item.embedding_tokens),
													recall: formatTokens(item.recall_tokens),
												})}
											</p>
											<p className="text-muted-foreground">
												{t("per_turn_tooltip_value", {
													memories: item.memories_created,
													citations: item.citations_generated,
												})}
											</p>
										</div>
									);
								}}
							/>
							<Bar dataKey="cost_micros" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
						</BarChart>
					</ResponsiveContainer>
				</div>

				<Table>
					<TableHeader>
						<TableRow>
							<TableHead className="w-[140px]">{t("per_turn_table_date")}</TableHead>
							<TableHead>{t("per_turn_table_capability")}</TableHead>
							<TableHead>{t("per_turn_table_model")}</TableHead>
							<TableHead className="text-right">{t("per_turn_table_tokens")}</TableHead>
							<TableHead className="text-right">{t("per_turn_table_cost")}</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{data.items.slice(0, 10).map((item) => (
							<TableRow key={item.turn_key}>
								<TableCell className="text-xs tabular-nums">
									{formatDate(item.created_at)}
								</TableCell>
								<TableCell className="text-xs">{item.capability}</TableCell>
								<TableCell className="text-xs text-muted-foreground">
									{item.resolved_model}
								</TableCell>
								<TableCell className="text-right text-xs tabular-nums">
									{formatTokens(item.llm_tokens + item.embedding_tokens + item.recall_tokens)}
								</TableCell>
								<TableCell className="text-right text-xs tabular-nums">
									{formatUsdMicros(item.cost_micros)}
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</CardContent>
		</Card>
	);
}
