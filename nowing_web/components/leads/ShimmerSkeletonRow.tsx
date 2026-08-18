"use client";

import type React from "react";
import { cn } from "@/lib/utils";

export interface ShimmerSkeletonRowProps {
	className?: string;
}

export const ShimmerSkeletonRow: React.FC<ShimmerSkeletonRowProps> = ({ className }) => {
	return (
		<tr
			data-testid="shimmer-skeleton-row"
			className={cn("border-b border-border/60 transition-colors", className)}
		>
			<td className="px-3 py-3.5 w-10">
				<div className="h-4 w-4 rounded bg-muted animate-pulse" />
			</td>
			<td className="px-3 py-3.5 min-w-[180px] max-w-[260px]">
				<div className="space-y-1.5">
					<div className="h-3.5 w-3/4 rounded bg-muted animate-pulse" />
					<div className="h-2.5 w-1/2 rounded bg-muted animate-pulse" />
				</div>
			</td>
			<td className="px-3 py-3.5 min-w-[100px] max-w-[180px]">
				<div className="h-3 w-16 rounded bg-muted animate-pulse" />
			</td>
			<td className="px-3 py-3.5 min-w-[90px] max-w-[140px]">
				<div className="h-3 w-14 rounded bg-muted animate-pulse" />
			</td>
			<td className="px-3 py-3.5 min-w-[110px] max-w-[150px]">
				<div className="h-5 w-20 rounded bg-muted animate-pulse" />
			</td>
			<td className="w-32 px-3 py-3.5 text-right">
				<div className="h-7 w-16 rounded bg-muted animate-pulse ml-auto" />
			</td>
		</tr>
	);
};
