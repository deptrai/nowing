import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import PricingBasic from "@/components/pricing/pricing-section";
import { JsonLd } from "@/components/seo/json-ld";

const canonicalUrl = "https://www.nowing.com/pricing";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("home");
	const metaTitle = t("pricing_meta_title");
	const metaDescription = t("pricing_meta_description");

	return {
		title: metaTitle,
		description: metaDescription,
		keywords: [
			"nowing pricing",
			"pay as you go ai platform",
			"open core ai agent platform",
			"self-hosted ai workspace",
			"ai automation pricing",
			"web scraping api pricing",
		],
		alternates: {
			canonical: canonicalUrl,
		},
		openGraph: {
			title: metaTitle,
			description: metaDescription,
			url: canonicalUrl,
			siteName: "Nowing",
			type: "website",
			images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Nowing pricing" }],
		},
		twitter: {
			card: "summary_large_image",
			title: metaTitle,
			description: metaDescription,
			images: ["/og-image.png"],
		},
	};
}

const page = async () => {
	const t = await getTranslations("home");
	return (
		<div>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "Nowing",
					applicationCategory: "BusinessApplication",
					operatingSystem: "Windows, macOS, Linux, Web",
					url: canonicalUrl,
					offers: [
						{
							"@type": "Offer",
							name: t("pricing_offer_free_name"),
							price: "0",
							priceCurrency: "USD",
							description: t("pricing_offer_free_desc"),
						},
						{
							"@type": "Offer",
							name: t("pricing_offer_payg_name"),
							price: "0",
							priceCurrency: "USD",
							description: t("pricing_offer_payg_desc"),
						},
					],
				}}
			/>
			<PricingBasic />
		</div>
	);
};

export default page;
