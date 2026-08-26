"use client";

import type React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import enMessages from "../messages/en.json";

export type Locale = "en" | "vi" | "es" | "pt" | "hi" | "zh" | "ko";

export const SUPPORTED_LOCALES: readonly Locale[] = [
	"en",
	"vi",
	"es",
	"pt",
	"hi",
	"zh",
	"ko",
] as const;

/**
 * Dynamically load locale messages on demand.
 * English is the default and always available synchronously.
 */
const loadMessages = async (locale: Locale): Promise<typeof enMessages> => {
	switch (locale) {
		case "vi":
			return (await import("../messages/vi.json")).default as unknown as typeof enMessages;
		case "es":
			return (await import("../messages/es.json")).default as unknown as typeof enMessages;
		case "hi":
			return (await import("../messages/hi.json")).default as unknown as typeof enMessages;
		case "pt":
			return (await import("../messages/pt.json")).default as unknown as typeof enMessages;
		case "zh":
			return (await import("../messages/zh.json")).default as unknown as typeof enMessages;
		case "ko":
			return (await import("../messages/ko.json")).default as unknown as typeof enMessages;
		default:
			return enMessages;
	}
};

interface LocaleContextType {
	locale: Locale;
	messages: typeof enMessages;
	setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextType | undefined>(undefined);

const LOCALE_STORAGE_KEY = "nowing-locale";

/**
 * Detect initial locale based on browser languages and timezone.
 * Defaults to 'vi' for Vietnamese browser language or Vietnam timezones,
 * or other supported languages if matched, otherwise 'en'.
 */
export function detectInitialLocale(): Locale {
	if (typeof window === "undefined") return "en";

	// 1. Check browser navigator languages
	const navLangs = window.navigator.languages || [window.navigator.language || ""];
	for (const lang of navLangs) {
		if (!lang) continue;
		const code = lang.toLowerCase();
		if (code.startsWith("vi")) return "vi";
		if (code.startsWith("es")) return "es";
		if (code.startsWith("pt")) return "pt";
		if (code.startsWith("hi")) return "hi";
		if (code.startsWith("zh")) return "zh";
		if (code.startsWith("ko")) return "ko";
		if (code.startsWith("en")) return "en";
	}

	// 2. Check timezone for Vietnam / Indochina
	try {
		const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
		if (
			timeZone === "Asia/Ho_Chi_Minh" ||
			timeZone === "Asia/Saigon" ||
			timeZone === "Asia/Hanoi" ||
			timeZone === "Asia/Bangkok"
		) {
			return "vi";
		}
	} catch {
		// Ignore timezone detection errors
	}

	return "en";
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
	// Always start with 'en' to avoid hydration mismatch
	// Then sync with localStorage after mount
	const [locale, setLocaleState] = useState<Locale>("en");
	const [messages, setMessages] = useState<typeof enMessages>(enMessages);
	const [mounted, setMounted] = useState(false);

	// Load locale from localStorage after component mounts (client-side only)
	useEffect(() => {
		setMounted(true);
		if (typeof window !== "undefined") {
			const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
			if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
				const storedLocale = stored as Locale;
				setLocaleState(storedLocale);
				// Load messages for non-English locale
				if (storedLocale !== "en") {
					loadMessages(storedLocale).then(setMessages);
				}
			} else if (!stored) {
				// First-time visit: auto-detect locale and persist preference
				const detected = detectInitialLocale();
				setLocaleState(detected);
				localStorage.setItem(LOCALE_STORAGE_KEY, detected);
				if (detected !== "en") {
					loadMessages(detected).then(setMessages);
				}
			}
		}
	}, []);

	// Update locale and persist to localStorage
	const setLocale = useCallback(async (newLocale: Locale) => {
		// Load messages for the new locale
		const newMessages = await loadMessages(newLocale);
		setMessages(newMessages);
		setLocaleState(newLocale);
		if (typeof window !== "undefined") {
			localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
			// Update HTML lang attribute
			document.documentElement.lang = newLocale;
		}
	}, []);

	// Set HTML lang attribute when locale changes
	useEffect(() => {
		if (typeof window !== "undefined" && mounted) {
			document.documentElement.lang = locale;
		}
	}, [locale, mounted]);

	const contextValue = useMemo(
		() => ({ locale, messages, setLocale }),
		[locale, messages, setLocale]
	);

	return <LocaleContext.Provider value={contextValue}>{children}</LocaleContext.Provider>;
}

export function useLocaleContext() {
	const context = useContext(LocaleContext);
	if (context === undefined) {
		throw new Error("useLocaleContext must be used within a LocaleProvider");
	}
	return context;
}
