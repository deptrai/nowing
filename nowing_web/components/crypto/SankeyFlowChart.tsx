"use client";

import { useEffect, useMemo, useState } from "react";
import { ResponsiveSankey } from "@nivo/sankey";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsMobile } from "@/hooks/use-mobile";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Maximize2, TableProperties, LineChart } from "lucide-react";
import type { WalletCohort } from "@/lib/chat/streaming-state";
import { colorForCohort } from "./cohort-colors";

// Types for Smart Money Data
export interface SankeyNode {
	id: string;
	// Story 10.1.4: cohort drives node color when present. Optional so legacy
	// "Market" aggregate node (no cohort) still renders.
	cohort?: WalletCohort;
	nodeColor?: string;
}

export interface SankeyLink {
	source: string;
	target: string;
	value: number;
}

export interface SankeyFlowChartProps {
	nodes?: SankeyNode[];
	links?: SankeyLink[];
	isLoading?: boolean;
	netFlowAmount?: number;
	locale?: string;
	currency?: string;
}

// Cohort palette — distinct, theme-friendly hues for nodes that ship without nodeColor.
const COHORT_PALETTE = [
	"#3b82f6",
	"#8b5cf6",
	"#ec4899",
	"#f97316",
	"#22c55e",
	"#14b8a6",
	"#eab308",
	"#ef4444",
];

// Safe Intl.NumberFormat — falls back to en-US/USD when locale or currency is rejected.
function safeFormat(amount: number, locale: string, currency: string, compact = false): string {
	if (!Number.isFinite(amount)) return "N/A";
	const opts: Intl.NumberFormatOptions = { style: "currency", currency };
	if (compact) opts.notation = "compact";
	try {
		return new Intl.NumberFormat(locale, opts).format(amount);
	} catch {
		return new Intl.NumberFormat("en-US", {
			style: "currency",
			currency: "USD",
			...(compact ? { notation: "compact" } : {}),
		}).format(amount);
	}
}

// Skeleton Sankey - no circular spinners (AC3)
export function SkeletonSankey() {
	return (
		<div className="w-full min-h-[400px] h-full flex flex-col gap-4 p-4 rounded-xl border bg-muted/20 animate-pulse">
			<div className="flex justify-between">
				<Skeleton className="h-6 w-32" />
				<Skeleton className="h-6 w-24" />
			</div>
			<div className="flex-1 flex justify-between items-center px-4">
				<div className="flex flex-col gap-8 w-12">
					<Skeleton className="h-16 w-full" />
					<Skeleton className="h-16 w-full" />
					<Skeleton className="h-16 w-full" />
				</div>
				<div className="flex-1 flex flex-col gap-4 items-center">
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-4 w-2/3" />
				</div>
				<div className="flex flex-col gap-12 w-16">
					<Skeleton className="h-24 w-full" />
					<Skeleton className="h-24 w-full" />
				</div>
			</div>
		</div>
	);
}

export function SankeyFlowChart({
	nodes = [],
	links = [],
	isLoading,
	netFlowAmount,
	locale = "en-US",
	currency = "USD",
}: SankeyFlowChartProps) {
	const [viewMode, setViewMode] = useState<"chart" | "table">("chart");
	const isMobile = useIsMobile();
	// Defer first render until after hydration so mobile vs desktop branches don't
	// mismatch SSR output (useIsMobile returns false on the server).
	const [mounted, setMounted] = useState(false);
	useEffect(() => {
		setMounted(true);
	}, []);

	// Sanitize graph: dedupe node ids, drop self-loops, drop links pointing at unknown nodes.
	const safeNodes = useMemo(() => {
		const map = new Map<string, SankeyNode>();
		for (const n of nodes) if (!map.has(n.id)) map.set(n.id, n);
		return Array.from(map.values());
	}, [nodes]);

	const safeLinks = useMemo(() => {
		const ids = new Set(safeNodes.map((n) => n.id));
		return links.filter((l) => l.source !== l.target && ids.has(l.source) && ids.has(l.target));
	}, [links, safeNodes]);

	// Story 10.1.4: prefer cohort-driven color (smart_money green, cex orange,
	// dex blue, etc.). Fall back to explicit nodeColor or palette rotation only
	// when cohort is missing (e.g. legacy data, "Market" aggregate node).
	const colorById = useMemo(() => {
		const out = new Map<string, string>();
		safeNodes.forEach((n, i) => {
			if (n.cohort) {
				out.set(n.id, colorForCohort(n.cohort));
			} else {
				out.set(n.id, n.nodeColor ?? COHORT_PALETTE[i % COHORT_PALETTE.length]);
			}
		});
		return out;
	}, [safeNodes]);

	if (isLoading || !mounted) {
		return <SkeletonSankey />;
	}

	const hasData = safeNodes.length > 0 && safeLinks.length > 0;

	const netFlowColor =
		netFlowAmount === undefined || !Number.isFinite(netFlowAmount)
			? "text-muted-foreground"
			: netFlowAmount > 0
				? "text-green-500"
				: netFlowAmount < 0
					? "text-red-500"
					: "text-muted-foreground";

	const netFlowLabel = (() => {
		if (netFlowAmount === undefined || !Number.isFinite(netFlowAmount)) return null;
		const sign = netFlowAmount > 0 ? "+" : "";
		return `${sign}${safeFormat(netFlowAmount, locale, currency, true)}`;
	})();

	const content = (
		<div className="w-full h-full flex flex-col border rounded-xl bg-card">
			<div className="flex justify-between items-center p-4 border-b">
				<div>
					<h3 className="font-semibold text-lg">Smart Money Flow</h3>
					{netFlowLabel && (
						<p className={`text-sm ${netFlowColor}`}>24h Net Flow: {netFlowLabel}</p>
					)}
				</div>

				{/* Table View Toggle for Accessibility (AC3) */}
				{hasData && (
					<Button
						variant="outline"
						size="sm"
						onClick={() => setViewMode(viewMode === "chart" ? "table" : "chart")}
						aria-label={viewMode === "chart" ? "Show data table" : "Show flow chart"}
					>
						{viewMode === "chart" ? (
							<>
								<TableProperties className="w-4 h-4 mr-2" /> Table View
							</>
						) : (
							<>
								<LineChart className="w-4 h-4 mr-2" /> Chart View
							</>
						)}
					</Button>
				)}
			</div>

			<div className="flex-1 p-4 overflow-hidden relative min-h-[300px]">
				{!hasData ? (
					<div className="h-full flex items-center justify-center text-sm text-muted-foreground">
						No flow activity in this period.
					</div>
				) : viewMode === "chart" ? (
					<ResponsiveSankey
						data={{ nodes: safeNodes, links: safeLinks }}
						margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
						align="justify"
						colors={(node: { id: string }) => colorById.get(node.id) ?? COHORT_PALETTE[0]}
						nodeOpacity={1}
						nodeHoverOthersOpacity={0.3}
						nodeThickness={18}
						nodeSpacing={24}
						nodeBorderWidth={0}
						nodeBorderRadius={3}
						linkOpacity={0.5}
						linkHoverOthersOpacity={0.1}
						linkContract={3}
						enableLinkGradient={true}
						labelPosition="outside"
						labelOrientation="vertical"
						labelPadding={16}
						labelTextColor="currentColor"
					/>
				) : (
					<div className="overflow-auto h-full">
						<Table>
							<TableHeader>
								<TableRow>
									<TableHead>Source Entity</TableHead>
									<TableHead>Target Entity</TableHead>
									<TableHead className="text-right">Value ({currency})</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{safeLinks.map((link, i) => (
									<TableRow key={`${link.source}->${link.target}#${i}`}>
										<TableCell className="font-medium">{link.source}</TableCell>
										<TableCell>{link.target}</TableCell>
										<TableCell className="text-right">
											{safeFormat(link.value, locale, currency)}
										</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					</div>
				)}
			</div>
		</div>
	);

	// Bottom Sheet for Mobile (AC3) — surface net flow KPI on the trigger.
	if (isMobile) {
		return (
			<Sheet>
				<SheetTrigger asChild>
					<Button variant="outline" className="w-full justify-between">
						<span className="flex items-center">
							<Maximize2 className="w-4 h-4 mr-2" />
							Smart Money Flow
						</span>
						{netFlowLabel && (
							<span className={`text-xs font-semibold ${netFlowColor}`}>{netFlowLabel}</span>
						)}
					</Button>
				</SheetTrigger>
				<SheetContent side="bottom" className="h-[80vh] pt-6 px-2">
					<SheetHeader className="mb-4 px-2">
						<SheetTitle>Smart Money Flow Analysis</SheetTitle>
					</SheetHeader>
					<div className="h-[calc(100%-60px)]">{content}</div>
				</SheetContent>
			</Sheet>
		);
	}

	return <div className="w-full h-full min-h-[400px]">{content}</div>;
}
