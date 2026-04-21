import {
	authStorageInit,
	setAuthProvider,
	configureAuthSession,
	authGlobalInit,
} from "@seontechnologies/playwright-utils/auth-session";
import nowingAuthProvider from "./support/auth/auth-provider";

async function globalSetup() {
	authStorageInit();

	configureAuthSession({
		authStoragePath: process.cwd() + "/playwright/auth-sessions",
		debug: process.env.DEBUG_AUTH === "true",
	});

	setAuthProvider(nowingAuthProvider);

	// Pre-fetch default user token
	await authGlobalInit();
}

export default globalSetup;
