"use client";

import { BarChart2, ExternalLink, X } from "lucide-react";
import { memo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { CryptoDataCitation } from "@/components/tool-ui/citation/schema";

interface SourceDetailPanelProps {
	citation: CryptoDataCitation | null;
	open: boolean;
	onClose: () => void;
}

function ProviderBadge({ provider }: { provider: string }) {
	return (
		<span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
			{provider}
		</span>
	);
}

function JsonBlock({ data }: { data: unknown }) {
	const [expanded, setExpanded] = useState(false);
	const json = JSON.stringify(data, null, 2);
	const preview = json.length > 300 ? json.slice(0, 300) + "..." : json;

	return (
		<div className="rounded-md border border-border/60 bg-muted/30 p-2 font-mono text-[11px]">
			<pre className="overflow-x-auto whitespace-pre-wrap break-all">
				{expanded ? json : preview}
			</pre>
			{json.length > 300 && (
				<button
					type="button"
					onClick={() => setExpanded((v) => !v)}
					className="mt-1 text-xs text-primary hover:underline"
				>
					{expanded ? "Show less" : "Show more"}
				</button>
			)}
		</div>
	);
}

/** Prominent CTA shown when the citation includes a Dune Analytics source (Story 9-UX-4 AC9) */
function DuneDeeplinkButton({ url }: { url: string }) {
	return (
		<a
			href={url}
			target="_blank"
			rel="noopener noreferrer"
			className={cn(
				"mb-4 flex w-full items-center justify-center gap-2 rounded-lg border-2 px-4 py-2.5 text-sm font-semibold no-underline transition-colors",
				"border-[var(--source-dune)]/50 bg-[var(--source-dune)]/10 text-[var(--source-dune)]",
				"hover:border-[var(--source-dune)] hover:bg-[var(--source-dune)]/20"
			)}
			data-slot="dune-deeplink-button"
		>
			<BarChart2 className="size-4 shrink-0" aria-hidden="true" />
			View on Dune Analytics →
		</a>
	);
}

const SourceDetailPanelImpl = ({ citation, open, onClose }: SourceDetailPanelProps) => {
	if (!citation) return null;

	const isConflict = citation.conflict;

	// Dune deeplink: first Dune source that has a rawUrl (Story 9-UX-4 AC9)
	const duneUrl = citation.sources.find(
		(s) => s.provider.toLowerCase() === "dune" && s.rawUrl
	)?.rawUrl;

	return (
		<Sheet open={open} onOpenChange={(v) => !v && onClose()}>
			<SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
				<SheetHeader className="mb-4">
					<div className="flex items-center justify-between">
						<SheetTitle className="text-base">
							{isConflict ? (
								<span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
									⚠️ Data Conflict
								</span>
							) : (
								<span>Source Detail</span>
							)}
						</SheetTitle>
						<Button variant="ghost" size="icon" onClick={onClose} className="size-7">
							<X className="size-4" aria-hidden="true" />
						</Button>
					</div>
				</SheetHeader>

				{/* Reported value */}
				<div className="mb-4 rounded-lg border border-border/60 bg-card p-3">
					<p className="mb-1 text-xs text-muted-foreground">Reported value</p>
					<p className="text-xl font-bold tabular-nums">{citation.value}</p>
					{citation.agentAttribution && (
						<p className="mt-1 text-xs text-muted-foreground">
							Processed by <span className="font-medium">{citation.agentAttribution}</span>
						</p>
					)}
				</div>

				{/* Dune Analytics deeplink (Story 9-UX-4 AC9) */}
				{duneUrl && <DuneDeeplinkButton url={duneUrl} />}

				{/* Conflict resolver: all source values */}
				{isConflict && citation.sources.length >= 2 && (
					<div className="mb-4">
						<p className="mb-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
							Conflicting values across sources
						</p>
						<div className="flex flex-col gap-2">
							{citation.sources.map((s, i) => (
								<div
									key={i}
									className={cn(
										"flex items-center justify-between rounded-md border p-2 text-sm",
										i === 0 ? "border-primary/40" : "border-border/60"
									)}
								>
									<ProviderBadge provider={s.provider} />
									<span className="tabular-nums font-medium">
										{String(s.rawValue ?? citation.value)}
									</span>
								</div>
							))}
						</div>
					</div>
				)}

				{/* Sources list */}
				<div className="space-y-4">
					{citation.sources.map((source, i) => (
						<div key={i} className="rounded-lg border border-border/60 bg-card/50 p-3">
							<div className="mb-2 flex items-center justify-between">
								<ProviderBadge provider={source.provider} />
								<span className="text-xs text-muted-foreground">
									{source.fetchedAt
										? new Date(source.fetchedAt).toLocaleTimeString()
										: "unknown time"}
								</span>
							</div>

							{source.rawUrl && (
								<a
									href={source.rawUrl}
									target="_blank"
									rel="noopener noreferrer"
									className="mb-2 flex items-center gap-1 text-xs text-primary hover:underline"
								>
									View on {source.provider}
									<ExternalLink className="size-3" aria-hidden="true" />
								</a>
							)}

							{source.rawValue !== undefined && <JsonBlock data={source.rawValue} />}
						</div>
					))}
				</div>
			</SheetContent>
		</Sheet>
	);
};

export const SourceDetailPanel = memo(SourceDetailPanelImpl);
