"use client";

import { AlertOctagon, AlertTriangle, CheckCircle2, HelpCircle, Play } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { DryRunResponse } from "@/contracts/types/admin-bulk-ops.types";

interface DryRunCardProps {
	dryRunResult: DryRunResponse | null;
	isLoading?: boolean;
	onExecute: () => void;
	isExecuting: boolean;
	onDryRun: () => void;
	isDryRunning: boolean;
	disabled?: boolean;
	isHighRisk?: boolean;
}

export function DryRunCard({
	dryRunResult,
	onExecute,
	isExecuting,
	onDryRun,
	isDryRunning,
	disabled = false,
	isHighRisk = false,
}: DryRunCardProps) {
	const count = dryRunResult?.affected_count ?? dryRunResult?.total_count ?? 0;
	const sample = dryRunResult?.sample_affected ?? dryRunResult?.sample_subjects ?? [];
	const warnings = dryRunResult?.warnings ?? [];
	const conflicts = dryRunResult?.conflicts ?? [];
	const canExecute = dryRunResult?.can_execute ?? true;

	return (
		<Card className="shadow-sm">
			<CardHeader className="pb-3">
				<div className="flex items-center justify-between">
					<div>
						<CardTitle className="text-base font-semibold">Dry-Run Simulation</CardTitle>
						<CardDescription className="text-xs">
							Simulate the query to preview affected targets and identify potential conflicts before
							running.
						</CardDescription>
					</div>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						onClick={onDryRun}
						disabled={disabled || isDryRunning || isExecuting}
						className="h-8 gap-1.5 text-xs"
					>
						{isDryRunning ? (
							<>Simulating...</>
						) : (
							<>
								<CheckCircle2 className="h-3.5 w-3.5 text-blue-500" />
								Run Simulation
							</>
						)}
					</Button>
				</div>
			</CardHeader>

			<CardContent className="space-y-4 pt-1">
				{!dryRunResult && !isDryRunning && (
					<div className="rounded-md border border-dashed p-6 text-center text-xs text-muted-foreground">
						No simulation results yet. Configure your action and filters above, then click &quot;Run
						Simulation&quot; to preview impact.
					</div>
				)}

				{isDryRunning && (
					<div className="py-8 text-center space-y-2">
						<div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
						<p className="text-xs text-muted-foreground">
							Evaluating filters and calculating targets...
						</p>
					</div>
				)}

				{dryRunResult && !isDryRunning && (
					<div className="space-y-4">
						{/* Affected Metrics */}
						<div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
							<div className="p-3 rounded-lg border bg-card">
								<span className="text-xs text-muted-foreground block">Affected Count</span>
								<span className="text-2xl font-bold tracking-tight text-primary">{count}</span>
							</div>
							<div className="p-3 rounded-lg border bg-card">
								<span className="text-xs text-muted-foreground block">Execution Safety</span>
								<div className="mt-1">
									{canExecute && conflicts.length === 0 ? (
										<Badge
											variant="outline"
											className="text-green-600 border-green-500/30 bg-green-500/10 text-xs"
										>
											Safe to Execute
										</Badge>
									) : (
										<Badge variant="destructive" className="text-xs">
											Execution Blocked
										</Badge>
									)}
								</div>
							</div>
							<div className="p-3 rounded-lg border bg-card col-span-2 sm:col-span-1">
								<span className="text-xs text-muted-foreground block">Warnings / Conflicts</span>
								<span className="text-2xl font-bold tracking-tight text-amber-500">
									{warnings.length + conflicts.length}
								</span>
							</div>
						</div>

						{/* Warnings */}
						{warnings.length > 0 && (
							<Alert
								variant="default"
								className="border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-200"
							>
								<AlertTriangle className="h-4 w-4 text-amber-600" />
								<AlertTitle className="text-xs font-semibold">Simulation Warnings</AlertTitle>
								<AlertDescription className="text-xs mt-1 space-y-1">
									{warnings.map((w) => (
										<div key={`warning-${w}`}>• {w}</div>
									))}
								</AlertDescription>
							</Alert>
						)}

						{/* Conflicts */}
						{conflicts.length > 0 && (
							<Alert variant="destructive">
								<AlertOctagon className="h-4 w-4" />
								<AlertTitle className="text-xs font-semibold">
									Execution Conflicts Detected
								</AlertTitle>
								<AlertDescription className="text-xs mt-1 space-y-1">
									{conflicts.map((c) => {
										const conflictObj = c as Record<string, unknown>;
										const msg =
											typeof conflictObj.message === "string"
												? conflictObj.message
												: JSON.stringify(c);
										return <div key={`conflict-${msg}`}>• {msg}</div>;
									})}
								</AlertDescription>
							</Alert>
						)}

						{/* Sample Affected Entities */}
						{sample.length > 0 && (
							<div className="space-y-2">
								<span className="text-xs font-semibold text-muted-foreground block">
									Sample Affected Subjects (Showing up to {sample.length})
								</span>
								<div className="rounded-md border overflow-x-auto max-h-48">
									<Table className="text-xs">
										<TableHeader>
											<TableRow className="h-8">
												<TableHead className="w-[80px]">ID</TableHead>
												<TableHead>Details</TableHead>
											</TableRow>
										</TableHeader>
										<TableBody>
											{sample.map((item, idx) => {
												const id = String(item.id ?? item.workspace_id ?? item.user_id ?? idx + 1);
												const details = Object.entries(item)
													.filter(([k]) => k !== "id")
													.map(([k, v]) => `${k}: ${String(v)}`)
													.join(" | ");

												return (
													<TableRow key={`sample-${id}`} className="h-8">
														<TableCell className="font-mono text-xs">{id}</TableCell>
														<TableCell className="text-muted-foreground font-mono text-[11px] truncate max-w-md">
															{details || "—"}
														</TableCell>
													</TableRow>
												);
											})}
										</TableBody>
									</Table>
								</div>
							</div>
						)}
					</div>
				)}
			</CardContent>

			<CardFooter className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t pt-3 bg-muted/10">
				<div className="text-xs text-muted-foreground flex items-center gap-1.5">
					<HelpCircle className="h-3.5 w-3.5" />
					Execution runs asynchronously in batches of 100 with transactional rollback on errors.
				</div>
				<Button
					type="button"
					variant={isHighRisk ? "destructive" : "default"}
					onClick={onExecute}
					disabled={
						disabled ||
						!dryRunResult ||
						count === 0 ||
						!canExecute ||
						conflicts.length > 0 ||
						isExecuting ||
						isDryRunning
					}
					className="gap-2 h-9 text-xs shrink-0"
				>
					<Play className="h-3.5 w-3.5 fill-current" />
					{isExecuting ? "Queuing Job..." : isHighRisk ? "Confirm & Execute" : "Execute Operation"}
				</Button>
			</CardFooter>
		</Card>
	);
}
