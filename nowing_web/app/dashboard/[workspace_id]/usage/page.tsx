import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { UsageContent } from "@/components/usage/usage-content";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("usage");
	return {
		title: t("page_title"),
	};
}

export default function UsagePage() {
	return (
		<div className="mx-auto w-full max-w-5xl py-6 md:py-8">
			<UsageContent />
		</div>
	);
}
