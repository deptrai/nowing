import { Suspense } from "react";
import { AuthRedirect } from "@/components/homepage/auth-redirect";
import { AffiliateBanner } from "@/components/landing/AffiliateBanner";
import { LiveMetricsCounter } from "@/components/landing/LiveMetricsCounter";
import { NowingCompareTable } from "@/components/landing/NowingCompareTable";
import { NowingFaq } from "@/components/landing/NowingFaq";
import { NowingFooter } from "@/components/landing/NowingFooter";
import { NowingHero } from "@/components/landing/NowingHero";
import { NowingPricingSection } from "@/components/landing/NowingPricingSection";
import { ProductShowcaseTabs } from "@/components/landing/ProductShowcaseTabs";
import { VerticalsMegaGrid } from "@/components/landing/VerticalsMegaGrid";
import { WorkflowSteps } from "@/components/landing/WorkflowSteps";

export default function HomePage() {
	return (
		<div className="min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-white antialiased selection:bg-emerald-500 selection:text-white">
			<Suspense fallback={null}>
				<AuthRedirect />
			</Suspense>

			{/* Section 1: Hero Section with Sọc Caro Grid & Prompt Input */}
			<NowingHero />

			{/* Section 2: Interactive 3-Tab Product Showcase (Live Table Matrix) */}
			<ProductShowcaseTabs />

			{/* Section 3: Value Metrics & Live Data Stats */}
			<LiveMetricsCounter />

			{/* Section 4: 12 Industry Verticals Grid */}
			<VerticalsMegaGrid />

			{/* Section 5: Step-by-Step Workflow */}
			<WorkflowSteps />

			{/* Section 6: Direct Comparison Table (Nowing vs Apollo vs Clay) */}
			<NowingCompareTable />

			{/* Section 7: $0 Pricing Matrix & Pay-as-you-go Credits */}
			<NowingPricingSection />

			{/* Section 8: Affiliate Partner 15% Banner */}
			<AffiliateBanner />

			{/* Section 9: FAQ Accordion */}
			<NowingFaq />

			{/* Section 10: Editorial Footer */}
			<NowingFooter />
		</div>
	);
}
