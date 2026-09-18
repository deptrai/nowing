import type { Metadata } from "next";
import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("home");
	const title = t("announcements_meta_title");
	const description = t("announcements_meta_description");

	return {
		title,
		description,
		alternates: {
			canonical: "https://www.nowing.com/announcements",
		},
		openGraph: {
			title,
			description,
			url: "https://www.nowing.com/announcements",
			type: "website",
		},
		twitter: {
			card: "summary_large_image",
			title,
			description,
		},
	};
}

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
