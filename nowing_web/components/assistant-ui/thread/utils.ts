"use client";

import type { SuggestionAnchorRect } from "@/components/assistant-ui/inline-mention-editor";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import type { ComposerSuggestionAnchorPoint } from "./types";

export function getComposerSuggestionAnchorPoint(
	triggerRect: SuggestionAnchorRect | null,
	side: "top" | "bottom"
): ComposerSuggestionAnchorPoint | null {
	if (!triggerRect) return null;
	return {
		left: triggerRect.left,
		top: side === "bottom" ? triggerRect.bottom : triggerRect.top,
	};
}

export function formatToolName(name: string): string {
	return getToolDisplayName(name);
}

export function _getTimeBasedGreeting(user?: {
	display_name?: string | null;
	email?: string;
}): string {
	const hour = new Date().getHours();

	let firstName: string | null = null;
	if (user?.display_name?.trim()) {
		const nameParts = user.display_name.trim().split(/\s+/);
		firstName = nameParts[0].charAt(0).toUpperCase() + nameParts[0].slice(1).toLowerCase();
	} else if (user?.email) {
		firstName =
			user.email.split("@")[0].split(".")[0].charAt(0).toUpperCase() +
			user.email.split("@")[0].split(".")[0].slice(1);
	}

	const morningGreetings = ["Good morning", "Fresh start today", "Morning", "Hey there"];
	const afternoonGreetings = ["Good afternoon", "Afternoon", "Hey there", "Hi there"];
	const eveningGreetings = ["Good evening", "Evening", "Hey there", "Hi there"];
	const nightGreetings = ["Good night", "Evening", "Hey there", "Winding down"];
	const lateNightGreetings = ["Still up", "Night owl mode", "Up past bedtime", "Hi there"];

	let greeting: string;
	if (hour < 5) {
		greeting = lateNightGreetings[Math.floor(Math.random() * lateNightGreetings.length)];
	} else if (hour < 12) {
		greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
	} else if (hour < 18) {
		greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
	} else if (hour < 22) {
		greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
	} else {
		greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
	}

	return firstName ? `${greeting}, ${firstName}!` : `${greeting}!`;
}
