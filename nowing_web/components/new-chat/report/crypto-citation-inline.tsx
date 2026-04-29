"use client";

import { memo } from "react";
import { CitationChipV2 } from "./citation-chip-v2";
import { useCryptoCitation, useOpenCitation } from "./crypto-citation-context";

interface CryptoCitationInlineProps {
	citationId: string;
	displayValue: string;
}

const CryptoCitationInlineImpl = ({ citationId, displayValue }: CryptoCitationInlineProps) => {
	const citation = useCryptoCitation(citationId);
	const openCitation = useOpenCitation();

	if (!citation) {
		return <span className="tabular-nums text-muted-foreground">{displayValue}</span>;
	}

	return <CitationChipV2 citation={citation} onOpen={openCitation} />;
};

export const CryptoCitationInline = memo(CryptoCitationInlineImpl);
