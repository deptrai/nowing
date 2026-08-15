"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

const REFERRAL_COOKIE_NAME = "nowing_ref";
const COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30 days

export function useReferralTracker() {
	const searchParams = useSearchParams();

	useEffect(() => {
		if (!searchParams) return;

		const refCode = searchParams.get("ref") || searchParams.get("nowing_ref");
		if (refCode) {
			const cleanCode = refCode
				.trim()
				.toUpperCase()
				.replace(/[^A-Z0-9_-]/g, "");
			if (cleanCode.length >= 3 && cleanCode.length <= 32) {
				// 1. Set 30-day attribution cookie
				// biome-ignore lint/suspicious/noDocumentCookie: Cookie attribution on public marketing landing page
				document.cookie = `${REFERRAL_COOKIE_NAME}=${cleanCode}; max-age=${COOKIE_MAX_AGE_SECONDS}; path=/; SameSite=Lax`;

				// 2. Persist to localStorage for fallback
				try {
					localStorage.setItem(REFERRAL_COOKIE_NAME, cleanCode);
				} catch {
					// Ignore localStorage exceptions in private browsing
				}
			}
		}
	}, [searchParams]);
}
