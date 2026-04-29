"use client";

import { cn } from "@/lib/utils";
import { type Source } from "@/atoms/chat/orchestra.atom";

interface SourceFaviconRiverProps {
	sources: Source[];
	className?: string;
}

/**
 * Horizontally scrollable row of source domain chips with favicons.
 * Deduplication is handled upstream (orchestraAtom) — this component
 * renders what it receives.
 */
export function SourceFaviconRiver({ sources, className }: SourceFaviconRiverProps) {
	if (sources.length === 0) return null;

	return (
		<div
			className={cn("flex flex-wrap gap-1", className)}
			data-slot="source-favicon-river"
			aria-label={`Sources: ${sources.map((s) => s.domain).join(", ")}`}
		>
			{sources.map((src) => (
				<SourceChip key={src.domain} source={src} />
			))}
		</div>
	);
}

function SourceChip({ source }: { source: Source }) {
	const chipBody = (
		<>
			{/* P22: only render <img> when favicon is non-empty to avoid empty-src
			    fetch loop in some browsers. Fall back to a neutral dot. */}
			{source.favicon ? (
				/* eslint-disable-next-line @next/next/no-img-element */
				<img
					src={source.favicon}
					alt=""
					width={12}
					height={12}
					className="size-3 rounded-full object-contain"
					onError={(e) => {
						(e.currentTarget as HTMLImageElement).style.display = "none";
					}}
				/>
			) : (
				<span className="size-3 rounded-full bg-muted-foreground/30" aria-hidden="true" />
			)}
			<span className="max-w-[80px] truncate">{source.domain}</span>
		</>
	);

	const className =
		"inline-flex animate-fade-in items-center gap-1 rounded-full border border-border/40 bg-muted/50 px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted";

	if (source.url) {
		return (
			<a
				href={source.url}
				target="_blank"
				rel="noopener noreferrer"
				className={className}
				title={source.domain}
			>
				{chipBody}
			</a>
		);
	}
	return (
		<span className={className} title={source.domain}>
			{chipBody}
		</span>
	);
}
