import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

export type CitationTarget = { kind: "chunk"; chunkId: number } | { kind: "run"; runId: string };

interface CitationPanelState {
	isOpen: boolean;
	target: CitationTarget | null;
}

const initialState: CitationPanelState = {
	isOpen: false,
	target: null,
};

export const citationPanelAtom = atom<CitationPanelState>(initialState);

export const citationPanelOpenAtom = atom((get) => get(citationPanelAtom).isOpen);

const preCitationCollapsedAtom = atom<boolean | null>(null);

export const openCitationPanelAtom = atom(null, (get, set, payload: { chunkId: number }) => {
	if (!get(citationPanelAtom).isOpen) {
		set(preCitationCollapsedAtom, get(rightPanelCollapsedAtom));
	}
	set(citationPanelAtom, {
		isOpen: true,
		target: { kind: "chunk", chunkId: payload.chunkId },
	});
	set(rightPanelTabAtom, "citation");
	set(rightPanelCollapsedAtom, false);
});

export const openRunCitationPanelAtom = atom(null, (get, set, payload: { runId: string }) => {
	if (!get(citationPanelAtom).isOpen) {
		set(preCitationCollapsedAtom, get(rightPanelCollapsedAtom));
	}
	set(citationPanelAtom, {
		isOpen: true,
		target: { kind: "run", runId: payload.runId },
	});
	set(rightPanelTabAtom, "citation");
	set(rightPanelCollapsedAtom, false);
});

export const closeCitationPanelAtom = atom(null, (get, set) => {
	set(citationPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preCitationCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preCitationCollapsedAtom, null);
	}
});
