/**
 * Non-hook translation helper for toast messages fired from jotai atoms and
 * other module code that runs outside React's render tree (where
 * `useTranslations` is unavailable).
 *
 * Reads the current locale from the same sources as LocaleContext
 * (`nowing-locale` localStorage key, falling back to the NEXT_LOCALE cookie)
 * and resolves a dot-separated key against the corresponding messages bundle.
 *
 * English is always loaded synchronously; other locales are loaded on demand
 * and cached. Falls back to English (then to the key itself) when a key is
 * missing.
 */
import enMessages from "../messages/en.json";

type Messages = Record<string, unknown>;

const LOCALE_STORAGE_KEY = "nowing-locale";
const LOCALE_COOKIE = "NEXT_LOCALE";

const messageCache = new Map<string, Messages>();
let enCache: Messages | null = null;

function getEnglishMessages(): Messages {
	if (!enCache) enCache = enMessages as Messages;
	return enCache;
}

async function loadMessages(locale: string): Promise<Messages> {
	if (locale === "en") return getEnglishMessages();
	const cached = messageCache.get(locale);
	if (cached) return cached;
	const mod = await import(`../messages/${locale}.json`);
	const messages = mod.default as Messages;
	messageCache.set(locale, messages);
	return messages;
}

function readStoredLocale(): string {
	if (typeof window === "undefined") return "en";
	try {
		const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
		if (stored) return stored;
		return document.cookie.match(new RegExp(`${LOCALE_COOKIE}=(\\w+)`))?.[1] ?? "en";
	} catch {
		return "en";
	}
}

function lookup(messages: Messages, key: string): string | undefined {
	let node: unknown = messages;
	for (const part of key.split(".")) {
		if (node && typeof node === "object" && part in (node as Messages)) {
			node = (node as Messages)[part];
		} else {
			return undefined;
		}
	}
	return typeof node === "string" ? node : undefined;
}

/**
 * Translate a dot-separated message key for toast display outside React.
 * Synchronous: uses the cached bundle for the stored locale (English on
 * first call in a non-English session — the async prefetch below warms the
 * cache right after module load).
 */
export function translateToast(key: string, params?: Record<string, unknown>): string {
	const locale = readStoredLocale();
	const messages = messageCache.get(locale) ?? getEnglishMessages();
	let text = lookup(messages, key) ?? lookup(getEnglishMessages(), key) ?? key;
	if (params) {
		for (const [name, value] of Object.entries(params)) {
			text = text.replaceAll(`{${name}}`, String(value));
		}
	}
	return text;
}

// Warm the cache for the active non-English locale so the first toast renders
// in the right language.
if (typeof window !== "undefined") {
	const locale = readStoredLocale();
	if (locale !== "en") {
		void loadMessages(locale).catch(() => {});
	}
}
