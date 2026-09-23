import { IconBrandDiscord, IconBrandGithub, IconBrandReddit } from "@tabler/icons-react";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { Button } from "@/components/ui/button";

const GITHUB_URL = "https://github.com/deptrai/nowing";
const DISCORD_URL = "https://discord.gg/ejRNvftDp9";
const REDDIT_URL = "https://www.reddit.com/r/Nowing/";

/** Closing CTA doubling as the GitHub/community strip (brief section 7). */
export function CommunityStrip() {
	const t = useTranslations("homepage");
	return (
		<MarketingSection>
			<Reveal>
				<div className="rounded-2xl border bg-card p-8 text-center sm:p-12">
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("community_title")}</h2>
					<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
						{t("community_desc")}
					</p>
					<div className="mt-7 flex flex-wrap justify-center gap-3">
						<Button asChild size="lg">
							<Link href="/register">
								{t("community_start_free")}
								<ArrowRight className="size-4" aria-hidden="true" />
							</Link>
						</Button>
						<Button asChild variant="outline" size="lg">
							<Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandGithub className="size-4" aria-hidden="true" />
								{t("community_star_github")}
							</Link>
						</Button>
						<Button asChild variant="ghost" size="lg">
							<Link href={DISCORD_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandDiscord className="size-4" aria-hidden="true" />
								{t("community_join_discord")}
							</Link>
						</Button>
						<Button asChild variant="ghost" size="lg">
							<Link href={REDDIT_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandReddit className="size-4" aria-hidden="true" />
								r/Nowing
							</Link>
						</Button>
					</div>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
