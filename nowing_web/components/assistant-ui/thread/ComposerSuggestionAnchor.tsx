"use client";

import { PopoverAnchor } from "@/components/ui/popover";
import type { ComposerSuggestionAnchorPoint } from "./types";

export function ComposerSuggestionAnchor({ point }: { point: ComposerSuggestionAnchorPoint }) {
	return (
		<PopoverAnchor
			className="pointer-events-none fixed size-0"
			style={{
				left: point.left,
				top: point.top,
			}}
			aria-hidden="true"
		/>
	);
}
