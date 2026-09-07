"use client";

import { AlertCircle, ArrowUpRight, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import type { CoverageGapItem } from "@/contracts/types/workspace-health.types";

interface CoverageGapDrawerProps {
	isOpen: boolean;
	onClose: () => void;
	gaps: CoverageGapItem[];
	workspaceId: number | string;
}

export function CoverageGapDrawer({
	isOpen,
	onClose,
	gaps = [],
	workspaceId,
}: CoverageGapDrawerProps) {
	return (
		<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
				<SheetHeader className="pb-4 border-b">
					<div className="flex items-center gap-2">
						<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
							<AlertCircle className="h-4 w-4" />
						</div>
						<div>
							<SheetTitle>Knowledge Coverage Gaps</SheetTitle>
							<SheetDescription>
								Enabled sources with 0 memories created in trailing 30 days
							</SheetDescription>
						</div>
					</div>
				</SheetHeader>

				<div className="py-6 space-y-4">
					{gaps.length === 0 ? (
						<div className="flex flex-col items-center justify-center p-8 text-center border rounded-xl bg-muted/20">
							<CheckCircle2 className="h-10 w-10 text-emerald-500 mb-2" />
							<h4 className="font-medium text-sm">Full Coverage Active</h4>
							<p className="text-xs text-muted-foreground mt-1 max-w-xs">
								All configured knowledge connectors and scrapers have actively contributed memories
								within the last 30 days.
							</p>
						</div>
					) : (
						<div className="space-y-3">
							<p className="text-xs text-muted-foreground">
								Found {gaps.length} inactive {gaps.length === 1 ? "source" : "sources"}. Review
								configuration and trigger syncs to ensure fresh context.
							</p>

							{gaps.map((gap) => (
								<Card
									key={gap.source_type}
									className="border-amber-500/20 bg-amber-500/5 shadow-none"
								>
									<CardContent className="p-4 space-y-3">
										<div className="flex items-center justify-between">
											<div className="flex items-center gap-2">
												<span className="font-semibold text-sm capitalize">
													{gap.source_type.replace(/_/g, " ")}
												</span>
												<Badge
													variant="outline"
													className="text-amber-600 border-amber-500/30 text-[10px] uppercase"
												>
													Zero Memories (30d)
												</Badge>
											</div>
										</div>

										<p className="text-xs text-foreground/80 leading-relaxed">
											{gap.remediation_action}
										</p>

										<div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/40">
											<span>Enabled: {new Date(gap.enabled_since).toLocaleDateString()}</span>
											{gap.last_synced_at ? (
												<span>Last sync: {new Date(gap.last_synced_at).toLocaleDateString()}</span>
											) : (
												<span className="italic">Never synced</span>
											)}
										</div>

										<div className="pt-1">
											<Button
												asChild
												size="sm"
												variant="outline"
												className="w-full justify-between h-8 text-xs"
											>
												<Link href={gap.configure_url || `/dashboard/${workspaceId}/connectors`}>
													<span>Configure Connector</span>
													<ArrowUpRight className="h-3.5 w-3.5 ml-1" />
												</Link>
											</Button>
										</div>
									</CardContent>
								</Card>
							))}
						</div>
					)}
				</div>
			</SheetContent>
		</Sheet>
	);
}
