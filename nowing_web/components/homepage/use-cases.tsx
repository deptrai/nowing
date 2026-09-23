import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { UseCaseArt, type UseCaseArtVariant } from "@/components/homepage/use-case-art";
import { MarketingSection } from "@/components/marketing/section";

/** Buyer language from the high-CPC keyword clusters; each anchors to the connector that fulfills it. */
function getUseCases(t: (k: string) => string): {
	title: string;
	description: string;
	href: string;
	anchor: string;
	art: UseCaseArtVariant;
}[] {
	return [
		{
			title: t("uc1_title"),
			description: t("uc1_desc"),
			href: "/google-search",
			anchor: "SERP API",
			art: "serp",
		},
		{
			title: t("uc2_title"),
			description: t("uc2_desc"),
			href: "/reddit",
			anchor: "Reddit API",
			art: "brand",
		},
		{
			title: t("uc3_title"),
			description: t("uc3_desc"),
			href: "/instagram",
			anchor: "Instagram API",
			art: "chat",
		},
		{
			title: t("uc4_title"),
			description: t("uc4_desc"),
			href: "/google-maps",
			anchor: "Google Maps API",
			art: "leads",
		},
		{
			title: t("uc5_title"),
			description: t("uc5_desc"),
			href: "/web-crawl",
			anchor: "Web Crawl API",
			art: "price",
		},
	];
}

export function UseCasesRow() {
	const t = useTranslations("homepage");
	const USE_CASES = getUseCases(t);
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("what_teams_use")}</h2>
			</Reveal>
			<div className="mt-8 grid gap-6 sm:grid-cols-2">
				{USE_CASES.map((useCase) => (
					<Reveal key={useCase.title}>
						<div className="flex h-full flex-col rounded-xl border bg-card p-6">
							<UseCaseArt variant={useCase.art} />
							<h3 className="text-lg font-semibold">{useCase.title}</h3>
							<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
								{useCase.description}
							</p>
							<Link
								href={useCase.href}
								className="group mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground"
							>
								{useCase.anchor}
								<ArrowRight
									className="size-4 transition-transform group-hover:translate-x-0.5"
									aria-hidden="true"
								/>
							</Link>
						</div>
					</Reveal>
				))}
			</div>
		</MarketingSection>
	);
}
