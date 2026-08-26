"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
	RuleSchema,
	ScraperRuleListItem,
	ScraperRuleRead,
} from "@/contracts/types/scraper-rules.types";
import { scraperRulesApi } from "@/lib/apis/scraper-rules-api.service";

function getApiErrorDetail(error: unknown, fallback: string): string {
	if (!error || typeof error !== "object") return fallback;
	const e = error as { response?: { data?: { detail?: unknown } } };
	const detail = e.response?.data?.detail;
	if (typeof detail === "string") return detail;
	if (Array.isArray(detail) && detail.length > 0) {
		const first = detail[0] as { msg?: string } | undefined;
		if (first && typeof first === "object" && "msg" in first) {
			return first.msg || fallback;
		}
	}
	if (detail && typeof detail === "object" && "detail" in detail) {
		return (detail as { detail?: string }).detail || fallback;
	}
	return fallback;
}

const DEFAULT_RULE: RuleSchema = {
	selectors: {
		listing_card: "",
		title: "",
		price: "",
		next_page_link: "",
	},
	regexes: {
		phone_in_title: "",
	},
	delays: {
		request_ms: 1500,
		retry_base_ms: 1000,
	},
	retries: {
		max_attempts: 3,
		statuses: [429, 500, 502, 503],
	},
	circuit_breaker: {
		error_threshold_pct: 20,
		min_calls: 10,
		trip_duration_seconds: 300,
		tripped: false,
	},
};

export default function ScraperRulesPage() {
	const [rules, setRules] = useState<ScraperRuleListItem[]>([]);
	const [active, setActive] = useState<ScraperRuleRead | null>(null);
	const [platform, setPlatform] = useState("batdongsan");
	const [loading, setLoading] = useState(false);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const list = await scraperRulesApi.list();
			setRules(list.items);
			if (list.items.length > 0) {
				const p = list.items[0].platform;
				setPlatform(p);
				const rule = await scraperRulesApi.get(p);
				setActive(rule);
			}
		} catch (_e) {
			toast.error("Failed to load scraper rules");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void fetchAll();
		const id = setInterval(() => void fetchAll(), 5000);
		return () => clearInterval(id);
	}, [fetchAll]);

	const handleSave = async () => {
		if (!active) return;
		try {
			const saved = await scraperRulesApi.save(platform, active.rule_schema);
			setActive(saved);
			toast.success("Rule saved");
		} catch (e) {
			toast.error(getApiErrorDetail(e, "Failed to save rule"));
		}
	};

	const updateField = (section: keyof RuleSchema, key: string, value: unknown) => {
		setActive((prev) =>
			prev
				? {
						...prev,
						rule_schema: {
							...prev.rule_schema,
							[section]: {
								...(prev.rule_schema[section] as Record<string, unknown>),
								[key]: value,
							},
						},
					}
				: prev
		);
	};

	const handleTrip = async () => {
		try {
			const rule = await scraperRulesApi.trip(platform);
			setActive(rule);
			toast.success("Circuit breaker tripped");
		} catch (e) {
			toast.error(getApiErrorDetail(e, "Trip failed"));
		}
	};

	const handleReset = async () => {
		try {
			const rule = await scraperRulesApi.reset(platform);
			setActive(rule);
			toast.success("Circuit breaker reset");
		} catch (e) {
			toast.error(getApiErrorDetail(e, "Reset failed"));
		}
	};

	const schema = active?.rule_schema ?? DEFAULT_RULE;
	const status = schema.circuit_breaker.tripped ? "tripped" : "healthy";

	return (
		<div className="p-6 max-w-4xl mx-auto space-y-6">
			<h1 className="text-2xl font-bold">Scraper Rules</h1>

			<Card>
				<CardHeader>
					<CardTitle>Active rule: {platform}</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="text-sm text-muted-foreground">
						version {active?.version ?? "-"} · status: {status}
					</div>

					<div>
						<Label>Selectors</Label>
						<div className="grid grid-cols-1 gap-2 mt-2">
							<Input
								data-testid="rule-editor-selectors-title"
								value={schema.selectors.title}
								onChange={(e) => updateField("selectors", "title", e.target.value)}
								placeholder="CSS selector for title"
							/>
							<Input
								data-testid="rule-editor-selectors-listing_card"
								value={schema.selectors.listing_card}
								onChange={(e) => updateField("selectors", "listing_card", e.target.value)}
								placeholder="CSS selector for listing card"
							/>
							<Input
								data-testid="rule-editor-selectors-next_page_link"
								value={schema.selectors.next_page_link}
								onChange={(e) => updateField("selectors", "next_page_link", e.target.value)}
								placeholder="CSS selector for next page link"
							/>
						</div>
					</div>

					<div>
						<Label>Regexes</Label>
						<Input
							data-testid="rule-editor-regexes-phone_in_title"
							value={schema.regexes.phone_in_title}
							onChange={(e) => updateField("regexes", "phone_in_title", e.target.value)}
							placeholder="Regex for phone in title"
						/>
					</div>

					<div className="flex gap-2">
						<Button onClick={handleSave} disabled={loading}>
							Save
						</Button>
						<Button variant="secondary" onClick={handleTrip} disabled={loading}>
							Trip Circuit Breaker
						</Button>
						<Button variant="outline" onClick={handleReset} disabled={loading}>
							Reset Circuit Breaker
						</Button>
					</div>
				</CardContent>
			</Card>

			<Card>
				<CardHeader>
					<CardTitle>All rules</CardTitle>
				</CardHeader>
				<CardContent>
					<ul className="space-y-1">
						{rules.map((r) => (
							<li key={`${r.platform}-${r.version}`} className="text-sm">
								{r.platform} — version {r.version} — {r.is_active ? "active" : "inactive"}
							</li>
						))}
					</ul>
				</CardContent>
			</Card>
		</div>
	);
}
