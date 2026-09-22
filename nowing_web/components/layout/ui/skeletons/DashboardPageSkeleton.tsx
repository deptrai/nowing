import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface DashboardPageSkeletonProps {
	className?: string;
	titleWidthClass?: string;
	showStats?: boolean;
	cardCount?: number;
	showCharts?: boolean;
	showTable?: boolean;
}

export function DashboardPageSkeleton({
	className,
	titleWidthClass = "w-48",
	showStats = true,
	cardCount = 4,
	showCharts = true,
	showTable = true,
}: DashboardPageSkeletonProps) {
	return (
		<div className={cn("w-full max-w-7xl mx-auto py-6 px-4 sm:px-6 space-y-6", className)}>
			{/* Fixed 72px header anchor to prevent layout shift */}
			<div className="flex h-[72px] flex-col justify-center gap-2 border-b border-border/40 pb-4">
				<Skeleton className={cn("h-7 rounded-md", titleWidthClass)} />
				<Skeleton className="h-4 w-72 max-w-full rounded-md" />
			</div>

			{/* KPI / Stats row */}
			{showStats && (
				<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
					{Array.from({ length: cardCount }).map((_, i) => (
						<div
							key={`stat-card-${
								// biome-ignore lint/suspicious/noArrayIndexKey: pure visual skeleton
								i
							}`}
							className="flex h-28 flex-col justify-between rounded-xl border border-border/50 bg-card/40 p-4 shadow-xs"
						>
							<div className="flex items-center justify-between">
								<Skeleton className="h-4 w-24 rounded" />
								<Skeleton className="h-6 w-6 rounded-full" />
							</div>
							<div className="space-y-1">
								<Skeleton className="h-6 w-16 rounded" />
								<Skeleton className="h-3 w-32 rounded" />
							</div>
						</div>
					))}
				</div>
			)}

			{/* Primary content grid / charts */}
			{showCharts && (
				<div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
					<div className="h-72 rounded-xl border border-border/50 bg-card/40 p-5 shadow-xs space-y-4">
						<div className="flex items-center justify-between">
							<Skeleton className="h-5 w-36 rounded" />
							<Skeleton className="h-4 w-20 rounded" />
						</div>
						<Skeleton className="h-48 w-full rounded-lg" />
					</div>
					<div className="h-72 rounded-xl border border-border/50 bg-card/40 p-5 shadow-xs space-y-4">
						<div className="flex items-center justify-between">
							<Skeleton className="h-5 w-36 rounded" />
							<Skeleton className="h-4 w-20 rounded" />
						</div>
						<Skeleton className="h-48 w-full rounded-lg" />
					</div>
				</div>
			)}

			{/* Bottom section / table */}
			{showTable && (
				<div className="h-56 rounded-xl border border-border/50 bg-card/40 p-5 shadow-xs space-y-3">
					<Skeleton className="h-5 w-40 rounded" />
					<div className="space-y-2 pt-2">
						<Skeleton className="h-8 w-full rounded" />
						<Skeleton className="h-8 w-full rounded" />
						<Skeleton className="h-8 w-full rounded" />
					</div>
				</div>
			)}
		</div>
	);
}

export default DashboardPageSkeleton;
