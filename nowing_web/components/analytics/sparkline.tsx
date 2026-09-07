"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface SparklineProps {
	values: (number | null | undefined)[];
	className?: string;
	width?: number;
	height?: number;
	colorClassName?: string;
}

export function Sparkline({
	values = [],
	className,
	width = 120,
	height = 32,
	colorClassName = "text-primary",
}: SparklineProps) {
	const sanitized = useMemo(() => {
		return values.map((v) => (typeof v === "number" && Number.isFinite(v) ? v : 0));
	}, [values]);

	const pathData = useMemo(() => {
		if (sanitized.length < 2) {
			const y = height / 2;
			return `M 0 ${y} L ${width} ${y}`;
		}

		const min = Math.min(...sanitized);
		const max = Math.max(...sanitized);
		const range = max - min;
		const padding = 3;
		const effectiveHeight = height - padding * 2;

		const points = sanitized.map((val, idx) => {
			const x = (idx / (sanitized.length - 1)) * width;
			const y =
				range === 0 ? height / 2 : height - padding - ((val - min) / range) * effectiveHeight;
			return [x, y];
		});

		return points.reduce((acc, [x, y], idx) => {
			return idx === 0
				? `M ${x.toFixed(1)} ${y.toFixed(1)}`
				: `${acc} L ${x.toFixed(1)} ${y.toFixed(1)}`;
		}, "");
	}, [sanitized, width, height]);

	return (
		<svg
			role="img"
			viewBox={`0 0 ${width} ${height}`}
			preserveAspectRatio="none"
			className={cn("overflow-visible", className)}
			aria-label="Trend sparkline"
		>
			<title>Trend sparkline</title>
			<path
				d={pathData}
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				className={colorClassName}
			/>
		</svg>
	);
}
