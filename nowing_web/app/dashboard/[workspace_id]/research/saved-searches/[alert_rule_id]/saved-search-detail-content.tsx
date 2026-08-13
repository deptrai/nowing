"use client";

import { useQuery } from "@tanstack/react-query";
import { SearchX } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import type { AlertRule, AlertSnapshot } from "@/contracts/types/alert-rules.types";
import { alertRulesApiService } from "@/lib/apis/alert-rules-api.service";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface SavedSearchDetailContentProps {
	workspaceId: number;
	alertRuleId: string;
}

function isValidWorkspaceId(value: number): boolean {
	return Number.isFinite(value) && value > 0 && Number.isInteger(value);
}

function isValidAlertRuleId(value: string): boolean {
	return UUID_RE.test(value);
}

/**
 * Detail view for a saved search (alert rule) opened from a notification.
 * Reads the `?snapshot=` query param to highlight the run the user was
 * notified about. Fails soft: 404/403 render the same not-found panel.
 */
export function SavedSearchDetailContent({
	workspaceId,
	alertRuleId,
}: SavedSearchDetailContentProps) {
	const searchParams = useSearchParams();
	const snapshotId = searchParams.get("snapshot");
	const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(snapshotId);

	const validId = isValidWorkspaceId(workspaceId) && isValidAlertRuleId(alertRuleId);
	const {
		data: rule,
		isLoading,
		error,
	} = useQuery<AlertRule, Error>({
		queryKey: ["alert-rule", workspaceId, alertRuleId],
		queryFn: () => alertRulesApiService.getAlertRule(workspaceId, alertRuleId),
		enabled: validId,
		staleTime: 60_000,
	});

	const { data: snapshots = [] } = useQuery<AlertSnapshot[], Error>({
		queryKey: ["alert-rule-snapshots", workspaceId, alertRuleId],
		queryFn: () => alertRulesApiService.listSnapshots(workspaceId, alertRuleId, 20),
		enabled: validId,
		staleTime: 30_000,
	});

	const requestedSnapshot = snapshots.find((s) => s.id === selectedSnapshotId) ?? null;
	const selectedSnapshot = requestedSnapshot ?? snapshots[0] ?? null;
	const snapshotMissing =
		selectedSnapshotId !== null && requestedSnapshot === null && snapshots.length > 0;

	if (isLoading) {
		return (
			<div className="space-y-4">
				<div className="h-8 w-1/2 animate-pulse rounded bg-muted" />
				<div className="h-40 w-full animate-pulse rounded-lg bg-muted" />
			</div>
		);
	}

	if (error || !rule) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<SearchX className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
				<h2 className="mt-3 text-base font-semibold text-foreground">Saved search not found</h2>
				<p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
					This saved search may have been deleted or you don't have access to it.
				</p>
			</div>
		);
	}

	return (
		<div className="w-full space-y-6">
			<div>
				<h1 className="text-xl font-semibold">{rule.name}</h1>
				<p className="mt-1 text-sm text-muted-foreground">
					Saved search · {rule.capability_id} ·{" "}
					{rule.schedule === "none" ? "manual" : rule.schedule}
				</p>
			</div>

			{selectedSnapshot ? (
				<div className="rounded-lg border border-border/60">
					<div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
						<h2 className="text-sm font-medium">
							Latest run{" "}
							{selectedSnapshotId && selectedSnapshot.id !== selectedSnapshotId ? "— selected" : ""}
						</h2>
						<span className="text-xs text-muted-foreground">
							{new Date(selectedSnapshot.created_at).toLocaleString()}
						</span>
					</div>
					<div className="grid grid-cols-2 gap-4 px-4 py-4 sm:grid-cols-4">
						<div>
							<p className="text-xs text-muted-foreground">New items</p>
							<p className="mt-0.5 text-lg font-semibold">{selectedSnapshot.new_items_count}</p>
						</div>
						<div>
							<p className="text-xs text-muted-foreground">Changed</p>
							<p className="mt-0.5 text-lg font-semibold">{selectedSnapshot.changed_items_count}</p>
						</div>
						<div>
							<p className="text-xs text-muted-foreground">Removed</p>
							<p className="mt-0.5 text-lg font-semibold">{selectedSnapshot.removed_items_count}</p>
						</div>
						<div>
							<p className="text-xs text-muted-foreground">Status</p>
							<p className="mt-0.5 text-lg font-semibold">{selectedSnapshot.run_status}</p>
						</div>
					</div>
					{selectedSnapshot.degradation_reasons?.length ? (
						<p className="border-t border-border/60 px-4 py-2 text-xs text-amber-600 dark:text-amber-400">
							Some sources were unavailable: {selectedSnapshot.degradation_reasons.join(", ")}
						</p>
					) : null}
				</div>
			) : snapshotMissing ? (
				<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-10 text-center">
					<p className="text-sm font-medium">Linked snapshot not found</p>
					<p className="mt-1 text-xs text-muted-foreground">
						The run this notification pointed to no longer exists. Showing the latest run instead.
					</p>
				</div>
			) : (
				<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-10 text-center">
					<p className="text-sm font-medium">No runs yet</p>
					<p className="mt-1 text-xs text-muted-foreground">
						This saved search hasn't run yet. New matches will appear here.
					</p>
				</div>
			)}

			{snapshots.length > 1 ? (
				<div className="rounded-lg border border-border/60">
					<h2 className="border-b border-border/60 px-4 py-3 text-sm font-medium">Run history</h2>
					<ul className="divide-y divide-border/60">
						{snapshots.map((snapshot) => (
							<li key={snapshot.id}>
								<button
									type="button"
									onClick={() => setSelectedSnapshotId(snapshot.id)}
									className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-accent/40"
								>
									<span className="text-sm">{new Date(snapshot.created_at).toLocaleString()}</span>
									<span className="flex items-center gap-3 text-xs text-muted-foreground">
										<span>+{snapshot.new_items_count} new</span>
										<span>{snapshot.run_status}</span>
									</span>
								</button>
							</li>
						))}
					</ul>
				</div>
			) : null}
		</div>
	);
}
