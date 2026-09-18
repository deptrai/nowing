import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { FAQJsonLd } from "@/components/seo/json-ld";
import { useTranslations } from "next-intl";

/** Answers are 40-60 words, written as quotable definitions for AI Overviews. */
function getHomeFaq(t: (k: string) => string) {
	return [
		{ question: t("faq1_q"), answer: t("faq1_a") },
		{ question: t("faq2_q"), answer: t("faq2_a") },
		{ question: t("faq3_q"), answer: t("faq3_a") },
		{ question: t("faq4_q"), answer: t("faq4_a") },
		{ question: t("faq5_q"), answer: t("faq5_a") },
	];
}

export function HomeFaq() {
	const t = useTranslations("homepage");
	const HOME_FAQ = getHomeFaq(t);
	return (
		<MarketingSection>
			<FAQJsonLd questions={HOME_FAQ} />
			<Reveal>
				<h2 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-normal tracking-tight">{t("home_frequently_asked_questions")}</h2>
			</Reveal>
			<Reveal>
				{/* Accordion capped at a readable measure; left edge stays on the page grid. */}
				<div className="mt-6 max-w-3xl">
					<ConnectorFaq items={HOME_FAQ} />
				</div>
			</Reveal>
		</MarketingSection>
	);
}
