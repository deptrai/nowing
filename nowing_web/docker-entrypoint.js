/**
 * Runtime environment variable substitution for Next.js Docker images.
 *
 * Next.js inlines NEXT_PUBLIC_* values at build time. The Docker image is built
 * with unique placeholder strings (e.g. __NEXT_PUBLIC_FASTAPI_BACKEND_URL__).
 * This script replaces those placeholders with real values from the container's
 * environment variables before the server starts.
 *
 * Runs once at container startup via docker-entrypoint.sh.
 */

const fs = require("fs");
const path = require("path");

const replacements = [
	[
		"__NEXT_PUBLIC_FASTAPI_BACKEND_URL__",
		process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000",
	],
	[
		"__NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__",
		process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "LOCAL",
	],
	["__NEXT_PUBLIC_ETL_SERVICE__", process.env.NEXT_PUBLIC_ETL_SERVICE || "DOCLING"],
	[
		"__NEXT_PUBLIC_ZERO_CACHE_URL__",
		process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848",
	],
	["__NEXT_PUBLIC_DEPLOYMENT_MODE__", process.env.NEXT_PUBLIC_DEPLOYMENT_MODE || "self-hosted"],
];

let filesProcessed = 0;
let filesModified = 0;

function walk(dir) {
	let entries;
	try {
		entries = fs.readdirSync(dir, { withFileTypes: true });
	} catch {
		return;
	}
	for (const entry of entries) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			walk(full);
		} else if (entry.name.endsWith(".js")) {
			filesProcessed++;
			let content = fs.readFileSync(full, "utf8");
			let changed = false;
			for (const [placeholder, value] of replacements) {
				if (content.includes(placeholder)) {
					content = content.replaceAll(placeholder, value);
					changed = true;
				}
			}
			if (changed) {
				fs.writeFileSync(full, content);
				filesModified++;
			}
		}
	}
}

console.log("[entrypoint] Replacing environment variable placeholders...");
for (const [placeholder, value] of replacements) {
	console.log(`  ${placeholder} -> ${value}`);
}

walk(path.join(__dirname, ".next"));

const serverJs = path.join(__dirname, "server.js");
if (fs.existsSync(serverJs)) {
	let content = fs.readFileSync(serverJs, "utf8");
	let changed = false;
	filesProcessed++;
	for (const [placeholder, value] of replacements) {
		if (content.includes(placeholder)) {
			content = content.replaceAll(placeholder, value);
			changed = true;
		}
	}
	if (changed) {
		fs.writeFileSync(serverJs, content);
		filesModified++;
	}
}

console.log(`[entrypoint] Done. Scanned ${filesProcessed} files, modified ${filesModified}.`);

// Also rewrite .env so Next.js standalone server reads correct runtime values.
// The baked-in .env may have build-time placeholders or incorrect URLs.
const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
	const envKeys = [
		"NEXT_PUBLIC_FASTAPI_BACKEND_URL",
		"NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE",
		"NEXT_PUBLIC_ETL_SERVICE",
		"NEXT_PUBLIC_ZERO_CACHE_URL",
		"NEXT_PUBLIC_DEPLOYMENT_MODE",
		"NEXT_PUBLIC_POSTHOG_KEY",
	];
	let envContent = fs.readFileSync(envPath, "utf8");
	for (const key of envKeys) {
		const value = process.env[key];
		if (value !== undefined) {
			envContent = envContent.replace(new RegExp(`^${key}=.*`, "m"), `${key}=${value}`);
		}
	}
	fs.writeFileSync(envPath, envContent);
	console.log("[entrypoint] Rewrote .env with runtime environment values.");
}
