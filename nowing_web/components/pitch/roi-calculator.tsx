"use client";

import { useMemo, useState } from "react";
import { Slider } from "@/components/ui/slider";

// Story 37.5 / AC-2: interactive ROI calculator on the mini-pitch portal.
// Seed values come from the generated portal content (roi defaults); the
// slider drives a live estimate — per UX-DR-E37-5 the thumb hit area is
// padded to >= 48px for mobile touch.

interface PitchRoiDefaults {
	default_sales_reps: number;
	min_sales_reps: number;
	max_sales_reps: number;
	meetings_per_rep_per_month: number;
	data_saving_per_rep_vnd: number;
}

const FALLBACK: PitchRoiDefaults = {
	default_sales_reps: 3,
	min_sales_reps: 1,
	max_sales_reps: 20,
	meetings_per_rep_per_month: 5,
	data_saving_per_rep_vnd: 8_000_000,
};

const vndFormatter = new Intl.NumberFormat("vi-VN", {
	style: "currency",
	currency: "VND",
	maximumFractionDigits: 0,
});

export function PitchRoiCalculator({ defaults }: { defaults?: PitchRoiDefaults | null }) {
	const roi = defaults ?? FALLBACK;
	const [reps, setReps] = useState(roi.default_sales_reps);

	const { meetings, savings } = useMemo(
		() => ({
			meetings: Math.round(reps * roi.meetings_per_rep_per_month),
			savings: reps * roi.data_saving_per_rep_vnd,
		}),
		[reps, roi.meetings_per_rep_per_month, roi.data_saving_per_rep_vnd]
	);

	return (
		<div className="space-y-6">
			<div className="space-y-3">
				<div className="flex items-center justify-between text-sm">
					<span className="text-muted-foreground">Quy mô đội sales</span>
					<span className="font-semibold tabular-nums">{reps} sales</span>
				</div>
				{/* Thumb stays h-5 w-5 visually; an invisible ::after box extends the
				    hit area to >=48px for mobile touch (UX-DR-E37-5). */}
				<Slider
					value={[reps]}
					min={roi.min_sales_reps}
					max={roi.max_sales_reps}
					step={1}
					onValueChange={(v) => setReps(v[0] ?? roi.default_sales_reps)}
					className="py-4 [&_[role=slider]]:relative [&_[role=slider]]:after:absolute [&_[role=slider]]:after:-inset-4 [&_[role=slider]]:after:content-['']"
					aria-label="Số lượng sales rep"
				/>
				<div className="flex justify-between text-xs text-muted-foreground">
					<span>{roi.min_sales_reps}</span>
					<span>{roi.max_sales_reps}</span>
				</div>
			</div>

			<div className="grid grid-cols-2 gap-3 text-center">
				<div className="rounded-lg border bg-background/60 p-4">
					<p className="text-2xl font-bold text-primary tabular-nums">+{meetings}</p>
					<p className="text-xs text-muted-foreground">cuộc hẹn bán hàng / tháng</p>
				</div>
				<div className="rounded-lg border bg-background/60 p-4">
					<p className="text-2xl font-bold text-primary tabular-nums">
						~{vndFormatter.format(savings)}
					</p>
					<p className="text-xs text-muted-foreground">tiết kiệm chi phí data / tháng</p>
				</div>
			</div>
		</div>
	);
}
