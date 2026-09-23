"use client";

export interface ThreadProps {
	hasActiveThread?: boolean;
	initialPrompt?: string;
}

export interface ComposerSuggestionAnchorPoint {
	left: number;
	top: number;
}
