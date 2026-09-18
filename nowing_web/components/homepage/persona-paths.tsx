import { ArrowRight, Code2, Megaphone } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { UseCaseArt, type UseCaseArtVariant } from "@/components/homepage/use-case-art";
import { MarketingSection } from "@/components/marketing/section";
import { useTranslations } from "next-intl";

/**
 * Answers "is this for me?" right below the hero: one card per audience.
 * Revenue persona (founders / marketing teams) first, growth persona
 * (developers / agent builders) second.
 */
function getPaths(t: (k: string) => string): {
	icon: typeof Megaphone;
	art: UseCaseArtVariant;
	eyebrow: string;
	title: string;
	description: string;
	links: { label: string; href: string }[];
}[] {
	return [
		{
			icon: Megaphone,
			art: "chat",
			eyebrow: t("founders_eyebrow"),
			title: t("founders_title"),
			description: t("founders_desc"),
			links: [
				{ label: t("see_what_teams_build"), href: "/connectors" },
				{ label: t("pricing"), href: "/pricing" },
			],
		},
		{
			icon: Code2,
			art: "api",
			eyebrow: t("devs_eyebrow"),
			title: t("devs_title"),
			description: t("devs_desc"),
			links: [
				{ label: t("read_docs"), href: "/docs" },
				{ label: t("mcp_server"), href: "/mcp-server" },
			],
		},
	];
}

export function PersonaPaths() {
	const t = useTranslations("homepage");
	const PATHS = getPaths(t);
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("who_nowing_is_for")}</h2>
			</Reveal>
			<div className="mt-8 grid gap-6 md:grid-cols-2">
				{PATHS.map((path) => {
					const Icon = path.icon;
					return (
						<Reveal key={path.eyebrow}>
							<div className="flex h-full flex-col rounded-xl border bg-card p-6">
								<UseCaseArt variant={path.art} />
								<div className="flex items-center gap-2 text-sm font-medium text-brand">
									<Icon className="size-4" aria-hidden />
									{path.eyebrow}
								</div>
								<h3 className="mt-3 text-lg font-semibold">{path.title}</h3>
								<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
									{path.description}
								</p>
								<div className="mt-4 flex flex-wrap gap-4">
									{path.links.map((link) => (
										<Link
											key={link.href}
											href={link.href}
											className="group inline-flex items-center gap-1 text-sm font-medium text-foreground"
										>
											{link.label}
											<ArrowRight
												className="size-4 transition-transform group-hover:translate-x-0.5"
												aria-hidden="true"
											/>
										</Link>
									))}
								</div>
							</div>
						</Reveal>
					);
				})}
			</div>
		</MarketingSection>
	);
}
