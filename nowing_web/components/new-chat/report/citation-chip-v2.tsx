"use client";

import { Clock, AlertTriangle, CheckCircle2 } from "lucide-react";
import { memo, useState } from "react";
import { cn } from "@/lib/utils";
import type { CryptoDataCitation } from "@/components/tool-ui/citation/schema";

// ─── Source favicon ───────────────────────────────────────────────────────────

const PROVIDER_ICONS: Record<string, string> = {
	defillama: "🦙",
	coingecko: "🦎",
	goplus: "🛡️",
	etherscan: "⬡",
	dexscreener: "📊",
	nansen: "🔮",
};

function providerIcon(provider: string): string {
	return PROVIDER_ICONS[provider.toLowerCase()] ?? "🌐";
}

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24h — data was fresh at generation time

function isStale(citation: CryptoDataCitation): boolean {
	if (citation.stalenessMs !== undefined) return citation.stalenessMs > STALE_THRESHOLD_MS;
	const source = citation.sources[0];
	if (!source?.fetchedAt) return false;
	return Date.now() - new Date(source.fetchedAt).getTime() > STALE_THRESHOLD_MS;
}

// ─── Chip variants ────────────────────────────────────────────────────────────

interface CitationChipV2Props {
	citation: CryptoDataCitation;
	onOpen?: (citation: CryptoDataCitation) => void;
	className?: string;
}

const CitationChipV2Impl = ({ citation, onOpen, className }: CitationChipV2Props) => {
	const [hovered, setHovered] = useState(false);

	const stale = isStale(citation);
	const verified = !citation.conflict && citation.sources.length >= 2;
	const primary = citation.sources[0];

	const handleClick = () => onOpen?.(citation);

	if (citation.conflict) {
		// Conflict variant: amber border, all source values
		const values = citation.sources.map((s) => s.rawValue ?? citation.value);
		return (
			<button
				type="button"
				onClick={handleClick}
				onMouseEnter={() => setHovered(true)}
				onMouseLeave={() => setHovered(false)}
				className={cn(
					"inline-flex items-center gap-1 rounded border border-amber-400/60 bg-amber-50/10 px-1.5 py-0.5 text-xs font-medium tabular-nums",
					"cursor-pointer transition-colors hover:bg-amber-100/20 dark:hover:bg-amber-900/20",
					hovered && "border-amber-400",
					className
				)}
				aria-label={`Conflicting data for ${citation.value}`}
				data-slot="citation-chip"
				data-variant="conflict"
			>
				<AlertTriangle className="size-3 text-amber-500" aria-hidden="true" />
				{values.slice(0, 2).map((v, i) => (
					<span key={i}>
						{i > 0 && <span className="text-muted-foreground/60">·</span>}
						{v}
						<span className="ml-0.5 opacity-60">
							{providerIcon(citation.sources[i]?.provider ?? "")}
						</span>
					</span>
				))}
			</button>
		);
	}

	if (stale) {
		// Stale variant: muted gray
		return (
			<button
				type="button"
				onClick={handleClick}
				className={cn(
					"inline-flex items-center gap-1 rounded bg-muted/60 px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground",
					"cursor-pointer transition-colors hover:bg-muted",
					className
				)}
				aria-label={`Stale data: ${citation.value}`}
				data-slot="citation-chip"
				data-variant="stale"
			>
				{citation.value}
				<span aria-hidden="true">{primary ? providerIcon(primary.provider) : "🌐"}</span>
				<Clock className="size-3" aria-hidden="true" />
			</button>
		);
	}

	if (verified) {
		// Verified variant: green checkmark, multiple source icons
		return (
			<button
				type="button"
				onClick={handleClick}
				className={cn(
					"inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium tabular-nums text-emerald-700 dark:text-emerald-400",
					"cursor-pointer transition-colors hover:bg-emerald-500/20",
					className
				)}
				aria-label={`Verified: ${citation.value} from ${citation.sources.length} sources`}
				data-slot="citation-chip"
				data-variant="verified"
			>
				{citation.value}
				<CheckCircle2 className="size-3" aria-hidden="true" />
				{citation.sources.slice(0, 2).map((s, i) => (
					<span key={i} aria-hidden="true">
						{providerIcon(s.provider)}
					</span>
				))}
			</button>
		);
	}

	// Default variant
	return (
		<button
			type="button"
			onClick={handleClick}
			className={cn(
				"inline-flex items-center gap-1 rounded bg-muted/40 px-1.5 py-0.5 text-xs tabular-nums",
				"cursor-pointer transition-colors hover:bg-muted",
				className
			)}
			aria-label={`${citation.value} from ${primary?.provider ?? "unknown source"}`}
			data-slot="citation-chip"
			data-variant="default"
		>
			{citation.value}
			{primary && (
				<>
					<span aria-hidden="true">{providerIcon(primary.provider)}</span>
					<span className="text-muted-foreground/60">{primary.provider}</span>
				</>
			)}
		</button>
	);
};

export const CitationChipV2 = memo(CitationChipV2Impl);
