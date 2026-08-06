"use client";

import { XIcon } from "lucide-react";
import { useParams } from "next/navigation";
import type { FC } from "react";
import { RunDetail } from "@/app/dashboard/[workspace_id]/playground/components/run-detail";
import { Button } from "@/components/ui/button";

interface RunCitationPanelContentProps {
	runId: string;
	onClose?: () => void;
	showHeader?: boolean;
}

/**
 * Right-panel viewer for a run citation (`run_<uuid>`).
 *
 * Resolves the run in the current workspace and reuses the playground
 * `RunDetail` component to show capability, input, output, progress, and
 * error. A missing or invalid workspace shows a clear message instead of
 * a broken fetch.
 */
export const RunCitationPanelContent: FC<RunCitationPanelContentProps> = ({
	runId,
	onClose,
	showHeader = true,
}) => {
	const params = useParams<{ workspace_id?: string }>();
	const workspaceId = Number(params?.workspace_id);
	const scraperRunId = runId.replace(/^run_/, "");

	return (
		<>
			<div className="shrink-0">
				{showHeader && (
					<div className="shrink-0 flex h-12 items-center justify-between px-3 border-b">
						<h2 className="select-none text-lg font-semibold">Scraper run</h2>
						<div className="flex items-center gap-1 shrink-0">
							{onClose && (
								<Button
									variant="ghost"
									size="icon"
									onClick={onClose}
									className="h-8 w-8 rounded-full shrink-0 text-muted-foreground hover:text-accent-foreground"
								>
									<XIcon className="h-4 w-4" />
									<span className="sr-only">Close run panel</span>
								</Button>
							)}
						</div>
					</div>
				)}
			</div>

			<div className="flex-1 overflow-y-auto px-5 py-4">
				{!Number.isFinite(workspaceId) || workspaceId <= 0 ? (
					<p className="text-sm text-muted-foreground">Open a workspace to view this run.</p>
				) : (
					<RunDetail workspaceId={workspaceId} runId={scraperRunId} />
				)}
			</div>
		</>
	);
};
