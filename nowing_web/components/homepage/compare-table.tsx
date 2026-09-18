import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { useTranslations } from "next-intl";

function getColumns(t: (k: string) => string) {
	return [
		{ label: t("col_browser"), examples: "Browserbase, Browser Use" },
		{ label: t("col_scraping"), examples: "Firecrawl" },
		{ label: t("col_search"), examples: "Exa, Tavily, Parallel" },
		{ label: t("col_marketplace"), examples: "Apify" },
	];
}

function getRows(t: (k: string) => string) {
	return [
		{ feature: t("r1_feature"), browser: t("r1_browser"), scraping: t("r1_scraping"), search: t("r1_search"), marketplace: t("r1_marketplace"), nowing: t("r1_nowing") },
		{ feature: t("r2_feature"), browser: t("r2_browser"), scraping: t("r2_scraping"), search: t("r2_search"), marketplace: t("r2_marketplace"), nowing: t("r2_nowing") },
		{ feature: t("r3_feature"), browser: t("r3_browser"), scraping: t("r3_scraping"), search: t("r3_search"), marketplace: t("r3_marketplace"), nowing: t("r3_nowing") },
		{ feature: t("r4_feature"), browser: t("r4_browser"), scraping: t("r4_scraping"), search: t("r4_search"), marketplace: t("r4_marketplace"), nowing: t("r4_nowing") },
		{ feature: t("r5_feature"), browser: t("r5_browser"), scraping: t("r5_scraping"), search: t("r5_search"), marketplace: t("r5_marketplace"), nowing: t("r5_nowing") },
		{ feature: t("r6_feature"), browser: t("r6_browser"), scraping: t("r6_scraping"), search: t("r6_search"), marketplace: t("r6_marketplace"), nowing: t("r6_nowing") },
	];
}

export function CompareTable() {
	const t = useTranslations("homepage");
	const COLUMNS = getColumns(t);
	const ROWS = getRows(t);
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-normal tracking-tight">{t("home_how_nowing_compares")}</h2>
				<p className="mt-2.5 max-w-2xl text-sm sm:text-[15px] text-muted-foreground font-sans leading-relaxed">
					{t("compare_lede")}
				</p>
			</Reveal>
			<Reveal>
				<div className="mt-8 overflow-x-auto rounded-xl border bg-card">
					<table className="w-full min-w-4xl text-xs sm:text-[13px]">
						<thead>
							<tr className="border-b bg-muted/40 text-left">
								<th className="p-4 font-medium">{t("feature")}</th>
								{COLUMNS.map((col) => (
									<th key={col.label} className="p-4 font-medium text-muted-foreground">
										{col.label}
										<span className="block text-xs font-normal">{col.examples}</span>
									</th>
								))}
								<th className="p-4 font-medium text-brand">Nowing</th>
							</tr>
						</thead>
						<tbody>
							{ROWS.map((row) => (
								<tr key={row.feature} className="border-b last:border-b-0">
									<th scope="row" className="p-4 text-left font-medium">
										{row.feature}
									</th>
									<td className="p-4 text-muted-foreground">{row.browser}</td>
									<td className="p-4 text-muted-foreground">{row.scraping}</td>
									<td className="p-4 text-muted-foreground">{row.search}</td>
									<td className="p-4 text-muted-foreground">{row.marketplace}</td>
									<td className="bg-brand/5 p-4 text-foreground">{row.nowing}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
