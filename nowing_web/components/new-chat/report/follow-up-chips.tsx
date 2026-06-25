"use client";

import { useAui } from "@assistant-ui/react";
import { SparklesIcon } from "lucide-react";
import { useCallback } from "react";
import { cn } from "@/lib/utils";

interface FollowUpChipsProps {
	followUps: string[];
	className?: string;
}

export function FollowUpChips({ followUps, className }: FollowUpChipsProps) {
	const aui = useAui();

	const handleChipClick = useCallback(
		(question: string) => {
			const composer = aui?.composer?.();
			if (!composer) return;
			composer.setText(question);
			const textarea = document.querySelector<HTMLElement>(".aui-composer-input");
			textarea?.focus();
		},
		[aui]
	);

	if (!followUps.length) return null;

	return (
		<div className={cn("mt-4 flex flex-col gap-2", className)} data-slot="follow-up-chips">
			<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
				<SparklesIcon className="size-3" />
				<span>Suggested follow-up questions</span>
			</div>
			<div className="flex flex-wrap gap-2">
				{followUps.map((q, idx) => (
					<button
						key={`${idx}-${q}`}
						onClick={() => handleChipClick(q)}
						className="inline-flex max-w-[280px] items-center rounded-full border bg-background px-3 py-1.5 text-xs text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring truncate"
						title={q}
					>
						{q}
					</button>
				))}
			</div>
		</div>
	);
}
