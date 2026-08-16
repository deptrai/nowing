import type { FC } from "react";
import { cn } from "@/lib/utils";
import type { ItemStatus } from "../types";

/**
 * The title row + sub-bullets shared by every timeline item kind. The
 * timeline's chrome (status dot, indent, vertical line) renders to the
 * left; this fills the right column.
 *
 * Status-aware text styling matches the legacy ``StepBody`` semantics:
 *   running   → emphasised (font-medium foreground)
 *   completed → muted
 *   pending   → muted/60
 *   error     → destructive
 *   cancelled → strikethrough muted
 *
 * Sub-bullets render via ``ChainOfThoughtItem`` (reused from
 * ``components/prompt-kit/chain-of-thought``) — same component the
 * legacy ``StepBody`` used.
 */
export const ItemHeader: FC<{
	title: string;
	status: ItemStatus;
	items?: readonly string[];
	itemKey: string;
}> = ({ title, status, items, itemKey }) => (
	<div className="min-w-0 flex flex-col justify-center">
		<div className="flex items-center gap-1.5 leading-tight">
			<span
				className={cn(
					"text-[11px] truncate",
					status === "running" && "text-foreground font-medium",
					status === "completed" && "text-muted-foreground font-normal",
					status === "pending" && "text-muted-foreground/60",
					status === "error" && "text-destructive",
					status === "cancelled" && "text-muted-foreground line-through"
				)}
			>
				{title}
			</span>
			{status === "running" && (
				<span className="text-[9.5px] text-primary/80 font-mono italic shrink-0">running...</span>
			)}
		</div>

		{items && items.length > 0 && (
			<div className="mt-0.5 space-y-0.5">
				{items.map((item) => (
					<p key={`${itemKey}-${item}`} className="text-[10px] text-muted-foreground/80 truncate">
						{item}
					</p>
				))}
			</div>
		)}
	</div>
);
