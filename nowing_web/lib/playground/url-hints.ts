import { tryGetHostname } from "../url";

/**
 * URL fields that map to platform-host expectations. Instagram `urls`
 * accepts bare handles, so it is always skipped.
 */
const SUFFIX_HOSTS: Record<string, string[]> = {
	reddit: ["reddit.com", "redd.it"],
	youtube: ["youtube.com", "youtu.be"],
	tiktok: ["tiktok.com"],
	google_maps: ["google.com", "maps.google.com"],
};

const URL_FIELD_NAMES = new Set(["urls", "video_urls", "startUrls"]);

const AMAZON_TLDS = new Set([
	"com",
	"ca",
	"com.mx",
	"com.br",
	"com.au",
	"com.tr",
	"de",
	"es",
	"fr",
	"it",
	"nl",
	"se",
	"pl",
	"co.uk",
	"co.jp",
	"in",
	"sg",
	"ae",
	"sa",
	"eg",
]);

const AMAZON_HOSTNAME_RE = new RegExp(
	`^amazon\\.(${[...AMAZON_TLDS].map((t) => t.replace(/\./g, "\\.")).join("|")})$`
);

const KNOWN_PLATFORMS = new Set(["amazon", ...Object.keys(SUFFIX_HOSTS)]);

function isPlatformHost(platform: string, hostname: string): boolean {
	if (platform === "amazon") return AMAZON_HOSTNAME_RE.test(hostname);
	const hosts = SUFFIX_HOSTS[platform];
	if (!hosts) return false;
	return hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`));
}

/**
 * Warning hint for a single URL value: hostname mismatch vs the platform.
 * Returns `undefined` when the platform/field is unknown, the value is
 * empty or unparseable, or the host matches the platform.
 */
export function urlFieldWarning(
	platform: string,
	fieldName: string,
	value: string
): string | undefined {
	if (
		!URL_FIELD_NAMES.has(fieldName) ||
		platform === "instagram" ||
		!KNOWN_PLATFORMS.has(platform)
	) {
		return undefined;
	}
	if (typeof value !== "string" || value.trim() === "") return undefined;
	const hostname = tryGetHostname(value.trim());
	if (!hostname || isPlatformHost(platform, hostname)) return undefined;
	return `"${hostname}" doesn't look like a ${platform} URL`;
}

/**
 * Collect hints for every URL field in the current form values.
 * Values are raw textarea strings (one URL per line); the first
 * offending line per field wins.
 */
export function urlFieldWarnings(
	platform: string,
	values: Record<string, unknown>
): Record<string, string> {
	const warnings: Record<string, string> = {};
	if (!values || typeof values !== "object") return warnings;
	for (const fieldName of Object.keys(values)) {
		if (!URL_FIELD_NAMES.has(fieldName)) continue;
		const raw = values[fieldName];
		if (typeof raw !== "string" || raw.trim() === "") continue;
		for (const line of raw.split("\n")) {
			const warning = urlFieldWarning(platform, fieldName, line.trim());
			if (warning) {
				warnings[fieldName] = warning;
				break;
			}
		}
	}
	return warnings;
}
