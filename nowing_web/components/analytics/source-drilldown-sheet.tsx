"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Database, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { workspaceHealthApiService } from "@/lib/apis/workspace-health-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface SourceDrilldownSheetProps {
	workspaceId: number | string;
	sourceType: string | null;
	isOpen: boolean;
	onClose: () => void;
	isPublicSnapshot?: boolean;
}

function formatCostUsd(micros: number | null | undefined): string {
	if (micros === null || micros === undefined) return "—";
	const dollars = micros / 1_000_000;
	if (dollars === 0) return "$0.00";
	if (dollars < 0.01) return `< $0.01`;
	return `$${dollars.toFixed(2)}`;
}

export function SourceDrilldownSheet({
	workspaceId,
	sourceType,
	isOpen,
	onClose,
	isPublicSnapshot = false,
}: SourceDrilldownSheetProps) {
	const { data, isLoading, isError } = useQuery({
		queryKey: cacheKeys.workspaces.health.sourceDrilldown(workspaceId, sourceType || ""),
		queryFn: () => workspaceHealthApiService.getSourceDrilldown(workspaceId, sourceType || ""),
		enabled: isOpen && !!sourceType && !!workspaceId,
	});

	return (
		<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto">
				<SheetHeader className="pb-4 border-b">
					<div className="flex items-center gap-2">
						<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
							<Database className="h-4 w-4" />
						</div>
						<div>
							<SheetTitle className="capitalize">
								{sourceType?.replace(/_/g, " ") || "Source"} Drilldown
							</SheetTitle>
							<SheetDescription>
								Ingestion history, query citations, and timeline samples
							</SheetDescription>
						</div>
					</div>
				</SheetHeader>

				<div className="py-6 space-y-6">
					{isLoading ? (
						<div className="flex h-48 items-center justify-center">
							<Spinner className="h-6 w-6 text-muted-foreground" />
						</div>
					) : isError || !data ? (
						<div className="p-4 border rounded-lg text-center text-sm text-muted-foreground">
							No historical metrics found for this source.
						</div>
					) : (
						<>
							{/* Summary Cards */}
							<div className="grid grid-cols-3 gap-3">
								<Card className="shadow-none">
									<CardHeader className="p-3 pb-1">
										<CardTitle className="text-xs font-normal text-muted-foreground">
											Total Memories
										</CardTitle>
									</CardHeader>
									<CardContent className="p-3 pt-0">
										<div className="text-lg font-bold">{data.total_memories.toLocaleString()}</div>
									</CardContent>
								</Card>

								<Card className="shadow-none">
									<CardHeader className="p-3 pb-1">
										<CardTitle className="text-xs font-normal text-muted-foreground">
											Query Citations
										</CardTitle>
									</CardHeader>
									<CardContent className="p-3 pt-0">
										<div className="text-lg font-bold">{data.query_volume.toLocaleString()}</div>
									</CardContent>
								</Card>

								<Card className="shadow-none">
									<CardHeader className="p-3 pb-1">
										<CardTitle className="text-xs font-normal text-muted-foreground">
											Cost Attribution
										</CardTitle>
									</CardHeader>
									<CardContent className="p-3 pt-0">
										<div className="text-lg font-bold">
											{isPublicSnapshot || data.cost_micros === null
												? "Protected"
												: formatCostUsd(data.cost_micros)}
										</div>
									</CardContent>
								</Card>
							</div>

							{isPublicSnapshot && (
								<div className="flex items-center gap-2 p-2.5 rounded-md bg-muted/40 text-xs text-muted-foreground">
									<ShieldAlert className="h-4 w-4 text-amber-500 shrink-0" />
									<span>Cost attribution is masked in public snapshot mode.</span>
								</div>
							)}

							{/* Recent Timeline Samples */}
							<div className="space-y-3">
								<div className="flex items-center justify-between">
									<h4 className="font-medium text-xs text-muted-foreground uppercase tracking-wider">
										Recent Memory Samples ({data.recent_samples.length})
									</h4>
								</div>

								{data.recent_samples.length === 0 ? (
									<div className="p-6 border rounded-lg text-center text-xs text-muted-foreground bg-muted/10">
										No memory samples available for this source.
									</div>
								) : (
									<div className="space-y-3">
										{data.recent_samples.map((sample) => (
											<div
												key={sample.id}
												className="p-3.5 border rounded-lg bg-card text-xs space-y-2 hover:border-primary/40 transition-colors"
											>
												<p className="line-clamp-3 font-mono text-[11px] leading-relaxed text-foreground/90">
													{sample.content}
												</p>

												<div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/40 text-[11px] text-muted-foreground">
													<div className="flex items-center gap-1">
														<Clock className="h-3 w-3" />
														<span>{new Date(sample.created_at).toLocaleString()}</span>
													</div>

													<div className="flex items-center gap-1.5">
														<Badge
															variant="secondary"
															className="text-[10px] px-1.5 py-0 font-normal"
														>
															Conf: {(sample.confidence * 100).toFixed(0)}%
														</Badge>
														{sample.tags.slice(0, 2).map((tag) => (
															<Badge
																key={tag}
																variant="outline"
																className="text-[10px] px-1.5 py-0 font-normal"
															>
																{tag}
															</Badge>
														))}
													</div>
												</div>
											</div>
										))}
									</div>
								)}
							</div>
						</>
					)}
				</div>
			</SheetContent>
		</Sheet>
	);
}
