import type { Metadata } from "next";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import PricingBasic from "@/components/pricing/pricing-section";

export const metadata: Metadata = {
	title: "Pricing | Nowing - AI Knowledge Platform for Teams",
	description:
		"Explore Nowing plans and pricing. The AI knowledge platform for teams — cited answers, reports, and podcasts from your documents and connectors.",
	alternates: {
		canonical: "https://nowing.com/pricing",
	},
};

const page = () => {
	return (
		<div>
			<div className="container mx-auto pt-24 px-4">
				<BreadcrumbNav
					items={[
						{ name: "Home", href: "/" },
						{ name: "Pricing", href: "/pricing" },
					]}
				/>
			</div>
			<PricingBasic />
		</div>
	);
};

export default page;
