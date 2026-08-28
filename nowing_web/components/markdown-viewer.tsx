import { createCodePlugin } from "@streamdown/code";
import { createMathPlugin } from "@streamdown/math";
import { Streamdown, type StreamdownProps } from "streamdown";
import "katex/dist/katex.min.css";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { processChildrenWithCitations } from "@/components/citations/citation-renderer";
import { type CitationUrlMap, preprocessCitationMarkdown } from "@/lib/citations/citation-parser";
import { cn } from "@/lib/utils";

const code = createCodePlugin({
	themes: ["nord", "nord"],
});

const math = createMathPlugin({
	// Keep currency from being parsed as math; real math is normalized below.
	singleDollarTextMath: false,
});

interface MarkdownViewerProps {
	content: string;
	className?: string;
	maxLength?: number;
	/** Render citation tokens as interactive badges. */
	enableCitations?: boolean;
	/** Text to scroll into view and highlight after rendering. */
	highlightText?: string;
	/** Optional proportional position for fallback scrolling when the exact text is not found. */
	highlightPosition?: number;
	/** Total chunk count used with highlightPosition. */
	totalChunks?: number;
}

const EMPTY_URL_MAP: CitationUrlMap = new Map();

/** Strip a single outer markdown fence when the whole payload is fenced. */
function stripOuterMarkdownFence(content: string): string {
	const trimmed = content.trim();
	const match = trimmed.match(/^(`{3,})(?:markdown|md)?\s*\n([\s\S]+?)\n\1\s*$/);
	return match ? match[2] : content;
}

/** Normalize common LaTeX delimiters to Streamdown's double-dollar syntax. */
function convertLatexDelimiters(content: string): string {
	content = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `\n$$\n${inner.trim()}\n$$\n`);
	content = content.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$$${inner.trim()}$$`);
	content = content.replace(
		/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
		(_, inner) => `\n$$\n${inner.trim()}\n$$\n`
	);
	content = content.replace(
		/\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}/g,
		(_, inner) => `\n$$\n${inner.trim()}\n$$\n`
	);
	content = content.replace(
		/\\begin\{math\}([\s\S]*?)\\end\{math\}/g,
		(_, inner) => `$$${inner.trim()}$$`
	);
	content = content.replace(/`(\${1,2})((?:(?!\1).)+)\1`/g, "$1$2$1");
	// Only convert command-style single-dollar math, leaving currency alone.
	content = content.replace(
		/(?<!\$)\$(?!\$)(\\[a-zA-Z][\s\S]*?)(?<!\$)\$(?!\$)/g,
		(_, inner) => `$$${inner.trim()}$$`
	);
	return content;
}

export function MarkdownViewer({
	content,
	className,
	maxLength,
	enableCitations = false,
	highlightText,
	highlightPosition,
	totalChunks,
}: MarkdownViewerProps) {
	const containerRef = useRef<HTMLDivElement>(null);
	const highlightedElementRef = useRef<HTMLElement | null>(null);
	const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const isTruncated = maxLength != null && content.length > maxLength;
	const displayContent = isTruncated ? content.slice(0, maxLength) : content;

	const clearHighlight = useCallback(() => {
		if (highlightTimeoutRef.current) {
			clearTimeout(highlightTimeoutRef.current);
			highlightTimeoutRef.current = null;
		}
		if (highlightedElementRef.current) {
			highlightedElementRef.current.classList.remove("bg-yellow-200", "dark:bg-yellow-800");
			highlightedElementRef.current = null;
		}
		const selection = window.getSelection();
		if (selection) selection.removeAllRanges();
	}, []);

	useEffect(() => {
		const container = containerRef.current;
		clearHighlight();
		if (!container || !highlightText) return;

		const target = highlightText.trim();
		if (!target) return;

		const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
		let matchNode: Text | null = null;
		let matchOffset = -1;
		while (walker.nextNode()) {
			const node = walker.currentNode as Text;
			const text = node.textContent ?? "";
			const idx = text.indexOf(target);
			if (idx >= 0) {
				matchNode = node;
				matchOffset = idx;
				break;
			}
		}

		if (!matchNode) {
			// Proportional fallback: scroll to the text node nearest the expected position.
			if (highlightPosition === undefined || totalChunks === undefined || totalChunks <= 0) return;
			const fullText = container.textContent ?? "";
			if (!fullText) return;
			const safePosition = Math.max(0, highlightPosition);
			const safeTotal = Math.max(1, totalChunks - 1);
			const targetRatio = Math.max(0, Math.min(1, safePosition / safeTotal));
			const targetOffset = Math.floor(targetRatio * (fullText.length - 1));
			let accumulated = 0;
			walker.currentNode = container; // reset walker
			while (walker.nextNode()) {
				const node = walker.currentNode as Text;
				const text = node.textContent ?? "";
				if (accumulated + text.length > targetOffset) {
					matchNode = node;
					matchOffset = Math.max(0, targetOffset - accumulated);
					break;
				}
				accumulated += text.length;
			}
		}

		if (!matchNode) return;

		const range = document.createRange();
		range.setStart(matchNode, matchOffset);
		range.setEnd(
			matchNode,
			Math.min(matchOffset + target.length, matchNode.textContent?.length ?? 0)
		);

		const selection = window.getSelection();
		if (selection) {
			selection.removeAllRanges();
			selection.addRange(range);
		}

		const element = matchNode.parentElement;
		if (element) {
			element.scrollIntoView({ behavior: "auto", block: "center" });
			element.classList.add("bg-yellow-200", "dark:bg-yellow-800");
			highlightedElementRef.current = element;
		}

		highlightTimeoutRef.current = setTimeout(() => {
			clearHighlight();
		}, 3000);
	}, [highlightText, highlightPosition, totalChunks, clearHighlight]);

	// Rewrite citation URLs before markdown autolinking can split them.
	const { processedContent, urlMap } = useMemo(() => {
		const stripped = stripOuterMarkdownFence(displayContent);
		if (!enableCitations) {
			return {
				processedContent: convertLatexDelimiters(stripped),
				urlMap: EMPTY_URL_MAP,
			};
		}
		const { content: rewritten, urlMap: map } = preprocessCitationMarkdown(stripped);
		return {
			processedContent: convertLatexDelimiters(rewritten),
			urlMap: map,
		};
	}, [displayContent, enableCitations]);

	// Do not wrap anchors or code; citation buttons inside them would be invalid.
	const wrap = (children: React.ReactNode): React.ReactNode =>
		enableCitations ? processChildrenWithCitations(children, urlMap) : children;

	const components: StreamdownProps["components"] = {
		p: ({ children, ...props }) => (
			<p className="my-2" {...props}>
				{wrap(children)}
			</p>
		),
		a: ({ children, ...props }) => (
			<a
				className="text-primary hover:underline"
				target="_blank"
				rel="noopener noreferrer"
				{...props}
			>
				{children}
			</a>
		),
		li: ({ children, ...props }) => <li {...props}>{wrap(children)}</li>,
		ul: ({ ...props }) => <ul className="list-disc pl-5 my-2" {...props} />,
		ol: ({ ...props }) => <ol className="list-decimal pl-5 my-2" {...props} />,
		h1: ({ children, ...props }) => (
			<h1 className="text-2xl font-bold mt-6 mb-2" {...props}>
				{wrap(children)}
			</h1>
		),
		h2: ({ children, ...props }) => (
			<h2 className="text-xl font-bold mt-5 mb-2" {...props}>
				{wrap(children)}
			</h2>
		),
		h3: ({ children, ...props }) => (
			<h3 className="text-lg font-bold mt-4 mb-2" {...props}>
				{wrap(children)}
			</h3>
		),
		h4: ({ children, ...props }) => (
			<h4 className="text-base font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h4>
		),
		h5: ({ children, ...props }) => (
			<h5 className="text-sm font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h5>
		),
		h6: ({ children, ...props }) => (
			<h6 className="text-xs font-bold mt-3 mb-1" {...props}>
				{wrap(children)}
			</h6>
		),
		strong: ({ children, ...props }) => (
			<strong className="font-semibold" {...props}>
				{wrap(children)}
			</strong>
		),
		em: ({ children, ...props }) => <em {...props}>{wrap(children)}</em>,
		blockquote: ({ children, ...props }) => (
			<blockquote className="border-l-4 border-muted pl-4 italic my-2" {...props}>
				{wrap(children)}
			</blockquote>
		),
		hr: ({ ...props }) => <hr className="my-4 border-muted" {...props} />,
		img: ({ src, alt, width: _w, height: _h, ...props }) => {
			if (typeof src !== "string") return null;

			const width = typeof _w === "number" ? _w : Number(_w) || 800;
			const height = typeof _h === "number" ? _h : Number(_h) || 600;
			const shouldSkipOptimization = src.startsWith("data:");

			return (
				<Image
					className="max-w-full h-auto my-4 rounded"
					alt={alt || "markdown image"}
					src={src}
					width={width}
					height={height}
					sizes="(max-width: 768px) 100vw, (max-width: 1200px) 75vw, 60vw"
					unoptimized={shouldSkipOptimization}
					{...props}
				/>
			);
		},
		table: ({ ...props }) => (
			<div className="overflow-x-auto my-4 rounded-lg border border-border w-full">
				<table className="w-full divide-y divide-border" {...props} />
			</div>
		),
		th: ({ children, ...props }) => (
			<th
				className="px-4 py-2.5 text-left text-sm font-semibold text-muted-foreground/80 bg-muted/30 border-r border-border/40 last:border-r-0"
				{...props}
			>
				{wrap(children)}
			</th>
		),
		td: ({ children, ...props }) => (
			<td
				className="px-4 py-2.5 text-sm border-t border-r border-border/40 last:border-r-0"
				{...props}
			>
				{wrap(children)}
			</td>
		),
	};

	return (
		<div
			ref={containerRef}
			className={cn(
				"max-w-none overflow-hidden",
				"[&_[data-streamdown=code-block-header]]:!bg-transparent",
				"[&_[data-streamdown=code-block]>*]:!border-none [&_[data-streamdown=code-block]>*]:![box-shadow:none]",
				"[&_[data-streamdown=code-block-download-button]]:!hidden",
				className
			)}
		>
			<Streamdown
				components={components}
				plugins={{ code, math }}
				controls={{ code: true }}
				mode="static"
			>
				{processedContent}
			</Streamdown>
			{isTruncated && (
				<p className="mt-4 text-sm text-muted-foreground italic">
					Content truncated ({Math.round(content.length / 1024)}KB total). Showing first{" "}
					{Math.round(maxLength / 1024)}KB.
				</p>
			)}
		</div>
	);
}
