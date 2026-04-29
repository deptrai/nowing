import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";

export interface PriceAlert {
	id: string;
	symbol: string;
	name: string;
	threshold: number;
	direction: "above" | "below";
	createdAt: number;
}

function isValidAlert(a: unknown): a is PriceAlert {
	if (typeof a !== "object" || a === null) return false;
	const x = a as PriceAlert;
	return (
		typeof x.id === "string" &&
		typeof x.symbol === "string" &&
		typeof x.name === "string" &&
		typeof x.threshold === "number" &&
		Number.isFinite(x.threshold) &&
		(x.direction === "above" || x.direction === "below") &&
		typeof x.createdAt === "number"
	);
}

const baseStorage = createJSONStorage<PriceAlert[]>(() =>
	typeof window !== "undefined" ? window.localStorage : (undefined as unknown as Storage)
);

const validatingStorage: typeof baseStorage = {
	...baseStorage,
	getItem(key, initialValue) {
		try {
			const raw = baseStorage.getItem(key, initialValue);
			if (!Array.isArray(raw)) return initialValue;
			return raw.filter(isValidAlert);
		} catch {
			return initialValue;
		}
	},
};

export const priceAlertsAtom = atomWithStorage<PriceAlert[]>(
	"nowing:price-alerts",
	[],
	validatingStorage
);

export const createPriceAlertAtom = atom(
	null,
	(get, set, alert: Omit<PriceAlert, "id" | "createdAt">) => {
		const current = get(priceAlertsAtom);
		const newAlert: PriceAlert = {
			...alert,
			id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
			createdAt: Date.now(),
		};
		set(priceAlertsAtom, [newAlert, ...current]);
	}
);

export const removePriceAlertAtom = atom(null, (get, set, id: string) => {
	set(
		priceAlertsAtom,
		get(priceAlertsAtom).filter((a) => a.id !== id)
	);
});
