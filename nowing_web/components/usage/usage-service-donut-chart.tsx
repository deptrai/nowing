"use client";

import { Bot, Calendar, Globe, PhoneCall, Share2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ServiceBreakdownItem } from "@/contracts/types/outcome-pricing.types";

export function calculateServicePercentages(
	items: ServiceBreakdownItem[] = []
): Array<ServiceBreakdownItem & { percentage: number; color: string; iconName: string }> {
	const totalCost = items?.reduce((acc, curr) => acc + (curr?.cost_micros ?? 0), 0) ?? 0;

	const metaMap: Record<string, { color: string; iconName: string }> = {
		"AI Generation": { color: "bg-purple-500", iconName: "bot" },
		"Web Search": { color: "bg-blue-500", iconName: "globe" },
		"Social Media": { color: "bg-pink-500", iconName: "share" },
		"Phone Waterfall": { color: "bg-amber-500", iconName: "phone" },
		"Outcome Meetings": { color: "bg-emerald-500", iconName: "calendar" },
	};

	return (items || []).map((item) => {
		const meta = metaMap[item?.category] || { color: "bg-primary", iconName: "bot" };
		const costMicros = item?.cost_micros ?? 0;
		const percentage = totalCost > 0 ? (costMicros / totalCost) * 100 : 0;
		return {
			...item,
			cost_micros: costMicros,
			total_tokens: item?.total_tokens ?? 0,
			event_count: item?.event_count ?? 0,
			percentage: Number(percentage.toFixed(1)),
			color: meta.color,
			iconName: meta.iconName,
		};
	});
}

function renderIcon(iconName: string) {
	switch (iconName) {
		case "globe":
			return <Globe className="h-4 w-4 text-blue-500" />;
		case "share":
			return <Share2 className="h-4 w-4 text-pink-500" />;
		case "phone":
			return <PhoneCall className="h-4 w-4 text-amber-500" />;
		case "calendar":
			return <Calendar className="h-4 w-4 text-emerald-500" />;
		default:
			return <Bot className="h-4 w-4 text-purple-500" />;
	}
}

export function UsageServiceDonutChart({ items = [] }: { items?: ServiceBreakdownItem[] }) {
	const processed = calculateServicePercentages(items);
	const totalCostMicros = items?.reduce((acc, curr) => acc + (curr?.cost_micros ?? 0), 0) ?? 0;
	const totalUsd = (totalCostMicros / 1_000_000).toFixed(2);
	const totalCredits = (totalCostMicros / 40_000).toLocaleString();

	return (
		<Card className="border-border/60">
			<CardHeader className="pb-3">
				<div className="flex items-center justify-between">
					<div>
						<CardTitle className="text-base font-semibold">Phân bổ chi phí theo Dịch vụ</CardTitle>
						<CardDescription className="text-xs">
							Mô hình giá theo kết quả (Outcome Pricing) & dịch vụ tiêu thụ thực tế
						</CardDescription>
					</div>
					<div className="text-right">
						<span className="text-sm font-bold">${totalUsd}</span>
						<span className="block text-[11px] text-muted-foreground">{totalCredits} credits</span>
					</div>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				{/* Multi-segment progress bar */}
				<div className="h-3 w-full overflow-hidden rounded-full bg-secondary/50 flex">
					{processed.map((item) =>
						item.percentage > 0 ? (
							<div
								key={item.category}
								style={{ width: `${item.percentage}%` }}
								className={`${item.color} transition-all duration-300`}
								title={`${item.category}: ${item.percentage}%`}
							/>
						) : null
					)}
				</div>

				{/* Legend list */}
				<div className="grid gap-2 sm:grid-cols-2">
					{processed.map((item) => (
						<div
							key={item.category}
							className="flex items-center justify-between rounded-lg border border-border/40 bg-card/30 p-2.5"
						>
							<div className="flex items-center gap-2">
								<div className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary/80">
									{renderIcon(item.iconName)}
								</div>
								<div>
									<div className="text-xs font-medium">{item.category}</div>
									<div className="text-[10px] text-muted-foreground">
										{item.event_count.toLocaleString()} sự kiện •{" "}
										{item.total_tokens > 0
											? `${item.total_tokens.toLocaleString()} tokens`
											: "Sự kiện giá trị"}
									</div>
								</div>
							</div>
							<div className="text-right">
								<span className="text-xs font-semibold">
									${(item.cost_micros / 1_000_000).toFixed(3)}
								</span>
								<span className="block text-[10px] text-muted-foreground">{item.percentage}%</span>
							</div>
						</div>
					))}
				</div>
			</CardContent>
		</Card>
	);
}
