"use client";

import { Award, CalendarCheck, CheckCircle2, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ServiceBreakdownItem } from "@/contracts/types/outcome-pricing.types";

export interface RoiMetrics {
	meetingCount: number;
	meetingCostMicros: number;
	costPerMeetingUsd: number;
	estimatedPipelineUsd: number;
	roiMultiplier: number;
}

export function calculateRoiMetrics(items: ServiceBreakdownItem[] = []): RoiMetrics {
	const meetingItem = items?.find((i) => i?.category === "Outcome Meetings");
	const meetingCount = meetingItem ? (meetingItem.event_count ?? 0) : 0;
	const meetingCostMicros = meetingItem ? (meetingItem.cost_micros ?? 0) : 0;
	const totalCostUsd = meetingCostMicros / 1_000_000;

	const costPerMeetingUsd = meetingCount > 0 ? totalCostUsd / meetingCount : 0;
	// Standard B2B qualified meeting estimated pipeline value is $500
	const estimatedPipelineUsd = meetingCount * 500;
	const roiMultiplier = totalCostUsd > 0 ? estimatedPipelineUsd / totalCostUsd : 0;

	return {
		meetingCount,
		meetingCostMicros,
		costPerMeetingUsd,
		estimatedPipelineUsd,
		roiMultiplier,
	};
}

export function OutcomeRoiMetricsCards({ items = [] }: { items?: ServiceBreakdownItem[] }) {
	const metrics = calculateRoiMetrics(items);

	const phoneItem = items?.find((i) => i?.category === "Phone Waterfall");
	const phoneCount = phoneItem ? (phoneItem.event_count ?? 0) : 0;

	return (
		<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
			<Card className="border-border/60 bg-card/50">
				<CardHeader className="flex flex-row items-center justify-between pb-2">
					<CardTitle className="text-sm font-medium">Cuộc hẹn B2B chốt</CardTitle>
					<CalendarCheck className="h-4 w-4 text-emerald-500" />
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold tabular-nums">
						{metrics.meetingCount.toLocaleString()}{" "}
						<span className="text-sm font-normal text-muted-foreground">lượt</span>
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Chi phí: ${(metrics.meetingCostMicros / 1_000_000).toFixed(2)} (50 credits/lượt)
					</p>
				</CardContent>
			</Card>

			<Card className="border-border/60 bg-card/50">
				<CardHeader className="flex flex-row items-center justify-between pb-2">
					<CardTitle className="text-sm font-medium">Chi phí / Cuộc hẹn</CardTitle>
					<Award className="h-4 w-4 text-primary" />
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold tabular-nums">
						${metrics.costPerMeetingUsd.toFixed(2)}
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Tương đương ~50.000đ (cố định theo kết quả)
					</p>
				</CardContent>
			</Card>

			<Card className="border-border/60 bg-card/50">
				<CardHeader className="flex flex-row items-center justify-between pb-2">
					<CardTitle className="text-sm font-medium">SĐT xác thực mở khóa</CardTitle>
					<CheckCircle2 className="h-4 w-4 text-blue-500" />
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold tabular-nums">
						{phoneCount.toLocaleString()}{" "}
						<span className="text-sm font-normal text-muted-foreground">SĐT</span>
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Waterfall 4 lớp (1.5 credits = 1.500đ / SĐT)
					</p>
				</CardContent>
			</Card>

			<Card className="border-border/60 bg-card/50">
				<CardHeader className="flex flex-row items-center justify-between pb-2">
					<CardTitle className="text-sm font-medium">Ước tính Pipeline ROI</CardTitle>
					<TrendingUp className="h-4 w-4 text-emerald-500" />
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold tabular-nums text-emerald-500">
						{metrics.roiMultiplier > 0 ? `${metrics.roiMultiplier.toFixed(0)}x` : "—"}
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Giá trị cơ hội: ${metrics.estimatedPipelineUsd.toLocaleString()}
					</p>
				</CardContent>
			</Card>
		</div>
	);
}
