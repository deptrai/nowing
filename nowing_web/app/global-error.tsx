"use client";

import "./globals.css";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

const ISSUES_URL = "https://github.com/deptrai/nowing/issues/new";

// This root error boundary renders outside all providers (it replaces the root
// layout), so next-intl context is unavailable. Read the stored locale directly.
const STRINGS = {
	en: {
		title: "Something went wrong",
		desc: "An unexpected error occurred. Please try again, or report this issue if it persists.",
		try_again: "Try again",
		report_issue: "Report Issue",
	},
	vi: {
		title: "Đã xảy ra lỗi",
		desc: "Đã xảy ra lỗi không mong muốn. Vui lòng thử lại, hoặc báo cáo sự cố nếu vẫn tiếp diễn.",
		try_again: "Thử lại",
		report_issue: "Báo cáo sự cố",
	},
} as const;

function useUiLocale() {
	const [vi, setVi] = useState(false);
	useEffect(() => {
		try {
			const l =
				localStorage.getItem("nowing-locale") ||
				(document.cookie.match(/NEXT_LOCALE=(\w+)/)?.[1] ?? "en");
			setVi(l.startsWith("vi"));
		} catch {
			setVi(false);
		}
	}, []);
	return vi ? STRINGS.vi : STRINGS.en;
}

function buildBasicIssueUrl(error: Error & { digest?: string }) {
	const params = new URLSearchParams();
	const lines = [
		"## Bug Report",
		"",
		"**Describe what happened:**",
		"",
		"",
		"## Diagnostics (auto-filled)",
		"",
		`- **Error:** ${error.message}`,
		...(error.digest ? [`- **Digest:** \`${error.digest}\``] : []),
		`- **Timestamp:** ${new Date().toISOString()}`,
		`- **Page:** \`${typeof window !== "undefined" ? window.location.pathname : "unknown"}\``,
		`- **User Agent:** \`${typeof navigator !== "undefined" ? navigator.userAgent : "unknown"}\``,
	];
	params.set("body", lines.join("\n"));
	params.set("labels", "bug");
	return `${ISSUES_URL}?${params.toString()}`;
}

export default function GlobalError({
	error,
	reset,
}: {
	error: Error & { digest?: string };
	reset: () => void;
}) {
	useEffect(() => {
		import("posthog-js")
			.then(({ default: posthog }) => {
				posthog.captureException(error);
			})
			.catch(() => {});
	}, [error]);

	const issueUrl = useMemo(() => buildBasicIssueUrl(error), [error]);
	const s = useUiLocale();

	return (
		<html lang={s === STRINGS.vi ? "vi" : "en"}>
			<body>
				<div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
					<h2 className="text-xl font-semibold">{s.title}</h2>
					<p className="text-sm text-muted-foreground max-w-md">{s.desc}</p>

					{error.digest && (
						<p className="text-xs text-muted-foreground font-mono">Digest: {error.digest}</p>
					)}

					<div className="flex gap-2">
						<Button onClick={reset}>{s.try_again}</Button>
						<a
							href={issueUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
						>
							{s.report_issue}
						</a>
					</div>
				</div>
			</body>
		</html>
	);
}
