import { loader } from "fumadocs-core/source";
import type { MDXComponents } from "mdx/types";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import type { ComponentType } from "react";
import { changelog } from "@/.source/server";
import { ChangelogTimeline, type ChangelogTimelineEntry } from "@/components/ui/changelog-timeline";
import { formatDate } from "@/lib/utils";
import { getMDXComponents } from "@/mdx-components";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("home");
	return {
		title: t("changelog_meta_title"),
		description: t("changelog_meta_description"),
		alternates: {
			canonical: "https://www.nowing.com/changelog",
		},
	};
}

const source = loader({
	baseUrl: "/changelog",
	source: changelog.toFumadocsSource(),
});

interface ChangelogData {
	date: string;
	version?: string;
	body: ComponentType<{ components?: MDXComponents }>;
}

interface ChangelogPageItem {
	url: string;
	data: ChangelogData;
}

export default async function ChangelogPage() {
	const t = await getTranslations("home");
	const allPages = source.getPages() as ChangelogPageItem[];
	const sortedChangelogs = allPages.toSorted((a, b) => {
		const dateA = new Date(a.data.date).getTime();
		const dateB = new Date(b.data.date).getTime();
		return dateB - dateA;
	});
	const entries: ChangelogTimelineEntry[] = sortedChangelogs.map((changelog) => {
		const MDX = changelog.data.body;
		const date = new Date(changelog.data.date);

		return {
			version: changelog.data.version
				? t("changelog_version", { version: changelog.data.version })
				: t("changelog_release"),
			date: formatDate(date),
			content: <MDX components={getMDXComponents()} />,
		};
	});

	return (
		<div className="min-h-screen relative pt-20">
			<ChangelogTimeline
				title={t("changelog_title")}
				description={t("changelog_description")}
				entries={entries}
				className="pt-12"
			/>
		</div>
	);
}
