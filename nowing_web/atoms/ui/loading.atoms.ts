import { atom } from "jotai";

interface GlobalLoadingState {
	isLoading: boolean;
}

export const globalLoadingAtom = atom<GlobalLoadingState>({
	isLoading: false,
});

// Helper atom for showing global loading
export const showGlobalLoadingAtom = atom(null, (_get, set) => {
	set(globalLoadingAtom, { isLoading: true });
});

// Helper atom for hiding global loading
export const hideGlobalLoadingAtom = atom(null, (_get, set) => {
	set(globalLoadingAtom, { isLoading: false });
});
