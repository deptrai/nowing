import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
	plugins: [react()],
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: "./vitest.setup.ts",
		css: true,
		pool: "threads",
		poolOptions: {
			threads: {
				maxThreads: process.env.CI ? 4 : undefined,
			},
		},
		coverage: {
			provider: "v8",
			reporter: ["text", "json", "html"],
			exclude: ["node_modules/", "vitest.setup.ts", "**/*.config.ts", "**/*.d.ts", "**/types/**"],
		},
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./"),
		},
	},
});
