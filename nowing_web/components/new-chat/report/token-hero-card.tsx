"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, TrendingDown, TrendingUp } from "lucide-react";
import { memo, useMemo } from "react";
import { getBearerToken } from "@/lib/auth-utils";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

/** Minimal subset of get_tokeninsight_rating tool result surfaced via message metadata */
export interface TokenInsightRating {
	/** Letter grade: A+, A, B+, B, C, D */
	overall_rating: string;
	/** Numeric score 0–100 */
	overall_score: number;
}

interface TokenHeroCardProps {
	symbol?: string;
	name?: string;
	coingeckoId?: string;
	reportText?: string;
	/** When present, shows a TokenInsight rating badge (Story 9-UX-4 AC5) */
	tokenInsightRating?: TokenInsightRating;
	className?: string;
}

interface CoinGeckoPrice {
	usd: number;
	usd_24h_change: number;
}

type RiskLevel = "LOW" | "MED" | "HIGH";

// ─── CoinGecko live price (proxied through BE to avoid client-side rate limit) ─

const _backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

function useLivePrice(coingeckoId: string | undefined) {
	return useQuery<CoinGeckoPrice | null>({
		queryKey: ["coingecko-price", coingeckoId],
		queryFn: async () => {
			if (!coingeckoId) return null;
			const token = getBearerToken();
			const res = await fetch(
				`${_backendUrl}/compare/coingecko-price/${encodeURIComponent(coingeckoId)}`,
				token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
			);
			if (!res.ok) return null;
			const data = await res.json();
			return data[coingeckoId] ?? null;
		},
		enabled: !!coingeckoId,
		staleTime: 30_000,
		refetchInterval: 30_000,
		retry: 1,
	});
}

// ─── TokenInsight rating badge (Story 9-UX-4 AC5) ────────────────────────────

const RATING_GRADE_MAP: Record<string, { label: string; emoji: string }> = {
	"A+": { label: "A+", emoji: "🏆" },
	A: { label: "A", emoji: "🅰️" },
	"B+": { label: "B+", emoji: "🔵" },
	B: { label: "B", emoji: "🔵" },
	C: { label: "C", emoji: "🟡" },
	D: { label: "D", emoji: "🔴" },
};

function TokenInsightRatingBadge({ rating }: { rating: TokenInsightRating }) {
	const grade = RATING_GRADE_MAP[rating.overall_rating] ?? {
		label: rating.overall_rating,
		emoji: "📊",
	};
	const isStrong = rating.overall_rating === "A+" || rating.overall_rating === "A";

	return (
		<a
			href={`https://tokeninsight.com`}
			target="_blank"
			rel="noopener noreferrer"
			className={cn(
				"inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold no-underline transition-opacity hover:opacity-80",
				isStrong
					? "bg-[var(--source-tokeninsight)]/15 text-[var(--source-tokeninsight)]"
					: "bg-muted/60 text-muted-foreground"
			)}
			title={`TokenInsight Rating: ${rating.overall_rating} (${rating.overall_score}/100)`}
			data-slot="tokeninsight-rating-badge"
		>
			<span aria-hidden="true">{grade.emoji}</span>
			{grade.label} Rating
		</a>
	);
}

// ─── Risk badge ───────────────────────────────────────────────────────────────

const RISK_PATTERNS: { level: RiskLevel; pattern: RegExp }[] = [
	{ level: "LOW", pattern: /risk[:\s]+low|low\s+risk/i },
	{ level: "HIGH", pattern: /risk[:\s]+high|high\s+risk/i },
	{ level: "MED", pattern: /risk[:\s]+med|medium\s+risk/i },
];

function deriveRisk(text: string): RiskLevel | null {
	for (const { level, pattern } of RISK_PATTERNS) {
		if (pattern.test(text)) return level;
	}
	return null;
}

function RiskBadge({ level }: { level: RiskLevel }) {
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
				level === "LOW" && "bg-[var(--risk-low)]/15 text-[var(--risk-low)]",
				level === "MED" && "bg-[var(--risk-medium)]/15 text-[var(--risk-medium)]",
				level === "HIGH" && "bg-[var(--risk-high)]/15 text-[var(--risk-high)]"
			)}
		>
			{level === "LOW" && "🟢"}
			{level === "MED" && "🟡"}
			{level === "HIGH" && "🔴"}
			{level} RISK
		</span>
	);
}

// ─── Token logo ───────────────────────────────────────────────────────────────

function TokenLogo({ symbol, size = 48 }: { symbol: string; size?: number }) {
	const slug = symbol.toLowerCase();
	const src = `https://assets.trustwallet.com/blockchains/ethereum/assets/${slug}/logo.png`;
	const fallbackColor = useMemo(() => {
		const colors = ["#6366f1", "#8b5cf6", "#ec4899", "#14b8a6", "#f59e0b", "#10b981"];
		const idx = symbol.charCodeAt(0) % colors.length;
		return colors[idx];
	}, [symbol]);

	return (
		<div className="shrink-0 overflow-hidden rounded-full" style={{ width: size, height: size }}>
			<img
				src={src}
				alt={`${symbol} logo`}
				width={size}
				height={size}
				onError={(e) => {
					const el = e.currentTarget;
					el.style.display = "none";
					const parent = el.parentElement;
					if (parent) {
						parent.style.backgroundColor = fallbackColor;
						parent.style.display = "flex";
						parent.style.alignItems = "center";
						parent.style.justifyContent = "center";
						parent.style.color = "white";
						parent.style.fontWeight = "700";
						parent.style.fontSize = `${size * 0.4}px`;
						parent.textContent = symbol.charAt(0).toUpperCase();
					}
				}}
				className="h-full w-full object-cover"
			/>
		</div>
	);
}

// ─── Price display ────────────────────────────────────────────────────────────

function PriceDisplay({ price, change24h }: { price: number; change24h: number }) {
	const isPositive = change24h >= 0;
	const formatted =
		price < 0.01
			? price.toFixed(6)
			: price < 1
				? price.toFixed(4)
				: price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

	return (
		<div className="flex items-baseline gap-2">
			<span className="text-2xl font-bold tabular-nums tracking-tight">${formatted}</span>
			<span
				className={cn(
					"flex items-center gap-0.5 text-sm font-medium tabular-nums",
					isPositive ? "text-[var(--crypto-gain)]" : "text-[var(--crypto-loss)]"
				)}
			>
				{isPositive ? (
					<TrendingUp className="size-3.5" aria-hidden="true" />
				) : (
					<TrendingDown className="size-3.5" aria-hidden="true" />
				)}
				{isPositive ? "+" : ""}
				{change24h.toFixed(2)}%
			</span>
		</div>
	);
}

// ─── Main component ───────────────────────────────────────────────────────────

const TokenHeroCardImpl = ({
	symbol,
	name,
	coingeckoId,
	reportText = "",
	tokenInsightRating,
	className,
}: TokenHeroCardProps) => {
	const { data: priceData, isLoading } = useLivePrice(coingeckoId);
	const risk = useMemo(() => deriveRisk(reportText), [reportText]);

	if (!symbol) return null;

	return (
		<div
			className={cn(
				"mb-6 flex flex-col gap-3 rounded-xl border border-border/60 bg-card p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between",
				className
			)}
			data-slot="token-hero-card"
		>
			{/* Left: logo + identity */}
			<div className="flex items-center gap-3">
				<TokenLogo symbol={symbol} size={48} />
				<div>
					<div className="flex items-center gap-2">
						<span className="text-lg font-bold tracking-tight">{symbol}</span>
						{name && <span className="text-sm text-muted-foreground">{name}</span>}
					</div>
					{priceData && <PriceDisplay price={priceData.usd} change24h={priceData.usd_24h_change} />}
					{isLoading && !priceData && (
						<div className="mt-1 h-7 w-32 animate-pulse rounded bg-muted" />
					)}
				</div>
			</div>

			{/* Right: risk badge + TokenInsight rating */}
			<div className="flex flex-wrap items-center gap-2">
				{tokenInsightRating && <TokenInsightRatingBadge rating={tokenInsightRating} />}
				{risk && <RiskBadge level={risk} />}
				{!risk && (
					<span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
						<AlertTriangle className="size-3" aria-hidden="true" />
						Risk unrated
					</span>
				)}
			</div>
		</div>
	);
};

export const TokenHeroCard = memo(TokenHeroCardImpl);
