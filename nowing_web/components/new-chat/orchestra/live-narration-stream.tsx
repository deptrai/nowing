"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface LiveNarrationStreamProps {
	text: string | null;
	className?: string;
}

/**
 * AC8: Single-line narration with cross-fade transition between texts.
 * - Old text fades out (~200ms) before new text fades in (~200ms)
 * - Long text truncated with ellipsis (single line)
 * - Re-mount via key on text change so animation runs each transition
 */
export function LiveNarrationStream({ text, className }: LiveNarrationStreamProps) {
	const [visibleText, setVisibleText] = useState(text);
	const [outgoing, setOutgoing] = useState<string | null>(null);
	const [fadeKey, setFadeKey] = useState(0);
	const prevRef = useRef(text);
	// V2-P5: when a new text arrives mid-fade-out, jump straight to the new
	// text instead of clobbering with stale outgoing — prevents "flash B
	// fading out, never appears" race when narrations arrive < 180ms apart.
	const fadingRef = useRef(false);

	useEffect(() => {
		if (text !== prevRef.current) {
			const oldText = prevRef.current;
			prevRef.current = text;

			if (fadingRef.current) {
				// Already mid-fade — skip the cross-fade choreography and just
				// swap to the latest text. The pending timer's setVisibleText
				// will be overridden by this synchronous setVisibleText.
				setOutgoing(null);
				setVisibleText(text);
				setFadeKey((k) => k + 1);
				return;
			}

			if (oldText) {
				fadingRef.current = true;
				setOutgoing(oldText);
				const t1 = setTimeout(() => {
					fadingRef.current = false;
					setOutgoing(null);
					setVisibleText(prevRef.current);
					setFadeKey((k) => k + 1);
				}, 200);
				return () => {
					clearTimeout(t1);
					fadingRef.current = false;
				};
			}
			setVisibleText(text);
			setFadeKey((k) => k + 1);
		}
	}, [text]);

	if (!visibleText && !outgoing) return null;

	return (
		<div
			className={cn("relative h-[1.5em] overflow-hidden", className)}
			aria-live="polite"
			aria-atomic="true"
		>
			{outgoing && (
				<p
					className="absolute inset-0 truncate animate-fade-out text-muted-foreground"
					aria-hidden="true"
				>
					{outgoing}
				</p>
			)}
			{visibleText && !outgoing && (
				<p
					key={fadeKey}
					className="absolute inset-0 truncate animate-fade-in text-muted-foreground"
				>
					{visibleText}
				</p>
			)}
		</div>
	);
}
