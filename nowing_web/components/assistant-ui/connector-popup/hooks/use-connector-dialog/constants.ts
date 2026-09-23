"use client";

import { OAUTH_RESULT_COOKIE } from "@/contracts/types/oauth.types";

export function readOAuthResultCookie(): string | null {
	const match = document.cookie
		.split("; ")
		.find((row) => row.startsWith(`${OAUTH_RESULT_COOKIE}=`));
	return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

export function clearOAuthResultCookie(): void {
	// biome-ignore lint: only standard way to expire a cookie
	document.cookie = `${OAUTH_RESULT_COOKIE}=; path=/; max-age=0`;
}

export function getFrequencyLabel(minutes: string): string {
	switch (minutes) {
		case "15":
			return "15 minutes";
		case "60":
			return "hour";
		case "360":
			return "6 hours";
		case "720":
			return "12 hours";
		case "1440":
			return "day";
		case "10080":
			return "week";
		default:
			return `${minutes} minutes`;
	}
}
