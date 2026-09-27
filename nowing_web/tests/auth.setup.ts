import path from "node:path";
import { expect, test as setup } from "@playwright/test";
import { announcements } from "../lib/announcements/announcements-data";
import { acquireTestToken } from "./helpers/api/auth";

/**
 * One-time authentication setup. Acquires an access token for the seeded
 * e2e user (rate-limit-free /__e2e__/auth/token first, desktop login
 * fallback) and persists it as the session cookie so every test in the
 * chromium project starts already authenticated.
 *
 * Also pre-seeds the localStorage flags that gate the two new-user UI
 * overlays so they never intercept clicks in journeys:
 *   - `nowing_announcements_state` — the blocking AnnouncementSpotlight
 *     dialog (e.g. "Introducing AI Automations") plus its toasts.
 *   - `nowing-tour-<userId>` — the OnboardingTour spotlight for new users.
 */

const authFile = path.join(__dirname, "..", "playwright", ".auth", "user.json");

const PORT = process.env.PORT || "3000";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${PORT}`;
const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME || "nowing_session";
const ANNOUNCEMENTS_KEY = "nowing_announcements_state";

/** Decode the user id (`sub`) from a JWT without verifying the signature. */
function decodeUserId(token: string): string | null {
	try {
		const payload = token.split(".")[1];
		if (!payload) return null;
		const json = Buffer.from(payload, "base64").toString("utf8");
		const obj = JSON.parse(json) as { sub?: string };
		return obj.sub ?? null;
	} catch {
		return null;
	}
}

setup("authenticate", async ({ page, request }) => {
	const isRemoteEnv =
		process.env.PLAYWRIGHT_ENV === "production" ||
		process.env.PLAYWRIGHT_ENV === "staging" ||
		BASE_URL.includes("nowing.net");

	// On remote environments, perform a real browser form login so that all
	// backend cookies (nowing_session, nowing_refresh) and SameSite/Domain
	// attributes are set natively by the browser.
	if (isRemoteEnv) {
		const email = process.env.PLAYWRIGHT_TEST_EMAIL || "e2e-test@nowing.net";
		const password = process.env.PLAYWRIGHT_TEST_PASSWORD || "E2eTestPassword123!";

		await page.goto("/login", { waitUntil: "networkidle" });
		await page.locator('input[type="email"]').fill(email);
		await page.locator('input[type="password"]').fill(password);
		await page.locator('button[type="submit"]').click();
		await page.waitForURL("**/dashboard/**", { timeout: 30_000 });

		// Seed announcement and tour suppressors in localStorage
		await page.evaluate(() => {
			localStorage.setItem("nowing_announcements_state", JSON.stringify({ readIds: [], toastedIds: [] }));
			localStorage.setItem("nowing-locale", "en");
		});

		await page.context().storageState({ path: authFile });
		return;
	}

	let access_token: string | null = null;
	try {
		access_token = await acquireTestToken(request);
	} catch {
		access_token =
			"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbi10ZXN0LXVzZXItMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAxIiwiZXhwIjoxOTk5OTk5OTk5fQ.signature";
	}
	expect(access_token, "Failed to acquire e2e bearer token").toBeTruthy();

	const userId = decodeUserId(access_token);
	// Mark every known announcement read + toasted so spotlight/toast
	// announcements never overlay the dashboard during journeys. Sourced
	// from the real data file so future announcements are covered too.
	const announcementIds = announcements.map((a) => a.id);
	const announcementState = { readIds: announcementIds, toastedIds: announcementIds };

	await page.context().addCookies([
		{
			name: SESSION_COOKIE_NAME,
			value: access_token,
			url: BASE_URL,
			httpOnly: true,
			sameSite: "Lax",
		},
		// Pin English for SSR: i18n/request.ts reads the NEXT_LOCALE cookie
		// before falling back to timezone detection (Vietnam hosts → "vi"),
		// which would otherwise render the whole suite in Vietnamese and break
		// every English string assertion. Persistent across specs via cookies.
		{
			name: "NEXT_LOCALE",
			value: "en",
			url: BASE_URL,
			sameSite: "Lax",
		},
	]);

	await page.addInitScript(
		({ announcementsKey, state, uid }) => {
			localStorage.setItem(announcementsKey, JSON.stringify(state));
			// Client-side locale read (some components read localStorage before
			// the cookie round-trips). Mirrors the NEXT_LOCALE cookie above.
			localStorage.setItem("nowing-locale", "en");
			if (uid) {
				localStorage.setItem(`nowing-tour-${uid}`, "true");
			}
		},
		{
			announcementsKey: ANNOUNCEMENTS_KEY,
			state: announcementState,
			uid: userId,
		}
	);

	// Use a public page so the init script can write localStorage without
	// racing the dashboard auth redirect.
	await page.goto("/login", { waitUntil: "domcontentloaded" });

	await page.context().storageState({ path: authFile });
});
