"use client";

import { useSetAtom } from "jotai";
import { Database } from "lucide-react";
import type { FC } from "react";
import { openRunCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface RunCitationProps {
	runId: string;
}

/**
 * Inline citation badge for a scraper run handle (`run_<uuid>`).
 *
 * Shows a compact "Source" chip with a database icon; clicking it opens
 * the run-detail panel in the right sidebar.
 */
export const RunCitation: FC<RunCitationProps> = ({ runId }) => {
	const openRunCitationPanel = useSetAtom(openRunCitationPanelAtom);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					onClick={() => openRunCitationPanel({ runId })}
					className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
					title="See where this came from"
					aria-label={`View scraper run ${runId}`}
				>
					<Database className="size-3" />
					Source
				</Button>
			</TooltipTrigger>
			<TooltipContent>See where this came from</TooltipContent>
		</Tooltip>
	);
};
