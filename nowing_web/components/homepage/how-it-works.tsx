import { useTranslations } from "next-intl";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { FlowLine } from "@/components/homepage/flow-line";
import { MarketingSection } from "@/components/marketing/section";

/** Numbered because the content is genuinely sequential: connect, gather, act. */
function getSteps(t: (k: string) => string) {
	return [
		{ number: "01", title: t("step1_title"), description: t("step1_desc") },
		{ number: "02", title: t("step2_title"), description: t("step2_desc") },
		{ number: "03", title: t("step3_title"), description: t("step3_desc") },
	];
}

export function HowItWorks() {
	const t = useTranslations("homepage");
	const STEPS = getSteps(t);
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-normal tracking-tight">
					{t("how_nowing_works")}
				</h2>
			</Reveal>
			<FlowLine />
			<div className="grid gap-6 md:mt-0 mt-8 md:grid-cols-3">
				{STEPS.map((step, i) => (
					<Reveal key={step.number} delay={i * 0.06}>
						<div className="h-full rounded-xl border bg-card p-6">
							<span className="font-mono text-xs font-bold text-brand">{step.number}</span>
							<h3 className="mt-2 text-base font-semibold">{step.title}</h3>
							<p className="mt-2 text-xs sm:text-[13px] leading-relaxed text-muted-foreground">
								{step.description}
							</p>
						</div>
					</Reveal>
				))}
			</div>
		</MarketingSection>
	);
}
