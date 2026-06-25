"use client";

/**
 * StaticMarkdown — renders a markdown string outside of the assistant-ui
 * message context (unlike <MarkdownText /> which reads from useAuiState).
 *
 * Used by CryptoReportLayout to render scenario re-synthesis content.
 *
 * Security: pipeline includes `rehype-sanitize` to strip script/iframe/style
 * and dangerous attributes. Even though our content originates from trusted
 * LLM synthesis, defence-in-depth protects against:
 *   1. Cached scenario rows tampered if anyone gains DB write access
 *   2. Markdown autolinks/images that allow attribute injection
 */

import { memo, useMemo } from "react";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeSanitize from "rehype-sanitize";
import rehypeStringify from "rehype-stringify";

interface StaticMarkdownProps {
	content: string;
	className?: string;
}

const processor = unified()
	.use(remarkParse)
	.use(remarkGfm)
	.use(remarkRehype)
	.use(rehypeSanitize)
	.use(rehypeStringify);

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function StaticMarkdownImpl({ content, className }: StaticMarkdownProps) {
	const html = useMemo(() => {
		// Guard non-string content (e.g. null/undefined from upstream typing slip)
		if (typeof content !== "string") {
			return `<pre>${escapeHtml(String(content ?? ""))}</pre>`;
		}
		try {
			return String(processor.processSync(content));
		} catch {
			// Fallback: HTML-escape so unparseable input cannot inject markup
			return `<pre>${escapeHtml(content)}</pre>`;
		}
	}, [content]);

	return (
		<div
			className={`aui-md prose prose-sm dark:prose-invert max-w-none ${className ?? ""}`}
			// Sanitized via rehype-sanitize above — no script/iframe/style/event handlers survive
			dangerouslySetInnerHTML={{ __html: html }}
		/>
	);
}

export const StaticMarkdown = memo(StaticMarkdownImpl);
