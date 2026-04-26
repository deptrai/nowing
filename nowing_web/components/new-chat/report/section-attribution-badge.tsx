"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { CryptoDataCitationMap } from "@/components/tool-ui/citation/schema";

interface SectionAttributionBadgeProps {
	sectionId: string;
	citationMap: CryptoDataCitationMap;
	className?: string;
}

const PROVIDER_COLORS: Record<string, string> = {
	coingecko: "var(--source-coingecko)",
	defillama: "var(--source-defillama)",
	goplus: "var(--source-goplus)",
	etherscan: "var(--source-etherscan)",
	dexscreener: "var(--source-dexscreener)",
};

function getProviderColor(provider: string): string {
	const key = provider.toLowerCase();
	for (const [k, v] of Object.entries(PROVIDER_COLORS)) {
		if (key.includes(k)) return v;
	}
	return "var(--muted-foreground)";
}

function ProviderDot({ provider }: { provider: string }) {
	return (
		<span
			className="inline-block size-1.5 rounded-full"
			style={{ background: getProviderColor(provider) }}
			title={provider}
		/>
	);
}

function SectionAttributionBadgeImpl({
	sectionId,
	citationMap,
	className,
}: SectionAttributionBadgeProps) {
	// Collect providers cited in this section by checking citation IDs that share the section prefix
	const sectionPrefix = sectionId.toLowerCase().replace(/[^a-z0-9]/g, "-");
	const providers = new Set<string>();

	for (const [id, citation] of citationMap) {
		if (id.startsWith(sectionPrefix) || id.includes(sectionPrefix)) {
			for (const source of citation.sources) {
				providers.add(source.provider);
			}
		}
	}

	if (providers.size === 0) return null;

	const providerList = [...providers].slice(0, 4);

	return (
		<span
			className={cn(
				"ml-2 inline-flex items-center gap-1 rounded-full border border-border/40 bg-muted/30 px-1.5 py-0.5",
				className
			)}
			title={`Data from: ${providerList.join(", ")}`}
		>
			{providerList.map((p) => (
				<ProviderDot key={p} provider={p} />
			))}
		</span>
	);
}

export const SectionAttributionBadge = memo(SectionAttributionBadgeImpl);
