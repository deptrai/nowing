"use client";

import { ChevronDown, Clipboard, X } from "lucide-react";
import { type FC, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const ClipboardChip: FC<{ text: string; onDismiss: () => void }> = ({ text, onDismiss }) => {
	const [expanded, setExpanded] = useState(false);
	const isLong = text.length > 120;
	const preview = isLong ? `${text.slice(0, 120)}…` : text;

	return (
		<div className="mx-3 mt-2 rounded-lg border border-border/40 bg-background/60">
			<div className="flex items-center gap-2 px-3 py-2">
				<Clipboard className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
				<span className="text-xs font-medium text-muted-foreground">From clipboard</span>
				<div className="flex-1" />
				{isLong && (
					<Button
						type="button"
						onClick={() => setExpanded((v) => !v)}
						variant="ghost"
						size="icon"
						className="size-5 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
					>
						<ChevronDown
							className={cn("size-3.5 transition-transform", expanded && "rotate-180")}
						/>
					</Button>
				)}
				<Button
					type="button"
					onClick={onDismiss}
					variant="ghost"
					size="icon"
					className="size-5 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
				>
					<X className="size-3.5" aria-hidden="true" />
				</Button>
			</div>
			<div className="px-3 pb-2">
				<p className="text-xs text-foreground/80 whitespace-pre-wrap wrap-break-word leading-relaxed">
					{expanded ? text : preview}
				</p>
			</div>
		</div>
	);
};
