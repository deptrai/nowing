"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// ─── Section icons per heading content ───────────────────────────────────────

const SECTION_ICONS: { pattern: RegExp; icon: string }[] = [
	{ pattern: /overview|tổng quan|giới thiệu/i, icon: "🦄" },
	{ pattern: /tokenomics|token|supply|vesting/i, icon: "📦" },
	{ pattern: /defi|protocol|tvl|liquidity/i, icon: "🏗️" },
	{ pattern: /security|audit|risk|bảo mật/i, icon: "🛡️" },
	{ pattern: /market|price|chart|giá/i, icon: "📈" },
	{ pattern: /team|governance|dao/i, icon: "👥" },
	{ pattern: /roadmap|ecosystem/i, icon: "🗺️" },
	{ pattern: /conclusion|summary|kết luận/i, icon: "✅" },
];

function sectionIcon(text: string): string {
	for (const { pattern, icon } of SECTION_ICONS) {
		if (pattern.test(text)) return icon;
	}
	return "📄";
}

// ─── Parse headings from markdown ─────────────────────────────────────────────

interface TocItem {
	id: string;
	level: 1 | 2;
	text: string;
	icon: string;
}

function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^\w\s-]/g, "")
		.trim()
		.replace(/\s+/g, "-");
}

function parseHeadings(markdown: string): TocItem[] {
	const lines = markdown.split("\n");
	const items: TocItem[] = [];
	const seen = new Map<string, number>();

	for (const line of lines) {
		const h1 = line.match(/^#\s+(.+)/);
		const h2 = line.match(/^##\s+(.+)/);
		const match = h1 ?? h2;
		const level = h1 ? 1 : 2;
		if (!match) continue;

		const text = match[1].replace(/<!--.*?-->/g, "").trim();
		const base = slugify(text);
		const count = seen.get(base) ?? 0;
		const id = count === 0 ? base : `${base}-${count}`;
		seen.set(base, count + 1);
		items.push({ id, level: level as 1 | 2, text, icon: sectionIcon(text) });
	}
	return items;
}

// ─── ReportTOC ────────────────────────────────────────────────────────────────

interface ReportTOCProps {
	content: string;
	className?: string;
}

const ReportTOCImpl = ({ content, className }: ReportTOCProps) => {
	const items = useMemo(() => parseHeadings(content), [content]);
	const [activeId, setActiveId] = useState<string>("");
	const observerRef = useRef<IntersectionObserver | null>(null);

	useEffect(() => {
		if (items.length === 0) return;

		observerRef.current?.disconnect();

		const headingEls = items
			.map((item) => document.getElementById(item.id))
			.filter(Boolean) as HTMLElement[];

		if (headingEls.length === 0) return;

		observerRef.current = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) {
						setActiveId(entry.target.id);
						break;
					}
				}
			},
			{ rootMargin: "-80px 0px -60% 0px", threshold: 0 }
		);

		for (const el of headingEls) {
			observerRef.current.observe(el);
		}

		return () => observerRef.current?.disconnect();
	}, [items]);

	if (items.length < 2) return null;

	return (
		<nav
			className={cn(
				"w-48 shrink-0",
				"sticky top-20 self-start",
				"max-h-[calc(100vh-6rem)] overflow-y-auto",
				"scrollbar-hide",
				className
			)}
			aria-label="Table of contents"
			data-slot="report-toc"
		>
			<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
				Contents
			</p>
			<ul className="space-y-0.5">
				{items.map((item) => (
					<li key={item.id}>
						<a
							href={`#${item.id}`}
							onClick={(e) => {
								e.preventDefault();
								document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth" });
								setActiveId(item.id);
							}}
							className={cn(
								"flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors",
								item.level === 2 && "ml-3",
								activeId === item.id
									? "bg-primary/10 font-medium text-primary"
									: "text-muted-foreground hover:bg-muted hover:text-foreground"
							)}
						>
							<span aria-hidden="true">{item.icon}</span>
							<span className="truncate">{item.text}</span>
						</a>
					</li>
				))}
			</ul>
		</nav>
	);
};

export const ReportTOC = memo(ReportTOCImpl);
