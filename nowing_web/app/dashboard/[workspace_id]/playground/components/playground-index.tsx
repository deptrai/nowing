"use client";

import { ArrowRight, History, Info, KeyRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useScraperCapabilities } from "@/hooks/use-scraper-capabilities";
import { PLAYGROUND_PLATFORMS } from "@/lib/playground/catalog";
import { formatPricing } from "@/lib/playground/format";

function usePlaygroundBase(workspaceId: number) {
	const pathname = usePathname();
	const userSettingsBase = `/dashboard/${workspaceId}/user-settings/playground`;
	if (pathname?.startsWith(userSettingsBase)) return userSettingsBase;
	return `/dashboard/${workspaceId}/playground`;
}

export function PlaygroundIndex({ workspaceId }: { workspaceId: number }) {
	const t = useTranslations("playground");
	const base = usePlaygroundBase(workspaceId);

	// The grid renders from the static catalog immediately; pricing fills in
	// once the capabilities fetch lands (blank while loading, never blocking).
	const { data: capabilities } = useScraperCapabilities(workspaceId);
	const pricingByName = useMemo(
		() => new Map(capabilities?.map((c) => [c.name, formatPricing(c.pricing)])),
		[capabilities]
	);

	return (
		<div className="space-y-8">
			<Alert>
				<Info />
				<AlertDescription>
					<p>
						{t.rich("intro", {
							link: (chunks) => (
								<Link
									href={`${base}/api-keys`}
									className="font-medium text-foreground underline-offset-4 hover:underline"
								>
									{chunks}
								</Link>
							),
						})}
					</p>
				</AlertDescription>
			</Alert>

			<div className="grid gap-3 sm:grid-cols-2">
				<Link
					href={`${base}/runs`}
					className="flex items-center justify-between rounded-lg border border-border/60 bg-accent/40 px-4 py-3 transition-colors hover:bg-accent"
				>
					<div className="flex items-center gap-3">
						<History className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
						<div>
							<p className="text-sm font-medium">{t("api_runs")}</p>
							<p className="text-xs text-muted-foreground">{t("api_runs_description")}</p>
						</div>
					</div>
					<ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
				</Link>
				<Link
					href={`${base}/api-keys`}
					className="flex items-center justify-between rounded-lg border border-border/60 bg-accent/40 px-4 py-3 transition-colors hover:bg-accent"
				>
					<div className="flex items-center gap-3">
						<KeyRound className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
						<div>
							<p className="text-sm font-medium">{t("api_keys")}</p>
							<p className="text-xs text-muted-foreground">{t("api_keys_description")}</p>
						</div>
					</div>
					<ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
				</Link>
			</div>

			<div className="space-y-6">
				{PLAYGROUND_PLATFORMS.map((platform) => (
					<div key={platform.id} className="space-y-3">
						<div className="flex items-center gap-2">
							<platform.icon className="h-4 w-4 text-muted-foreground" />
							<h2 className="text-sm font-semibold">{platform.label}</h2>
						</div>
						<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
							{platform.verbs.map((verb) => (
								<Link
									key={verb.name}
									href={`${base}/${platform.id}/${verb.verb}`}
									className="group flex flex-col rounded-lg border border-border/60 p-4 transition-colors hover:border-border hover:bg-muted/30"
								>
									<div className="flex items-center justify-between">
										<span className="text-sm font-medium">{verb.label}</span>
										<ArrowRight
											className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
											aria-hidden="true"
										/>
									</div>
									<code className="mt-2 text-xs text-muted-foreground">{verb.name}</code>
									{pricingByName.has(verb.name) ? (
										<span className="mt-2 text-xs tabular-nums text-muted-foreground">
											{pricingByName.get(verb.name)}
										</span>
									) : null}
								</Link>
							))}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}
