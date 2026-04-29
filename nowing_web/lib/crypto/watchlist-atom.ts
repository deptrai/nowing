import { atom } from "jotai";
import { atomFamily, atomWithStorage, createJSONStorage } from "jotai/utils";

export interface WatchlistToken {
	symbol: string;
	name: string;
	addedAt: number;
}

// Max 50 tokens in watchlist
const MAX_WATCHLIST_SIZE = 50;

function isValidToken(t: unknown): t is WatchlistToken {
	return (
		typeof t === "object" &&
		t !== null &&
		typeof (t as WatchlistToken).symbol === "string" &&
		typeof (t as WatchlistToken).name === "string" &&
		typeof (t as WatchlistToken).addedAt === "number"
	);
}

const baseStorage = createJSONStorage<WatchlistToken[]>(() =>
	typeof window !== "undefined" ? window.localStorage : (undefined as unknown as Storage)
);

// Defensive validating storage — guards against manual edits or version drift
const validatingStorage: typeof baseStorage = {
	...baseStorage,
	getItem(key, initialValue) {
		try {
			const raw = baseStorage.getItem(key, initialValue);
			if (!Array.isArray(raw)) return initialValue;
			return raw.filter(isValidToken);
		} catch {
			return initialValue;
		}
	},
};

export const watchlistAtom = atomWithStorage<WatchlistToken[]>(
	"nowing:watchlist",
	[],
	validatingStorage
);

export const addToWatchlistAtom = atom(
	null,
	(get, set, token: { symbol: string; name: string }) => {
		const current = get(watchlistAtom);
		if (current.some((t) => t.symbol.toLowerCase() === token.symbol.toLowerCase())) return;
		const updated = [
			{ symbol: token.symbol, name: token.name, addedAt: Date.now() },
			...current,
		].slice(0, MAX_WATCHLIST_SIZE);
		set(watchlistAtom, updated);
	}
);

export const removeFromWatchlistAtom = atom(null, (get, set, symbol: string) => {
	set(
		watchlistAtom,
		get(watchlistAtom).filter((t) => t.symbol.toLowerCase() !== symbol.toLowerCase())
	);
});

export const isInWatchlistAtom = atomFamily((symbol: string) =>
	atom((get) => get(watchlistAtom).some((t) => t.symbol.toLowerCase() === symbol.toLowerCase()))
);
