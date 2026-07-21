import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "What's New | Nowing",
	description: "Latest product updates, feature releases, and news from Nowing.",
	alternates: {
		canonical: "https://www.nowing.com/announcements",
	},
	openGraph: {
		title: "What's New | Nowing",
		description: "Latest product updates, feature releases, and news from Nowing.",
		url: "https://www.nowing.com/announcements",
		type: "website",
	},
	twitter: {
		card: "summary_large_image",
		title: "What's New | Nowing",
		description: "Latest product updates, feature releases, and news from Nowing.",
	},
};

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
