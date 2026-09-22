import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
import { routing } from "./routing";

/**
 * Cookie carrying the user's chosen/detected locale to the server so Server
 * Components using getTranslations render in the right language. LocaleContext
 * writes this cookie alongside localStorage (this app has no [locale] route).
 */
const LOCALE_COOKIE = "NEXT_LOCALE";

export default getRequestConfig(async ({ requestLocale }) => {
	// Prefer the explicit user choice stored in the cookie over the (usually
	// absent) requestLocale segment, since this app uses client-side locale.
	const cookieLocale = (await cookies()).get(LOCALE_COOKIE)?.value;
	let locale =
		cookieLocale && routing.locales.includes(cookieLocale as (typeof routing.locales)[number])
			? cookieLocale
			: await requestLocale;

	if (!locale || !routing.locales.includes(locale as (typeof routing.locales)[number])) {
		locale = routing.defaultLocale;
	}

	return {
		locale,
		messages: (await import(`../messages/${locale}.json`)).default,
		timeZone: "UTC",
	};
});
