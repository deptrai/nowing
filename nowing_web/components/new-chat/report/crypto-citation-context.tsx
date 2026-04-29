"use client";

import { createContext, type FC, type ReactNode, useCallback, useContext, useMemo } from "react";
import type {
	CryptoDataCitation,
	CryptoDataCitationMap,
} from "@/components/tool-ui/citation/schema";

interface CryptoCitationContextValue {
	map: CryptoDataCitationMap;
	openCitation: (citation: CryptoDataCitation) => void;
}

const CryptoCitationContext = createContext<CryptoCitationContextValue>({
	map: new Map(),
	openCitation: () => undefined,
});

interface CryptoCitationProviderProps {
	children: ReactNode;
	citationMap?: Record<string, CryptoDataCitation>;
	onOpenCitation?: (citation: CryptoDataCitation) => void;
}

export const CryptoCitationProvider: FC<CryptoCitationProviderProps> = ({
	children,
	citationMap,
	onOpenCitation,
}) => {
	const map: CryptoDataCitationMap = useMemo(
		() => (citationMap ? new Map(Object.entries(citationMap)) : new Map()),
		[citationMap]
	);

	const openCitation = useCallback(
		(citation: CryptoDataCitation) => onOpenCitation?.(citation),
		[onOpenCitation]
	);

	return (
		<CryptoCitationContext.Provider value={{ map, openCitation }}>
			{children}
		</CryptoCitationContext.Provider>
	);
};

export function useCryptoCitation(id: string): CryptoDataCitation | undefined {
	const { map } = useContext(CryptoCitationContext);
	return map.get(id);
}

export function useOpenCitation(): (citation: CryptoDataCitation) => void {
	return useContext(CryptoCitationContext).openCitation;
}
