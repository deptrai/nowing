"use client";

import { useAuiState } from "@assistant-ui/react";
import dynamic from "next/dynamic";
import { memo, useMemo, useState } from "react";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { CryptoCitationProvider } from "./crypto-citation-context";
import type { CryptoDataCitation } from "@/components/tool-ui/citation/schema";

const TokenHeroCard = dynamic(() => import("./token-hero-card").then((m) => m.TokenHeroCard), {
	ssr: false,
});
const ReportTOC = dynamic(() => import("./report-toc").then((m) => m.ReportTOC), { ssr: false });
const SourceDetailPanel = dynamic(
	() => import("./source-detail-panel").then((m) => m.SourceDetailPanel),
	{ ssr: false }
);

const SENTINEL = "<!-- crypto-report-v2 -->";

interface CryptoReportMeta {
	report_type?: string;
	citation_map?: Record<string, unknown>;
	token_symbol?: string;
	token_name?: string;
	coingecko_id?: string;
}

function isCryptoReport(text: string, meta: CryptoReportMeta | null): boolean {
	if (meta?.report_type === "comprehensive_crypto") return true;
	return text.includes(SENTINEL);
}

const CryptoReportLayoutImpl = () => {
	const { text, meta } = useAuiState(({ message }) => {
		const parts = (message as { content?: { type: string; text?: string }[] })?.content ?? [];
		const textPart = parts.find((p) => p.type === "text");
		const rawCustom = (message as { metadata?: { custom?: unknown } })?.metadata
			?.custom as CryptoReportMeta | null;
		return { text: textPart?.text ?? "", meta: rawCustom ?? null };
	});

	const [selectedCitation, setSelectedCitation] = useState<CryptoDataCitation | null>(null);
	const [panelOpen, setPanelOpen] = useState(false);

	const isCrypto = useMemo(() => isCryptoReport(text, meta), [text, meta]);

	const openCitation = (citation: CryptoDataCitation) => {
		setSelectedCitation(citation);
		setPanelOpen(true);
	};

	if (!isCrypto) return <MarkdownText />;

	const cleanText = text.replace(SENTINEL, "").trimStart();

	return (
		<CryptoCitationProvider
			citationMap={meta?.citation_map as Record<string, CryptoDataCitation> | undefined}
			onOpenCitation={openCitation}
		>
			<div className="relative flex gap-0 lg:gap-6" data-slot="crypto-report-layout">
				<ReportTOC content={cleanText} className="hidden lg:block" />
				<div className="min-w-0 flex-1">
					<TokenHeroCard
						symbol={meta?.token_symbol}
						name={meta?.token_name}
						coingeckoId={meta?.coingecko_id}
						reportText={cleanText}
					/>
					<div className="mt-4">
						<MarkdownText />
					</div>
				</div>
			</div>
			<SourceDetailPanel
				citation={selectedCitation}
				open={panelOpen}
				onClose={() => setPanelOpen(false)}
			/>
		</CryptoCitationProvider>
	);
};

export const CryptoReportLayout = memo(CryptoReportLayoutImpl);
