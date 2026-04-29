"use client";

import { SearchIcon, XIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { ComparisonTable } from "./comparison-table";

const BACKEND_URL =
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ||
	(process.env.NODE_ENV === "production"
		? (() => {
				throw new Error("NEXT_PUBLIC_FASTAPI_BACKEND_URL is required in production");
			})()
		: "http://localhost:8000");
const COINGECKO_SEARCH_URL = "https://api.coingecko.com/api/v3/search";

function isValidThumbUrl(url: string | undefined): boolean {
	if (!url) return false;
	return /^https?:\/\//.test(url);
}

interface CoinSearchResult {
	id: string;
	name: string;
	symbol: string;
	thumb?: string;
	market_cap_rank?: number;
}

interface CompareData {
	primary: Record<string, unknown>;
	secondary: Record<string, unknown>;
}

interface CoinComparisonOverlayProps {
	open: boolean;
	onClose: () => void;
	primaryToken: string;
	primaryName: string;
	primaryCoingeckoId?: string;
	token: string | null;
}

function useDebounce<T>(value: T, delay: number): T {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const timer = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(timer);
	}, [value, delay]);
	return debounced;
}

function TokenPicker({
	onSelect,
	placeholder,
}: {
	onSelect: (coin: CoinSearchResult) => void;
	placeholder: string;
}) {
	const [query, setQuery] = useState("");
	const [results, setResults] = useState<CoinSearchResult[]>([]);
	const [loading, setLoading] = useState(false);
	const debouncedQuery = useDebounce(query, 350);

	useEffect(() => {
		if (!debouncedQuery.trim()) {
			setResults([]);
			return;
		}
		const ctrl = new AbortController();
		setLoading(true);
		fetch(`${COINGECKO_SEARCH_URL}?query=${encodeURIComponent(debouncedQuery)}`, {
			signal: ctrl.signal,
		})
			.then((r) => r.json())
			.then((data) => {
				if (ctrl.signal.aborted) return;
				const coins: CoinSearchResult[] = (data?.coins ?? []).slice(0, 10);
				setResults(coins);
			})
			.catch((err) => {
				if (ctrl.signal.aborted) return;
				if ((err as Error).name !== "AbortError") {
					console.warn("[CoinSearch]", err);
					setResults([]);
				}
			})
			.finally(() => {
				if (!ctrl.signal.aborted) setLoading(false);
			});
		return () => ctrl.abort();
	}, [debouncedQuery]);

	return (
		<div className="relative">
			<div className="relative">
				<SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
				<Input
					className="pl-9"
					placeholder={placeholder}
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					autoFocus
				/>
				{loading && (
					<span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
						…
					</span>
				)}
			</div>
			{results.length > 0 && (
				<ul className="absolute z-50 mt-1 w-full rounded-lg border bg-popover shadow-lg overflow-hidden">
					{results.map((coin) => (
						<li key={coin.id}>
							<button
								onClick={() => {
									onSelect(coin);
									setQuery("");
									setResults([]);
								}}
								className="flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
							>
								{isValidThumbUrl(coin.thumb) && (
									<img
										src={coin.thumb}
										alt={coin.symbol}
										className="size-5 rounded-full"
										onError={(e) => {
											(e.currentTarget as HTMLImageElement).style.display = "none";
										}}
									/>
								)}
								<span className="font-medium">{coin.symbol.toUpperCase()}</span>
								<span className="text-muted-foreground truncate">{coin.name}</span>
								{coin.market_cap_rank && (
									<span className="ml-auto text-xs text-muted-foreground">
										#{coin.market_cap_rank}
									</span>
								)}
							</button>
						</li>
					))}
				</ul>
			)}
		</div>
	);
}

export function CoinComparisonOverlay({
	open,
	onClose,
	primaryToken,
	primaryName,
	primaryCoingeckoId,
	token,
}: CoinComparisonOverlayProps) {
	const [selectedCoin, setSelectedCoin] = useState<CoinSearchResult | null>(null);
	const [compareData, setCompareData] = useState<CompareData | null>(null);
	const [verdict, setVerdict] = useState("");
	const [loading, setLoading] = useState(false);
	const abortRef = useRef<AbortController | null>(null);

	const runComparison = useCallback(
		async (coin: CoinSearchResult) => {
			if (!token) return;
			abortRef.current?.abort();
			const ctrl = new AbortController();
			abortRef.current = ctrl;

			setLoading(true);
			setCompareData(null);
			setVerdict("");

			try {
				const resp = await fetch(`${BACKEND_URL}/api/v1/compare/tokens`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						primary_token: primaryToken || coin.symbol,
						primary_coingecko_id: primaryCoingeckoId,
						secondary_token: coin.symbol,
						secondary_coingecko_id: coin.id,
					}),
					signal: ctrl.signal,
				});

				if (!resp.ok || !resp.body) {
					toast.error(`Comparison failed (HTTP ${resp.status})`);
					throw new Error(`HTTP ${resp.status}`);
				}

				const reader = resp.body.getReader();
				const decoder = new TextDecoder();
				let buf = "";
				let streamDone = false;

				while (!streamDone) {
					const { done, value } = await reader.read();
					if (done) break;
					buf += decoder.decode(value, { stream: true });
					const lines = buf.split("\n");
					buf = lines.pop() ?? "";
					for (const line of lines) {
						if (!line.startsWith("data: ")) continue;
						const raw = line.slice(6);
						if (raw === "[DONE]") {
							streamDone = true;
							break;
						}
						try {
							const ev = JSON.parse(raw) as { type: string; data?: unknown };
							if (ev.type === "data-compare-data") {
								setCompareData(ev.data as CompareData);
							} else if (ev.type === "data-compare-verdict-delta") {
								const d = ev.data as { delta?: unknown };
								if (typeof d?.delta === "string") {
									setVerdict((prev) => prev + d.delta);
								}
							}
						} catch (parseErr) {
							console.warn("[CoinComparisonOverlay] SSE parse", parseErr);
						}
					}
				}
			} catch (err) {
				if ((err as Error).name !== "AbortError") {
					console.error("[CoinComparisonOverlay]", err);
					toast.error("Comparison failed. Please try again.");
				}
			} finally {
				setLoading(false);
			}
		},
		[primaryToken, token]
	);

	const handleSelect = useCallback(
		(coin: CoinSearchResult) => {
			setSelectedCoin(coin);
			void runComparison(coin);
		},
		[runComparison]
	);

	// Reset on close
	useEffect(() => {
		if (!open) {
			abortRef.current?.abort();
			setSelectedCoin(null);
			setCompareData(null);
			setVerdict("");
			setLoading(false);
		}
	}, [open]);

	return (
		<Sheet open={open} onOpenChange={(o) => !o && onClose()}>
			<SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
				<SheetHeader className="mb-4">
					<SheetTitle>
						Compare {primaryToken || primaryName}
						{selectedCoin ? ` vs ${selectedCoin.symbol.toUpperCase()}` : " vs…"}
					</SheetTitle>
				</SheetHeader>

				<TokenPicker
					onSelect={handleSelect}
					placeholder={`Search token to compare with ${primaryToken || "…"}`}
				/>

				{loading && !compareData && (
					<div className="mt-8 flex flex-col items-center gap-3 text-muted-foreground">
						<div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
						<span className="text-sm">Fetching comparison data…</span>
					</div>
				)}

				{compareData && selectedCoin && (
					<ComparisonTable
						primarySymbol={primaryToken}
						secondarySymbol={selectedCoin.symbol.toUpperCase()}
						primaryData={compareData.primary}
						secondaryData={compareData.secondary}
						verdict={verdict}
						verdictLoading={loading}
						className="mt-6"
					/>
				)}
			</SheetContent>
		</Sheet>
	);
}
